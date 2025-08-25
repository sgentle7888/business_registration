# Copyright (c) 2025, Business Registration App and contributors
# For license information, please see license.txt

# Copyright (c) 2025, Business Registration App and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import getdate, nowdate, add_to_date, now_datetime
import re
from frappe.utils.file_manager import get_file
from frappe.utils.pdf import get_pdf
from frappe.utils.jinja import render_template
import os
from .email_notifications import (
    send_reviewer_notification_email,
    send_approval_notification_email, 
    send_rejection_notification_email
)

class BusinessRegistration(Document):
    def validate(self):
        self.validate_email_format()
        self.validate_phone_numbers()
        self.validate_cac_number()
        self.validate_dates()
        self.validate_required_attachments()
        self.validate_annual_turnover()
        self.validate_branch_outlets()
        self.validate_business_references()
    
    def validate_email_format(self):
        """Validate email addresses"""
        email_fields = [
            'contact_email', 'representative_contact_email'
        ]
        
        for field in email_fields:
            email = getattr(self, field, None)
            if email and not frappe.utils.validate_email_address(email):
                frappe.throw(_("Invalid email address in {0}").format(self.meta.get_label(field)))
    
    def validate_phone_numbers(self):
        """Validate phone number formats"""
        phone_fields = [
            'contact_phone_number', 'alternative_phone', 'representative_contact_phone'
        ]
        
        for field in phone_fields:
            phone = getattr(self, field, None)
            if phone:
                # Remove all non-digit characters for validation
                phone_digits = re.sub(r'\D', '', str(phone))
                if len(phone_digits) < 10:
                    frappe.msgprint(_("Phone number in {0} seems too short").format(
                        self.meta.get_label(field)), alert=True)
                elif len(phone_digits) > 15:
                    frappe.throw(_("Phone number in {0} is too long").format(
                        self.meta.get_label(field)))
    
    def validate_cac_number(self):
        """Validate CAC number format and uniqueness"""
        if self.cac_number:
            # Check for duplicate CAC numbers
            existing_registration = frappe.db.exists("Business Registration", {
                "cac_number": self.cac_number,
                "name": ["!=", self.name or ""]
            })
            if existing_registration:
                frappe.throw(_("A business with CAC number {0} is already registered").format(self.cac_number))
            
            # Basic CAC number format validation (Nigerian format)
            cac_pattern = r'^(RC|BN|IT)\d+$'
            if not re.match(cac_pattern, self.cac_number.upper()):
                frappe.msgprint(_("CAC number format may be incorrect. Expected format: RC123456, BN123456, or IT123456"), alert=True)
    
    def validate_dates(self):
        """Validate date fields for logical consistency"""
        today = getdate()
        
        if self.date_of_incorporation:
            incorporation_date = getdate(self.date_of_incorporation)
            if incorporation_date > today:
                frappe.throw(_("Date of Incorporation cannot be in the future"))
            
            # Check if business is not too old (reasonable business age check)
            fifty_years_ago = add_to_date(today, years=-50)
            if incorporation_date < fifty_years_ago:
                frappe.msgprint(_("Please verify the Date of Incorporation - it appears to be very old"), alert=True)
    
    def validate_required_attachments(self):
        """Validate that required documents are attached"""
        if self.application_status in ["Submitted", "Under Review"]:
            if not self.business_registration_details:
                frappe.throw(_("Business Registration Details document is required"))
            
            if not self.proof_of_address:
                frappe.throw(_("Proof of Address document is required"))
    
    def validate_annual_turnover(self):
        """Validate annual turnover is reasonable"""
        if self.annual_turnover:
            try:
                turnover_value = float(self.annual_turnover)
                
                if turnover_value < 0:
                    frappe.throw(_("Annual Turnover cannot be negative"))
                
                # Warning for very high turnover (above 1 billion)
                if turnover_value > 1000000000:
                    frappe.msgprint(_("Please verify the Annual Turnover amount - it appears to be very high"), alert=True)
                    
                # Update the field with the validated numeric value
                self.annual_turnover = turnover_value
                
            except (ValueError, TypeError):
                frappe.throw(_("Annual Turnover must be a valid number"))

    
    def validate_branch_outlets(self):
        """Validate branch/outlets information"""
        if self.branch_outlets:
            branch_names = []
            for idx, branch in enumerate(self.branch_outlets):
                if not branch.branch_name or not branch.branch_address:
                    frappe.throw(_("Branch Name and Address are required for all branches (Row {0})").format(idx + 1))
                
                # Check for duplicate branch names
                if branch.branch_name in branch_names:
                    frappe.throw(_("Duplicate branch name found: {0} (Row {1})").format(branch.branch_name, idx + 1))
                branch_names.append(branch.branch_name)
    
    def validate_business_references(self):
        """Validate business references content"""
        if self.details_of_business_references:
            # Check if references contain email addresses (basic validation)
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            emails_found = re.findall(email_pattern, self.details_of_business_references)
            
            if len(emails_found) < 2:
                frappe.msgprint(_("Please ensure you provide at least 2 business references with contact details including email addresses"), alert=True)
    
    def before_save(self):
        """Handle status changes and timestamps"""
        self.update_status_timestamps()
        self.validate_status_transitions()
    
    def update_status_timestamps(self):
        """Update timestamps based on status changes"""
        if self.has_value_changed("application_status"):
            current_time = now_datetime()
            
            if self.application_status == "Submitted" and not self.submission_date:
                self.submission_date = current_time
            
            elif self.application_status == "Under Review" and not self.review_date:
                self.review_date = current_time
                self.reviewed_by = frappe.session.user
            
            elif self.application_status == "Approved" and not self.approval_date:
                self.approval_date = current_time
                self.reviewed_by = frappe.session.user
            
            elif self.application_status == "Rejected":
                self.reviewed_by = frappe.session.user
                if not self.rejection_reason:
                    frappe.throw(_("Rejection reason is required when rejecting an application"))
    
    def validate_status_transitions(self):
        """Validate allowed status transitions"""
        if self.has_value_changed("application_status"):
            old_status = self.get_db_value("application_status") or "Draft"
            new_status = self.application_status
            
            if old_status == new_status:
                return
            
            allowed_transitions = {
                "Draft": ["Submitted"],
                "Submitted": ["Under Review", "Rejected"],
                "Under Review": ["Approved", "Rejected"],
                "Approved": [],  # Final state
                "Rejected": ["Submitted"]  # Allow resubmission after rejection
            }
            
            if new_status not in allowed_transitions.get(old_status, []):
                frappe.throw(_("Invalid status transition from {0} to {1}").format(old_status, new_status))
    
    def after_save(self):
        """Handle post-save actions"""
        if self.has_value_changed("application_status"):
            self.send_status_notifications()
    
    def send_status_notifications(self):
        """Send email notifications based on status changes using templates"""
        try:
            if self.application_status == "Submitted":
                send_reviewer_notification_email(self)
            
            elif self.application_status == "Approved":
                send_approval_notification_email(self)
            
            elif self.application_status == "Rejected":
                send_rejection_notification_email(self)
                
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Business Registration Notification Error")
            frappe.msgprint(_("Application saved successfully, but there was an issue sending notifications"), alert=True)
    
