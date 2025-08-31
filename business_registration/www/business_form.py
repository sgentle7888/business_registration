import frappe
from frappe import _
from frappe.utils import now_datetime, add_to_date, get_url
from frappe.utils.file_manager import save_file
import json
import secrets
import re


def get_context(context):
    """Get context for business registration form - supports guest access"""
    
    # Allow guest access for business registration
    is_guest = frappe.session.user == "Guest"
    registration_id = frappe.form_dict.get('registration_id')
    
    if registration_id:
        # Editing existing registration
        try:
            business_registration = frappe.get_doc("Business Registration", registration_id)
            # Only allow editing if status is Draft or Rejected
            if business_registration.application_status not in ['Draft', 'Rejected']:
                frappe.throw(_("This application cannot be edited as it has been submitted for review"))
        except frappe.DoesNotExistError:
            frappe.throw(_("Business registration not found"))
    else:
        # Creating new registration
        business_registration = frappe.new_doc("Business Registration")
        business_registration.application_status = "Draft"
    
    # Get company name safely
    company_name = "Business Registration Authority"
    try:
        companies = frappe.get_all("Company", fields=["company_name"], limit=1)
        if companies:
            company_name = companies[0].company_name
    except Exception:
        pass  # Use default if Company doctype doesn't exist
    
    # Get dropdown options
    business_types = [
        "Limited Liability Company",
        "Public Limited Company", 
        "Partnership",
        "Sole Proprietorship",
        "Non-Profit Organization",
        "Others"
    ]
    
    nigerian_states = [
        "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue", 
        "Borno", "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu", 
        "FCT", "Gombe", "Imo", "Jigawa", "Kaduna", "Kano", "Katsina", "Kebbi", 
        "Kogi", "Kwara", "Lagos", "Nasarawa", "Niger", "Ogun", "Ondo", "Osun", 
        "Oyo", "Plateau", "Rivers", "Sokoto", "Taraba", "Yobe", "Zamfara"
    ]
    
    # Set context variables
    context.business_registration = business_registration
    context.is_guest = is_guest
    context.business_types = business_types
    context.nigerian_states = nigerian_states
    context.company_name = company_name
    context.title = _("Business Registration Application")
    context.no_cache = 1
    
    return context


