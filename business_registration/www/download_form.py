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
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Business Registration Form</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .form-section {{ margin-bottom: 25px; page-break-inside: avoid; }}
        .form-section h3 {{ background: #f0f0f0; padding: 10px; margin: 0 0 15px 0; }}
        .form-group {{ margin-bottom: 15px; }}
        .form-group label {{ font-weight: bold; display: block; margin-bottom: 5px; }}
        .form-control {{ border: 1px solid #ccc; padding: 8px; width: 100%; min-height: 25px; }}
        .checkbox-group {{ display: flex; flex-wrap: wrap; gap: 15px; }}
        .checkbox-item {{ display: flex; align-items: center; gap: 5px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
        .signature-box {{ border: 1px solid #ccc; height: 50px; width: 200px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{context['company_name']}</h1>
        <h2>Business Registration Application Form</h2>
        <p><strong>Please fill all sections completely and legibly</strong></p>
    </div>

    <div class="form-section">
        <h3>1. BUSINESS INFORMATION</h3>
        <div class="form-group">
            <label>Business Name: *</label>
            <div class="form-control"></div>
        </div>
        <div class="form-group">
            <label>CAC Number: *</label>
            <div class="form-control"></div>
        </div>
        <div class="form-group">
            <label>Business Type:</label>
            <div class="checkbox-group">
                {' '.join([f'<div class="checkbox-item"><input type="checkbox"> {btype}</div>' for btype in context['business_types']])}
            </div>
        </div>
        <div class="form-group">
            <label>Annual Turnover (₦): *</label>
            <div class="form-control"></div>
        </div>
        <div class="form-group">
            <label>Date of Incorporation:</label>
            <div class="form-control"></div>
        </div>
        <div class="form-group">
            <label>Premises Licence Number:</label>
            <div class="form-control"></div>
        </div>
        <div class="form-group">
            <label>Website:</label>
            <div class="form-control"></div>
        </div>
    </div>

    <div class="form-section">
        <h3>2. BUSINESS ADDRESS</h3>
        <div class="form-group">
            <label>Address Line 1: *</label>
            <div class="form-control"></div>
        </div>
        <div class="form-group">
            <label>Address Line 2:</label>
            <div class="form-control"></div>
        </div>
        <div class="form-group">
            <label>Address Line 3:</label>
            <div class="form-control"></div>
        </div>
        <div class="form-group">
            <label>Town/City: *</label>
            <div class="form-control"></div>
        </div>
        <div class="form-group">
            <label>State: *</label>
            <div class="checkbox-group">
                {' '.join([f'<div class="checkbox-item"><input type="checkbox"> {state}</div>' for state in context['nigerian_states'][:18]])}
            </div>
            <div class="checkbox-group" style="margin-top: 10px;">
                {' '.join([f'<div class="checkbox-item"><input type="checkbox"> {state}</div>' for state in context['nigerian_states'][18:]])}
            </div>
        </div>
        <div class="form-group">
            <label>Local Government:</label>
            <div class="form-control"></div>
        </div>
        <div class="form-group">
            <label>Postal Code:</label>
            <div class="form-control"></div>
        </div>
    </div>

    <div class="form-section">
        <h3>3. CONTACT INFORMATION</h3>
        <div class="form-group">
            <label>Contact Person: *</label>
            <div class="form-control"></div>
        </div>
        <div class="form-group">
            <label>Contact Email: *</label>
            <div class="form-control"></div>
        </div>
        <div class="form-group">
            <label>Contact Phone Number: *</label>
            <div class="form-control"></div>
        </div>
        <div class="form-group">
            <label>Alternative Phone:</label>
            <div class="form-control"></div>
        </div>
    </div>

    <div class="form-section">
        <h3>4. AUTHORIZED REPRESENTATIVE</h3>
        <div class="form-group">
            <label>Representative Full Name: *</label>
            <div class="form-control"></div>
        </div>
        <div class="form-group">
            <label>Representative Designation:</label>
            <div class="form-control"></div>
        </div>
        <div class="form-group">
            <label>Representative Contact Email: *</label>
            <div class="form-control"></div>
        </div>
        <div class="form-group">
            <label>Representative Contact Phone: *</label>
            <div class="form-control"></div>
        </div>
        <div class="form-group">
            <label>Representative Address:</label>
            <div class="form-control" style="min-height: 60px;"></div>
        </div>
    </div>

    <div class="form-section">
        <h3>5. BUSINESS REFERENCES</h3>
        <div class="form-group">
            <label>Details of Business References (Provide at least 2):</label>
            <div class="form-control" style="min-height: 120px;">
                <p style="margin: 5px 0; font-size: 12px; color: #666;">
                    Reference 1: Company Name: _________________ Contact Person: _________________<br>
                    Phone: _________________ Email: _________________<br><br>
                    Reference 2: Company Name: _________________ Contact Person: _________________<br>
                    Phone: _________________ Email: _________________
                </p>
            </div>
        </div>
    </div>

    <div class="form-section">
        <h3>6. BRANCH/OUTLETS INFORMATION (Optional)</h3>
        <table>
            <thead>
                <tr><th>Branch Name</th><th>Branch Address</th></tr>
            </thead>
            <tbody>
                <tr><td style="height: 30px;"></td><td></td></tr>
                <tr><td style="height: 30px;"></td><td></td></tr>
                <tr><td style="height: 30px;"></td><td></td></tr>
            </tbody>
        </table>
    </div>

    <div class="form-section">
        <h3>7. DECLARATION AND SIGNATURE</h3>
        <p>I declare that the information provided in this form is true and accurate to the best of my knowledge.</p>
        <br>
        <table style="border: none;">
            <tr style="border: none;">
                <td style="border: none; width: 50%;">
                    <label>Signature:</label><br>
                    <div class="signature-box"></div>
                </td>
                <td style="border: none; width: 50%;">
                    <label>Date:</label><br>
                    <div class="form-control" style="width: 150px;"></div>
                </td>
            </tr>
        </table>
    </div>

    <div class="form-section">
        <h3>REQUIRED DOCUMENTS CHECKLIST</h3>
        <p>Please attach the following documents when submitting this form:</p>
        <div class="checkbox-item"><input type="checkbox"> CAC Certificate or Business Registration Documents</div>
        <div class="checkbox-item"><input type="checkbox"> Proof of Business Address (Utility bill, lease agreement, etc.)</div>
        <div class="checkbox-item"><input type="checkbox"> Additional Supporting Documents (if any)</div>
    </div>
</body>
</html>
"""
        
                
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