def has_permission(doc, ptype, user):
    """Custom permission logic"""
    if not doc:
        return True
    
    # System Manager and Administrator have full access
    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        return True
    
    # Form Reviewers have full access
    user_roles = frappe.get_roles(user)
    if "Form Reviewer" in user_roles:
        return True
    
    # Business Registration Users can create and read their own applications
    if "Business Registration User" in user_roles:
        if ptype in ["create", "read"]:
            return True
        # Can write only if they created the document and it's not approved
        if ptype == "write" and doc.owner == user and doc.application_status not in ["Approved"]:
            return True
    
    # Guest users can create new applications
    if user == "Guest" and ptype == "create":
        return True
    
    return False

@frappe.whitelist()
def submit_application(name):
    """Submit application for review"""
    doc = frappe.get_doc("Business Registration", name)
    
    # Check permissions
    if not frappe.has_permission("Business Registration", "write", doc=doc):
        frappe.throw(_("You don't have permission to submit this application"))
    
    # Validate required fields
    if doc.application_status != "Draft":
        frappe.throw(_("Only draft applications can be submitted"))
    
    # Update status
    doc.application_status = "Submitted"
    doc.save()
    
    frappe.msgprint(_("Application submitted successfully. You will receive email notifications about the review status."))
    
    return {"status": "success", "message": "Application submitted successfully"}

