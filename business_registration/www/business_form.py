import frappe
from frappe import _
from frappe.utils import now_datetime, add_to_date, get_url
from frappe.utils.file_manager import save_file  # moved import to top of file
import json
import secrets

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
    
    context.business_registration = business_registration
    context.is_guest = is_guest
    context.business_types = business_types
    context.nigerian_states = nigerian_states
    context.title = _("Business Registration Application")
    context.no_cache = 1
    
    return context

@frappe.whitelist(allow_guest=True)
def create_or_update_registration():
    """Handle business registration form submission - supports guest access"""
    
    try:
        form_data = frappe.form_dict
        registration_id = form_data.get('registration_id')
        
        if registration_id:
            # Update existing registration
            try:
                business_registration = frappe.get_doc("Business Registration", registration_id)
                # Only allow editing if status is Draft or Rejected
                if business_registration.application_status not in ['Draft', 'Rejected']:
                    return {"status": "error", "message": "This application cannot be edited as it has been submitted for review"}
            except frappe.DoesNotExistError:
                return {"status": "error", "message": "Business registration not found"}
        else:
            # Create new registration
            business_registration = frappe.new_doc("Business Registration")
            business_registration.application_status = "Draft"
        
        phone_fields = ['contact_phone_number', 'alternative_phone', 'representative_contact_phone']
        for phone_field in phone_fields:
            if phone_field in form_data and form_data.get(phone_field):
                country_code_field = f"{phone_field}_country_code"
                phone_number = form_data.get(phone_field)
                country_code = form_data.get(country_code_field, '+234')  # Default to Nigeria
                
                # Format phone number with country code if not already formatted
                if phone_number and not phone_number.startswith('+'):
                    # Remove any leading zeros or spaces
                    phone_number = phone_number.lstrip('0').strip()
                    formatted_phone = f"{country_code}{phone_number}"
                    setattr(business_registration, phone_field, formatted_phone)
                elif phone_number:
                    setattr(business_registration, phone_field, phone_number)
        
        # Update other registration fields
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
        
        # Process branch/outlets data
        process_branch_outlets(business_registration, form_data)
        
        business_registration.flags.ignore_permissions = True
        business_registration.save()
        
        # Handle file attachments after document has a name
        handle_file_attachments(business_registration, form_data)
        
        business_registration.save()
        frappe.db.commit()
        
        return {
            "status": "success", 
            "message": "Registration saved successfully",
            "registration_id": business_registration.name,
            "registration_name": business_registration.business_name
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Business Registration Create/Update Error")
        return {"status": "error", "message": str(e)}

@frappe.whitelist(allow_guest=True)
def submit_registration():
    """Submit registration for review"""
    
    try:
        registration_id = frappe.form_dict.get('registration_id')
        
        if not registration_id:
            return {"status": "error", "message": "Registration ID is required"}
        
        business_registration = frappe.get_doc("Business Registration", registration_id)
        
        # Validate required fields before submission
        validation_errors = validate_registration_for_submission(business_registration)
        if validation_errors:
            return {"status": "error", "message": "Please complete all required fields", "errors": validation_errors}
        
        # Update status to Submitted
        business_registration.application_status = "Submitted"
        business_registration.submission_date = now_datetime()
        business_registration.flags.ignore_permissions = True
        business_registration.save()
        frappe.db.commit()
        
        return {
            "status": "success", 
            "message": "Application submitted successfully. You will receive email notifications about the review status.",
            "registration_id": business_registration.name
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Business Registration Submission Error")
        return {"status": "error", "message": str(e)}

def process_branch_outlets(business_registration, form_data):
    """Process branch/outlets data from form"""
    
    # Clear existing branches
    business_registration.branch_outlets = []
    
    # Process form data for branches
    branches_data = {}
    
    # Extract branch data from form_data
    for key, value in form_data.items():
        if key.startswith('branch_outlets[') and value:
            # Parse key like 'branch_outlets[0][branch_name]'
            import re
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

def handle_file_attachments(business_registration, form_data):
    """Handle file attachments for the registration"""
    
    if not business_registration.name:
        frappe.throw("Document must be saved before attaching files")
    
    # Handle file uploads if present
    file_fields = ['business_registration_details', 'proof_of_address', 'additional_documents']
    
    for field in file_fields:
        # Check if file was uploaded for this field
        uploaded_file = frappe.request.files.get(field)
        
        if uploaded_file and uploaded_file.filename:
            try:
                # Validate file size (5MB limit)
                max_size = 5 * 1024 * 1024  # 5MB in bytes
                uploaded_file.seek(0, 2)  # Seek to end
                file_size = uploaded_file.tell()
                uploaded_file.seek(0)  # Reset to beginning
                
                if file_size > max_size:
                    frappe.throw(f"File {uploaded_file.filename} is too large. Maximum size is 5MB.")
                
                # Validate file type
                allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png']
                file_extension = '.' + uploaded_file.filename.split('.')[-1].lower()
                
                if file_extension not in allowed_extensions:
                    frappe.throw(f"File type {file_extension} not allowed. Please upload PDF, JPG, or PNG files only.")
                
                file_doc = save_file(
                    fname=uploaded_file.filename,
                    content=uploaded_file.read(),
                    dt="Business Registration",
                    dn=str(business_registration.name),  # Ensure name is string
                    folder=None,
                    decode=False,
                    is_private=1
                )
                
                # Set the file URL in the business registration document
                setattr(business_registration, field, file_doc.file_url)
                
            except Exception as e:
                frappe.log_error(f"File upload error for {field}: {str(e)}")
                frappe.throw(f"Error uploading {field}: {str(e)}")
        
        # If no new file uploaded but field exists in form_data, keep existing value
        elif field in form_data and form_data[field]:
            # This handles cases where the field already has a value and we're updating other fields
            existing_value = getattr(business_registration, field, None)
            if existing_value:
                setattr(business_registration, field, existing_value)

def validate_registration_for_submission(business_registration):
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
