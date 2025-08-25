import frappe
from frappe import _
from frappe.utils import now_datetime, add_to_date, get_url
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
        
        # Update registration fields
        updateable_fields = [
            'business_name', 'cac_number', 'premises_licence_number', 'annual_turnover',
            'business_type', 'date_of_incorporation', 'address_line1', 'address_line2',
            'address_line3', 'town_or_city', 'local_government', 'state', 'postal_code',
            'country', 'contact_person', 'contact_phone_number', 'contact_email',
            'alternative_phone', 'website', 'representative_full_name',
            'representative_contact_email', 'representative_contact_phone',
            'representative_designation', 'representative_address',
            'details_of_business_references'
        ]
        
        for field in updateable_fields:
            if field in form_data and hasattr(business_registration, field):
                value = form_data.get(field)
                if value:
                    setattr(business_registration, field, value)
        
        # Process branch/outlets data
        process_branch_outlets(business_registration, form_data)
        
        # Handle file attachments
        handle_file_attachments(business_registration, form_data)
        
        # Save with system permissions
        business_registration.flags.ignore_permissions = True
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
    
    # Handle file uploads if present
    file_fields = ['business_registration_details', 'proof_of_address', 'additional_documents']
    
    for field in file_fields:
        if field in form_data and form_data[field]:
            # File handling would be implemented based on your file upload system
            # This is a placeholder for file attachment logic
            setattr(business_registration, field, form_data[field])

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