@frappe.whitelist()
def approve_application(name, internal_notes=None):
    """Approve application (Form Reviewer only)"""
    if "Form Reviewer" not in frappe.get_roles():
        frappe.throw(_("You don't have permission to approve applications"))
    
    doc = frappe.get_doc("Business Registration", name)
    
    if doc.application_status not in ["Submitted", "Under Review"]:
        frappe.throw(_("Only submitted or under review applications can be approved"))
    
    doc.application_status = "Approved"
    if internal_notes:
        doc.internal_notes = internal_notes
    doc.save()
    
    frappe.msgprint(_("Application approved successfully. Congratulatory email sent to applicant."))
    
    return {"status": "success", "message": "Application approved successfully"}

@frappe.whitelist()
def reject_application(name, rejection_reason, internal_notes=None):
    """Reject application (Form Reviewer only)"""
    if "Form Reviewer" not in frappe.get_roles():
        frappe.throw(_("You don't have permission to reject applications"))
    
    if not rejection_reason:
        frappe.throw(_("Rejection reason is required"))
    
    doc = frappe.get_doc("Business Registration", name)
    
    if doc.application_status not in ["Submitted", "Under Review"]:
        frappe.throw(_("Only submitted or under review applications can be rejected"))
    
    doc.application_status = "Rejected"
    doc.rejection_reason = rejection_reason
    if internal_notes:
        doc.internal_notes = internal_notes
    doc.save()
    
    frappe.msgprint(_("Application rejected. Notification email sent to applicant."))
    
    return {"status": "success", "message": "Application rejected successfully"}

@frappe.whitelist()
def generate_registration_pdf(name):
    """Generate PDF for business registration"""
    doc = frappe.get_doc("Business Registration", name)
    
    # Check permissions
    if not frappe.has_permission("Business Registration", "read", doc=doc):
        frappe.throw(_("You don't have permission to access this document"))
    
    try:
        # Get the PDF template
        template_path = frappe.get_app_path("business_registration", "business_registration", "doctype", "business_registration", "templates", "business_registration_pdf.html")
        
        # Prepare context data
        context = {
            "doc": doc,
            "frappe": frappe,
            "format_currency": frappe.utils.fmt_money,
            "format_date": frappe.utils.formatdate,
            "get_fullname": frappe.utils.get_fullname
        }
        
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
        filename = f"Business_Registration_{doc.name}_{frappe.utils.today()}.pdf"
        frappe.local.response.filename = filename
        frappe.local.response.filecontent = pdf_content
        frappe.local.response.type = "download"
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "PDF Generation Error")
        frappe.throw(_("Error generating PDF: {0}").format(str(e)))

@frappe.whitelist()
def get_pdf_preview(name):
    """Get PDF preview URL for business registration"""
    doc = frappe.get_doc("Business Registration", name)
    
    # Check permissions
    if not frappe.has_permission("Business Registration", "read", doc=doc):
        frappe.throw(_("You don't have permission to access this document"))
    
    return {
        "pdf_url": f"/api/method/business_registration.business_registration.doctype.business_registration.business_registration.generate_registration_pdf?name={name}",
        "filename": f"Business_Registration_{doc.name}_{frappe.utils.today()}.pdf"
    }
