import frappe
from frappe import _
from frappe.utils import get_url, now_datetime
import os

def send_reviewer_notification_email(business_registration):
    """Send notification to form reviewers using template"""
    try:
        # Get all users with Form Reviewer role
        reviewers = frappe.get_all("Has Role", 
            filters={"role": "Form Reviewer", "parenttype": "User"},
            fields=["parent as user"]
        )
        
        if not reviewers:
            frappe.log_error("No Form Reviewers found", "Business Registration Notification")
            return False
        
        reviewer_emails = []
        for reviewer in reviewers:
            user_email = frappe.get_value("User", reviewer.user, "email")
            if user_email:
                reviewer_emails.append(user_email)
        
        if not reviewer_emails:
            frappe.log_error("No reviewer emails found", "Business Registration Notification")
            return False
        
        # Prepare template context
        context = {
            'business_name': business_registration.business_name,
            'cac_number': business_registration.cac_number,
            'business_type': business_registration.business_type,
            'contact_person': business_registration.contact_person,
            'contact_email': business_registration.contact_email,
            'contact_phone_number': business_registration.contact_phone_number,
            'town_or_city': business_registration.town_or_city,
            'state': business_registration.state,
            'submission_date': frappe.format(business_registration.submission_date, "datetime"),
            'application_id': business_registration.name,
            'dashboard_url': get_url() + '/business_dashboard',
            'priority': get_application_priority(business_registration)
        }
        
        # Render email template
        template_path = get_template_path('reviewer_notification.html')
        message = frappe.render_template(template_path, context)
        
        subject = _("New Business Registration Application - {0}").format(business_registration.business_name)
        
        frappe.sendmail(
            recipients=reviewer_emails,
            subject=subject,
            message=message,
            reference_doctype=business_registration.doctype,
            reference_name=business_registration.name,
            now=True
        )
        
        # Log notification
        log_email_notification(business_registration.name, "reviewer_notification", reviewer_emails)
        
        return True
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Reviewer Notification Email Error")
        return False

def send_approval_notification_email(business_registration):
    """Send approval notification using template"""
    try:
        if not business_registration.contact_email:
            return False
        
        # Get company logo if available
        company_logo = get_company_logo()
        
        # Prepare template context
        context = {
            'contact_person': business_registration.contact_person,
            'business_name': business_registration.business_name,
            'cac_number': business_registration.cac_number,
            'business_type': business_registration.business_type,
            'approval_date': frappe.format(business_registration.approval_date, "datetime"),
            'application_id': business_registration.name,
            'annual_turnover': business_registration.annual_turnover,
            'company_logo': company_logo,
            'company_name': get_company_name()
        }
        
        # Render email template
        template_path = get_template_path('approval_notification.html')
        message = frappe.render_template(template_path, context)
        
        subject = _("Congratulations! Your Business Registration Application has been Approved")
        
        recipients = [business_registration.contact_email]
        
        # Also send to representative if different email
        if (business_registration.representative_contact_email and 
            business_registration.representative_contact_email != business_registration.contact_email):
            recipients.append(business_registration.representative_contact_email)
        
        frappe.sendmail(
            recipients=recipients,
            subject=subject,
            message=message,
            reference_doctype=business_registration.doctype,
            reference_name=business_registration.name,
            now=True
        )
        
        # Log notification
        log_email_notification(business_registration.name, "approval_notification", recipients)
        
        return True
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Approval Notification Email Error")
        return False

def send_rejection_notification_email(business_registration):
    """Send rejection notification using template"""
    try:
        if not business_registration.contact_email:
            return False
        
        # Prepare template context
        context = {
            'contact_person': business_registration.contact_person,
            'business_name': business_registration.business_name,
            'cac_number': business_registration.cac_number,
            'application_id': business_registration.name,
            'review_date': frappe.format(business_registration.review_date or now_datetime(), "datetime"),
            'rejection_reason': business_registration.rejection_reason,
            'form_url': get_url() + f'/business_form?registration_id={business_registration.name}',
            'company_name': get_company_name()
        }
        
        # Render email template
        template_path = get_template_path('rejection_notification.html')
        message = frappe.render_template(template_path, context)
        
        subject = _("Business Registration Application Update Required - {0}").format(business_registration.business_name)
        
        recipients = [business_registration.contact_email]
        
        # Also send to representative if different email
        if (business_registration.representative_contact_email and 
            business_registration.representative_contact_email != business_registration.contact_email):
            recipients.append(business_registration.representative_contact_email)
        
        frappe.sendmail(
            recipients=recipients,
            subject=subject,
            message=message,
            reference_doctype=business_registration.doctype,
            reference_name=business_registration.name,
            now=True
        )
        
        # Log notification
        log_email_notification(business_registration.name, "rejection_notification", recipients)
        
        return True
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Rejection Notification Email Error")
        return False

