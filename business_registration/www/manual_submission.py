import frappe
from frappe import _
from frappe.utils import now_datetime
from frappe.utils.file_manager import save_file
import re

def get_context(context):
    """Get context for manual submission page"""
    
    # Get company name
    company_name = "Business Registration Authority"
    try:
        companies = frappe.get_all("Company", fields=["company_name"], limit=1)
        if companies:
            company_name = companies[0].company_name
    except Exception:
        pass
    
    # Set context variables
    context.company_name = company_name
    context.title = _("Manual Form Submission")
    context.no_cache = 1
    
    return context

@frappe.whitelist(allow_guest=True)
def submit_manual_application():
    """Submit manually filled application"""
    
    try:
        form_data = frappe.form_dict
        
        # Create new registration
        business_registration = frappe.new_doc("Business Registration")
        business_registration.application_status = "Under Review"
        
        # Set basic information from form
        business_registration.business_name = form_data.get('business_name')
        business_registration.contact_person = form_data.get('contact_person')
        business_registration.contact_email = form_data.get('contact_email')
        business_registration.contact_phone_number = form_data.get('contact_phone')
        
        # Set submission info
        business_registration.submission_date = now_datetime()
        business_registration.review_date = now_datetime()
        
        # Add note that this was submitted manually
        additional_notes = form_data.get('additional_notes', '')
        internal_note = "This application was submitted using the manual form submission process."
        if additional_notes:
            internal_note += f"\n\nAdditional Notes from Applicant:\n{additional_notes}"
        business_registration.internal_notes = internal_note
        
        # Set flags for initial creation
        business_registration.flags.ignore_attachment_validation = True
        business_registration.flags.ignore_permissions = True
        
        # Insert document first
        business_registration.insert()
        
        # Handle file attachments
        file_fields = {
            'completed_form': 'Completed Registration Form',
            'business_registration_details': 'Business Registration Details', 
            'proof_of_address': 'Proof of Address',
            'additional_documents': 'Additional Documents'
        }
        
        for field_name, description in file_fields.items():
            uploaded_file = frappe.request.files.get(field_name)
            
            if uploaded_file and uploaded_file.filename:
                try:
                    # Validate file size (5MB limit)
                    max_size = 5 * 1024 * 1024
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
                        fname=f"{description}_{uploaded_file.filename}",
                        content=uploaded_file.read(),
                        dt="Business Registration",
                        dn=str(business_registration.name),
                        folder=None,
                        decode=False,
                        is_private=1
                    )
                    
                    # For completed form, save as business registration details if that field is empty
                    if field_name == 'completed_form':
                        business_registration.business_registration_details = file_doc.file_url
                    elif hasattr(business_registration, field_name):
                        setattr(business_registration, field_name, file_doc.file_url)
                        
                except Exception as e:
                    frappe.log_error(f"File upload error for {field_name}: {str(e)}")
                    frappe.throw(f"Error uploading {description}: {str(e)}")
        
        # Save the document with all attachments
        business_registration.flags.ignore_attachment_validation = False
        business_registration.save()
        business_registration.submit()
        frappe.db.commit()
        
        return {
            "status": "success",
            "message": "Application submitted successfully and is now under review.",
            "registration_id": business_registration.name,
            "business_name": business_registration.business_name
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Manual Submission Error")
        frappe.throw(_("Error submitting manual application: {0}").format(str(e)))