@frappe.whitelist(allow_guest=True)
def submit_registration_data():
    """Submit registration data and files at once"""
    
    try:
        form_data = frappe.form_dict
        
        # Create new registration
        business_registration = frappe.new_doc("Business Registration")
        business_registration.application_status = "Under Review"
        
        # Process phone numbers with country codes
        _process_phone_numbers(business_registration, form_data)
        
        # Update basic fields
        _update_basic_fields(business_registration, form_data)
        
        # Process branch/outlets data
        _process_branch_outlets(business_registration, form_data)
        
        # Set submission timestamp
        business_registration.submission_date = now_datetime()
        business_registration.review_date = now_datetime()
        
        # Set flag to skip attachment validation during initial insert
        business_registration.flags.ignore_attachment_validation = True
        business_registration.flags.ignore_permissions = True
        
        # Insert document first (creates the name/ID)
        business_registration.insert()
        
        # NOW handle file attachments after document exists
        _handle_file_attachments(business_registration, form_data)
        
        # Remove the flag and validate everything including attachments
        business_registration.flags.ignore_attachment_validation = False
        validation_errors = _validate_registration_for_submission(business_registration)
        if validation_errors:
            # If validation fails, delete the created document
            frappe.delete_doc("Business Registration", business_registration.name, force=True)
            frappe.db.commit()
            return {
                "status": "error", 
                "message": "Please complete all required fields", 
                "errors": validation_errors
            }
        
        # Save again to update with file attachments and submit
        business_registration.save()
        business_registration.submit()
        frappe.db.commit()
        
        return {
            "status": "success",
            "message": "Application submitted successfully and is now under review. You will receive email notifications about the review status.",
            "registration_id": business_registration.name,
            "registration_name": business_registration.business_name
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Business Registration Submission Error")
        return {"status": "error", "message": str(e)}
    
def _process_phone_numbers(business_registration, form_data):
    """Process phone numbers with country codes"""
    
    phone_fields = ['contact_phone_number', 'alternative_phone', 'representative_contact_phone']
    
    for phone_field in phone_fields:
        if phone_field in form_data and form_data.get(phone_field):
            country_code_field = f"{phone_field}_country_code"
            phone_number = form_data.get(phone_field)
            country_code = form_data.get(country_code_field, '+234')
            
            # Format phone number with country code
            if phone_number and not phone_number.startswith('+'):
                # Clean the phone number
                clean_phone = re.sub(r'\D', '', phone_number.lstrip('0'))
                formatted_phone = f"{country_code}{clean_phone}"
                setattr(business_registration, phone_field, formatted_phone)
            elif phone_number:
                setattr(business_registration, phone_field, phone_number)


def _update_basic_fields(business_registration, form_data):
    """Update basic registration fields"""
    
    updateable_fields = [
        'business_name', 'cac_number', 'premises_licence_number', 'annual_turnover',
        'business_type', 'date_of_incorporation', 'address_line1', 'address_line2',
        'address_line3', 'town_or_city', 'local_government', 'state', 'postal_code',
        'country', 'contact_person', 'contact_email', 'website', 'representative_full_name',
        'representative_contact_email', 'representative_designation', 'representative_address',
        'details_of_business_references'
    ]
    
    for field in updateable_fields:
        if field in form_data and hasattr(business_registration, field):
            value = form_data.get(field)
            if value:
                setattr(business_registration, field, value)


def _process_branch_outlets(business_registration, form_data):
    """Process branch/outlets data from form"""
    
    # Clear existing branches
    business_registration.branch_outlets = []
    
    # Process form data for branches
    branches_data = {}
    
    # Extract branch data from form_data
    for key, value in form_data.items():
        if key.startswith('branch_outlets[') and value:
            match = re.match(r'branch_outlets\[(\d+)\]\[(\w+)\]', key)
            if match:
                index = int(match.group(1))
                field_name = match.group(2)
                
                if index not in branches_data:
                    branches_data[index] = {}
                
                branches_data[index][field_name] = value
    
    # Add branches to the registration
    for index in sorted(branches_data.keys()):
        branch_data = branches_data[index]
        
        # Only add if both name and address are provided
        if branch_data.get('branch_name') and branch_data.get('branch_address'):
            branch_row = business_registration.append('branch_outlets', {})
            branch_row.branch_name = branch_data['branch_name']
            branch_row.branch_address = branch_data['branch_address']


def _handle_file_attachments(business_registration, form_data):
    """Handle file attachments for the registration"""
    
    # Remove this line since document will already exist when we call this function
    # if not business_registration.name:
    #     frappe.throw("Document must be saved before attaching files")
    
    file_fields = ['business_registration_details', 'proof_of_address', 'additional_documents']
    
    for field in file_fields:
        uploaded_file = frappe.request.files.get(field)
        
        if uploaded_file and uploaded_file.filename:
            try:
                # Validate file size (5MB limit)
                max_size = 5 * 1024 * 1024  # 5MB
                uploaded_file.seek(0, 2)
                file_size = uploaded_file.tell()
                uploaded_file.seek(0)
                
                if file_size > max_size:
                    frappe.throw(f"File {uploaded_file.filename} is too large. Maximum size is 5MB.")
                
                # Validate file type
                allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png']
                file_extension = '.' + uploaded_file.filename.split('.')[-1].lower()
                
                if file_extension not in allowed_extensions:
                    frappe.throw(f"File type {file_extension} not allowed. Please upload PDF, JPG, or PNG files only.")
                
                # Save the file
                file_doc = save_file(
                    fname=uploaded_file.filename,
                    content=uploaded_file.read(),
                    dt="Business Registration",
                    dn=str(business_registration.name),
                    folder=None,
                    decode=False,
                    is_private=1
                )
                
                # Set the file URL in the document
                setattr(business_registration, field, file_doc.file_url)
                
            except Exception as e:
                frappe.log_error(f"File upload error for {field}: {str(e)}")
                frappe.throw(f"Error uploading {field}: {str(e)}")

def _validate_registration_for_submission(business_registration):
    """Validate registration before submission"""
    
    errors = []
    
    # Required fields for submission
    required_fields = [
        ('business_name', 'Business Name'),
        ('cac_number', 'CAC Number'),
        ('annual_turnover', 'Annual Turnover'),
        ('address_line1', 'Address Line 1'),
        ('town_or_city', 'Town/City'),
        ('state', 'State'),
        ('contact_person', 'Contact Person'),
        ('contact_phone_number', 'Contact Phone Number'),
        ('contact_email', 'Contact Email'),
        ('representative_full_name', 'Representative Full Name'),
        ('representative_contact_email', 'Representative Contact Email'),
        ('representative_contact_phone', 'Representative Contact Phone'),
        ('business_registration_details', 'Business Registration Details'),
        ('proof_of_address', 'Proof of Address')
    ]
    
    for field, label in required_fields:
        if not getattr(business_registration, field):
            errors.append(label)
    
    return errors


@frappe.whitelist(allow_guest=True)
def get_registration_status():
    """Get registration status for tracking"""
    
    try:
        registration_id = frappe.form_dict.get('registration_id')
        
        if not registration_id:
            return {"status": "error", "message": "Registration ID is required"}
        
        business_registration = frappe.get_doc("Business Registration", registration_id)
        
        status_info = {
            "registration_id": business_registration.name,
            "business_name": business_registration.business_name,
            "application_status": business_registration.application_status,
            "submission_date": business_registration.submission_date,
            "review_date": business_registration.review_date,
            "approval_date": business_registration.approval_date,
            "rejection_reason": business_registration.rejection_reason
        }
        
        return {"status": "success", "registration": status_info}
        
    except frappe.DoesNotExistError:
        return {"status": "error", "message": "Registration not found"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Registration Status Error")
        return {"status": "error", "message": "An error occurred"}