# Copyright (c) 2025, Business Registration App and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def after_install():
    """Setup function called after app installation"""
    setup_custom_roles()
    setup_workflow()
    setup_custom_fields()
    frappe.db.commit()

def setup_custom_roles():
    """Create custom roles for business registration"""
    roles = [
        {
            "role_name": "Business Registration User",
            "desk_access": 0,
            "home_page": "/business_form"
        },
        {
            "role_name": "Form Reviewer",
            "desk_access": 1,
            "home_page": "/business_dashboard"
        }
    ]
    
    for role_data in roles:
        if not frappe.db.exists("Role", role_data["role_name"]):
            role = frappe.new_doc("Role")
            role.role_name = role_data["role_name"]
            role.desk_access = role_data["desk_access"]
            role.home_page = role_data.get("home_page", "")
            role.insert(ignore_permissions=True)
            frappe.msgprint(_("Created role: {0}").format(role_data["role_name"]))

def setup_workflow():
    """Setup business registration workflow"""
    from business_registration.business_registration.doctype.business_registration_workflow.business_registration_workflow import setup_business_registration_workflow
    setup_business_registration_workflow()

def setup_custom_fields():
    """Setup custom fields for workflow tracking"""
    custom_fields = {
        "Business Registration": [
            {
                "fieldname": "workflow_history",
                "label": "Workflow History",
                "fieldtype": "Table",
                "options": "Business Registration Workflow History",
                "insert_after": "internal_notes",
                "read_only": 1,
                "hidden": 1
            }
        ]
    }
    
    create_custom_fields(custom_fields, update=True)

def create_workflow_history_doctype():
    """Create workflow history child table doctype"""
    if frappe.db.exists("DocType", "Business Registration Workflow History"):
        return
    
    doctype = frappe.new_doc("DocType")
    doctype.name = "Business Registration Workflow History"
    doctype.module = "Business Registration"
    doctype.istable = 1
    doctype.autoname = "hash"
    
    fields = [
        {
            "fieldname": "workflow_state",
            "label": "Workflow State",
            "fieldtype": "Data",
            "in_list_view": 1
        },
        {
            "fieldname": "action",
            "label": "Action",
            "fieldtype": "Data",
            "in_list_view": 1
        },
        {
            "fieldname": "user",
            "label": "User",
            "fieldtype": "Link",
            "options": "User",
            "in_list_view": 1
        },
        {
            "fieldname": "date",
            "label": "Date",
            "fieldtype": "Datetime",
            "in_list_view": 1
        }
    ]
    
    for field_data in fields:
        doctype.append("fields", field_data)
    
    doctype.insert(ignore_permissions=True)
    frappe.msgprint(_("Created DocType: Business Registration Workflow History"))
