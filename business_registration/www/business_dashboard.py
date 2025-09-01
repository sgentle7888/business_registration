import frappe
from frappe import _
from frappe.utils import now_datetime

def get_context(context):
    """Get context for Business Registration dashboard"""

    # Check if user has Form Reviewer access
    if not has_reviewer_access():
        frappe.throw(_("You don't have permission to access this page"), frappe.PermissionError)

    # Get filter parameters from URL
    filters = get_filters_from_request()

    # Get business registration records based on filters
    registrations_data = get_registrations_with_details(filters)

    # Get filter options for dropdowns
    filter_options = get_filter_options()

    # Get summary statistics
    stats = get_dashboard_stats(filters)

    # Set context variables
    context.registrations = registrations_data
    context.filter_options = filter_options
    context.current_filters = filters
    context.stats = stats
    context.title = _("Business Registration Dashboard")
    context.no_cache = 1

    return context

def has_reviewer_access():
    """Check if current user has Form Reviewer access"""
    if frappe.session.user == "Administrator":
        return True

    user_roles = frappe.get_roles()
    reviewer_roles = ["Form Reviewer", "System Manager"]

    return any(role in user_roles for role in reviewer_roles)

def get_filters_from_request():
    """Extract filters from form request"""
    return {
        'status': frappe.form_dict.get('status', ''),
        'business_type': frappe.form_dict.get('business_type', ''),
        'state': frappe.form_dict.get('state', ''),
        'search': frappe.form_dict.get('search', ''),
        'date_from': frappe.form_dict.get('date_from', ''),
        'date_to': frappe.form_dict.get('date_to', ''),
        'reviewed_by': frappe.form_dict.get('reviewed_by', ''),
    }

def get_registrations_with_details(filters):
    """Get business registration records with filtering"""

    # Build base query
    conditions = []
    values = {}

    # Status filter
    if filters['status']:
        conditions.append("application_status = %(status)s")
        values['status'] = filters['status']

    # Business type filter
    if filters['business_type']:
        conditions.append("business_type = %(business_type)s")
        values['business_type'] = filters['business_type']

    # State filter
    if filters['state']:
        conditions.append("state = %(state)s")
        values['state'] = filters['state']

    # Date range filters
    if filters['date_from']:
        conditions.append("submission_date >= %(date_from)s")
        values['date_from'] = filters['date_from']

    if filters['date_to']:
        conditions.append("submission_date <= %(date_to)s")
        values['date_to'] = filters['date_to']

    # Reviewed by filter
    if filters['reviewed_by']:
        conditions.append("reviewed_by = %(reviewed_by)s")
        values['reviewed_by'] = filters['reviewed_by']

    # Search filter
    if filters['search']:
        search_condition = """(
            business_name LIKE %(search)s OR
            cac_number LIKE %(search)s OR
            contact_person LIKE %(search)s OR
            contact_email LIKE %(search)s OR
            representative_full_name LIKE %(search)s
        )"""
        conditions.append(search_condition)
        values['search'] = f"%{filters['search']}%"

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    # Main query
    query = f"""
        SELECT
            name,
            business_name,
            cac_number,
            business_type,
            contact_person,
            contact_email,
            contact_phone_number,
            representative_full_name,
            representative_contact_email,
            state,
            town_or_city,
            annual_turnover,
            application_status,
            submission_date,
            review_date,
            approval_date,
            reviewed_by,
            rejection_reason,
            creation,
            modified
        FROM `tabBusiness Registration`
        {where_clause}
        ORDER BY 
            CASE application_status 
                WHEN 'Submitted' THEN 1 
                WHEN 'Under Review' THEN 2 
                WHEN 'Rejected' THEN 3 
                WHEN 'Approved' THEN 4 
                ELSE 5 
            END,
            submission_date DESC
    """

    registrations = frappe.db.sql(query, values, as_dict=True)

    # Add additional computed fields
    for registration in registrations:
        registration['days_pending'] = get_days_pending(registration)
        registration['priority'] = get_priority_level(registration)

    return registrations

def get_days_pending(registration):
    """Calculate days since submission for pending applications"""
    if registration['application_status'] in ['Submitted', 'Under Review'] and registration['submission_date']:
        from frappe.utils import date_diff, nowdate
        return date_diff(nowdate(), registration['submission_date'])
    return 0

def get_priority_level(registration):
    """Determine priority level based on days pending and business type"""
    days = get_days_pending(registration)
    if days > 7:
        return 'High'
    elif days > 3:
        return 'Medium'
    else:
        return 'Normal'

def get_filter_options():
    """Get options for filter dropdowns"""
    
    # Get unique business types
    business_types = frappe.get_all("Business Registration", 
        fields=["DISTINCT business_type as name"], 
        filters={"business_type": ["!=", ""]})
    
    # Get unique states
    states = frappe.get_all("Business Registration", 
        fields=["DISTINCT state as name"], 
        filters={"state": ["!=", ""]})
    
    # Get reviewers
    reviewers = frappe.get_all("Has Role", 
        filters={"role": "Form Reviewer", "parenttype": "User"},
        fields=["parent as user"])
    
    reviewer_list = []
    for reviewer in reviewers:
        user_name = frappe.get_value("User", reviewer.user, "full_name") or reviewer.user
        reviewer_list.append({"name": reviewer.user, "full_name": user_name})

    return {
        'business_types': business_types,
        'states': states,
        'statuses': [
            {'name': 'All Status', 'value': ''},
            {'name': 'Draft', 'value': 'Draft'},
            {'name': 'Submitted', 'value': 'Submitted'},
            {'name': 'Under Review', 'value': 'Under Review'},
            {'name': 'Approved', 'value': 'Approved'},
            {'name': 'Rejected', 'value': 'Rejected'}
        ],
        'reviewers': reviewer_list
    }

