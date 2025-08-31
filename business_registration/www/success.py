import frappe
from frappe import _

def get_context(context):
    """Get context for success page"""
    
    # Get query parameters
    registration_id = frappe.form_dict.get('registration_id')
    business_name = frappe.form_dict.get('business_name')
    
    # Get company name
    company_name = "Business Registration Authority"
    try:
        companies = frappe.get_all("Company", fields=["company_name"], limit=1)
        if companies:
            company_name = companies[0].company_name
    except Exception:
        pass
    
    # Set context variables
    context.registration_id = registration_id
    context.business_name = business_name
    context.company_name = company_name
    context.title = _("Application Submitted Successfully")
    context.no_cache = 1
    
    return context