def get_template_path(template_name):
    """Get the full path to email template"""
    return f"business_registration/business_registration/templates/emails/{template_name}"

def get_company_logo():
    """Get company logo URL"""
    try:
        logo_url = frappe.get_value("Website Settings", None, "banner_image")
        if logo_url:
            return get_url() + logo_url
    except:
        pass
    return None

def get_company_name():
    """Get company name from settings"""
    try:
        return frappe.get_value("Website Settings", None, "title_prefix") or "Business Registration System"
    except:
        return "Business Registration System"

def get_application_priority(business_registration):
    """Calculate application priority based on submission date"""
    if not business_registration.submission_date:
        return "Normal"
    
    from frappe.utils import date_diff, nowdate
    days_pending = date_diff(nowdate(), business_registration.submission_date)
    
    if days_pending > 7:
        return "High"
    elif days_pending > 3:
        return "Medium"
    else:
        return "Normal"

def log_email_notification(registration_id, notification_type, recipients):
    """Log email notification for tracking"""
    try:
        log_entry = frappe.new_doc("Email Notification Log")
        log_entry.reference_doctype = "Business Registration"
        log_entry.reference_name = registration_id
        log_entry.notification_type = notification_type
        log_entry.recipients = ", ".join(recipients)
        log_entry.sent_at = now_datetime()
        log_entry.status = "Sent"
        log_entry.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(f"Failed to log email notification: {str(e)}", "Email Notification Log Error")

@frappe.whitelist()
def send_bulk_notifications(filters=None, notification_type="reminder"):
    """Send bulk notifications to businesses based on filters"""
    try:
        # Check permissions
        if not frappe.has_permission("Business Registration", "read"):
            frappe.throw(_("Insufficient permissions"))
        
        # Build filters
        registration_filters = {}
        if filters:
            filter_dict = frappe.parse_json(filters) if isinstance(filters, str) else filters
            
            if filter_dict.get("status"):
                registration_filters["application_status"] = filter_dict["status"]
            if filter_dict.get("business_type"):
                registration_filters["business_type"] = filter_dict["business_type"]
            if filter_dict.get("state"):
                registration_filters["state"] = filter_dict["state"]
        
        # Get registrations
        registrations = frappe.get_all("Business Registration",
            filters=registration_filters,
            fields=["name", "business_name", "contact_email", "application_status"]
        )
        
        if not registrations:
            return {"status": "error", "message": "No registrations found matching the criteria"}
        
        sent_count = 0
        failed_count = 0
        
        for registration in registrations:
            try:
                if notification_type == "reminder" and registration.application_status == "Draft":
                    # Send reminder to complete application
                    send_completion_reminder(registration.name)
                    sent_count += 1
                elif notification_type == "status_update":
                    # Send status update
                    send_status_update_notification(registration.name)
                    sent_count += 1
            except Exception as e:
                failed_count += 1
                frappe.log_error(f"Failed to send notification to {registration.name}: {str(e)}")
        
        return {
            "status": "success",
            "message": f"Sent {sent_count} notifications successfully. {failed_count} failed.",
            "sent": sent_count,
            "failed": failed_count
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Bulk Notification Error")
        return {"status": "error", "message": str(e)}

def send_completion_reminder(registration_id):
    """Send reminder to complete draft application"""
    try:
        business_registration = frappe.get_doc("Business Registration", registration_id)
        
        if not business_registration.contact_email:
            return False
        
        subject = _("Complete Your Business Registration Application - {0}").format(business_registration.business_name)
        
        message = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2c5aa0;">Complete Your Business Registration</h2>
            
            <p>Dear {business_registration.contact_person or 'Applicant'},</p>
            
            <p>We noticed that your business registration application for <strong>{business_registration.business_name}</strong> is still in draft status.</p>
            
            <p>To proceed with the registration process, please complete and submit your application.</p>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{get_url()}/business_form?registration_id={business_registration.name}" 
                   style="background-color: #2c5aa0; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: 600;">
                   Complete Application
                </a>
            </div>
            
            <p>If you have any questions or need assistance, please contact our support team.</p>
            
            <p>Best regards,<br>Business Registration Team</p>
        </div>
        """
        
        frappe.sendmail(
            recipients=[business_registration.contact_email],
            subject=subject,
            message=message,
            reference_doctype=business_registration.doctype,
            reference_name=business_registration.name
        )
        
        return True
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Completion Reminder Error")
        return False
