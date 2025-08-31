import frappe
from frappe import _
from frappe.utils.pdf import get_pdf
from frappe.utils.jinja import render_template

def get_context(context):
    """Get context for download form page"""
    
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
    context.title = _("Download Business Registration Form")
    context.no_cache = 1
    
    return context

@frappe.whitelist(allow_guest=True)
def generate_empty_form():
    """Generate empty PDF form for manual filling"""
    
    try:
        # Get company info
        company_name = "Business Registration Authority"
        try:
            companies = frappe.get_all("Company", fields=["company_name"], limit=1)
            if companies:
                company_name = companies[0].company_name
        except Exception:
            pass
        
        # Prepare context data for empty form
        context = {
            "company_name": company_name,
            "frappe": frappe,
            "business_types": [
                "Limited Liability Company",
                "Public Limited Company", 
                "Partnership",
                "Sole Proprietorship",
                "Non-Profit Organization",
                "Others"
            ],
            "nigerian_states": [
                "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue", 
                "Borno", "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu", 
                "FCT", "Gombe", "Imo", "Jigawa", "Kaduna", "Kano", "Katsina", "Kebbi", 
                "Kogi", "Kwara", "Lagos", "Nasarawa", "Niger", "Ogun", "Ondo", "Osun", 
                "Oyo", "Plateau", "Rivers", "Sokoto", "Taraba", "Yobe", "Zamfara"
            ]
        }
        
        # Get the empty form template
        template_path = frappe.get_app_path("business_registration", "business_registration", "doctype", "business_registration", "templates", "empty_form_pdf.html")
        
        # Render HTML template
        html_content = render_template(template_path, context)
        
        # Generate PDF
        pdf_content = get_pdf(html_content, {
            "page-size": "A4",
            "margin-top": "0.5in",
            "margin-right": "0.5in",
            "margin-bottom": "0.5in",
            "margin-left": "0.5in",
            "encoding": "UTF-8",
            "no-outline": None
        })
        
        # Set response headers for PDF download
        filename = f"Business_Registration_Form_Empty_{frappe.utils.today()}.pdf"
        frappe.local.response.filename = filename
        frappe.local.response.filecontent = pdf_content
        frappe.local.response.type = "download"
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Empty PDF Generation Error")
        frappe.throw(_("Error generating empty form PDF: {0}").format(str(e)))