def get_dashboard_stats(filters):
    """Get dashboard summary statistics"""
    
    # Total applications
    total_query = "SELECT COUNT(*) as count FROM `tabBusiness Registration`"
    total_applications = frappe.db.sql(total_query)[0][0]

    # Pending applications (Submitted + Under Review)
    pending_query = """
        SELECT COUNT(*) as count 
        FROM `tabBusiness Registration` 
        WHERE application_status IN ('Submitted', 'Under Review')
    """
    pending_applications = frappe.db.sql(pending_query)[0][0]

    # Approved applications
    approved_query = """
        SELECT COUNT(*) as count 
        FROM `tabBusiness Registration` 
        WHERE application_status = 'Approved'
    """
    approved_applications = frappe.db.sql(approved_query)[0][0]

    # Applications this month
    this_month_query = """
        SELECT COUNT(*) as count
        FROM `tabBusiness Registration`
        WHERE MONTH(submission_date) = MONTH(CURDATE())
        AND YEAR(submission_date) = YEAR(CURDATE())
        AND submission_date IS NOT NULL
    """
    this_month_applications = frappe.db.sql(this_month_query)[0][0]

    # High priority applications (pending > 7 days)
    high_priority_query = """
        SELECT COUNT(*) as count
        FROM `tabBusiness Registration`
        WHERE application_status IN ('Submitted', 'Under Review')
        AND DATEDIFF(CURDATE(), submission_date) > 7
    """
    high_priority_applications = frappe.db.sql(high_priority_query)[0][0]

    return {
        'total_applications': total_applications,
        'pending_applications': pending_applications,
        'approved_applications': approved_applications,
        'this_month_applications': this_month_applications,
        'high_priority_applications': high_priority_applications,
    }

@frappe.whitelist()
def export_registrations():
    """Export business registration data to Excel"""
    if not has_reviewer_access():
        frappe.throw(_("Access denied"), frappe.PermissionError)

    filters = get_filters_from_request()
    registrations = get_registrations_with_details(filters)

    export_data = []
    for reg in registrations:
        export_data.append({
            'Business Name': reg['business_name'],
            'CAC Number': reg['cac_number'],
            'Business Type': reg['business_type'] or '',
            'Contact Person': reg['contact_person'],
            'Contact Email': reg['contact_email'],
            'Contact Phone': reg['contact_phone_number'] or '',
            'State': reg['state'] or '',
            'City': reg['town_or_city'] or '',
            'Annual Turnover': reg['annual_turnover'] or 0,
            'Application Status': reg['application_status'],
            'Submission Date': reg['submission_date'] or '',
            'Review Date': reg['review_date'] or '',
            'Approval Date': reg['approval_date'] or '',
            'Reviewed By': reg['reviewed_by'] or '',
            'Days Pending': reg['days_pending'],
            'Priority': reg['priority']
        })

    return export_data

@frappe.whitelist()
def get_registration_details(registration_id):
    """Get detailed business registration information"""
    try:
        # Check permissions
        if not has_reviewer_access():
            frappe.throw(_("Access denied"), frappe.PermissionError)

        # Validate registration_id parameter
        if not registration_id or registration_id.strip() == "":
            frappe.throw(_("Registration ID is required"))

        registration_id = registration_id.strip()
        
        # Check if registration exists
        if not frappe.db.exists("Business Registration", registration_id):
            frappe.throw(_("Business Registration with ID '{0}' does not exist").format(registration_id))

        # Get the registration document
        registration_doc = frappe.get_doc("Business Registration", registration_id)
        registration_details = registration_doc.as_dict()

        # Add computed fields
        registration_details['days_pending'] = get_days_pending(registration_details)
        registration_details['priority'] = get_priority_level(registration_details)

        # Get branch/outlets data
        if registration_doc.branch_outlets:
            registration_details['branch_outlets_list'] = [branch.as_dict() for branch in registration_doc.branch_outlets]
        else:
            registration_details['branch_outlets_list'] = []

        return registration_details

    except frappe.DoesNotExistError as e:
        frappe.log_error(f"Registration not found: {registration_id}", "Get Registration Details Error")
        frappe.throw(_("Registration not found: {0}").format(str(e)))
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Registration Details Error")
        frappe.throw(_("An error occurred while fetching registration details: {0}").format(str(e)))

@frappe.whitelist()
def update_application_status(registration_id, new_status, rejection_reason=None, internal_notes=None):
    """Update application status with proper validation and workflow handling."""
    try:
        if not has_reviewer_access():
            frappe.throw(_("Access denied"), frappe.PermissionError)

        doc = frappe.get_doc("Business Registration", registration_id)
        
        # Validate status transition
        if new_status == "Rejected" and not rejection_reason:
            frappe.throw(_("Rejection reason is required when rejecting an application."))

        # Update fields before saving
        doc.application_status = new_status
        if new_status == "Approved":
            doc.approval_date = now_datetime()
        elif new_status == "Rejected":
            doc.rejection_reason = rejection_reason

        if internal_notes:
            doc.internal_notes = internal_notes
            
        doc.reviewed_by = frappe.session.user

        # Save the document to trigger validations and workflow hooks
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        
        return {"status": "success", "message": f"Application status successfully updated to {new_status}."}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Application Status Error")
        frappe.response.http_status_code = 400
        return {"error": str(e)}
