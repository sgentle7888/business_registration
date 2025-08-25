# Copyright (c) 2025, Godwin Ariwodo and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.workflow.doctype.workflow.workflow import get_workflow_name
from frappe import _

class BusinessRegistrationWorkflow(Document):
    def validate(self):
        self.validate_workflow_states()
        self.validate_workflow_transitions()
    
    def validate_workflow_states(self):
        """Validate workflow states are properly configured"""
        if not self.states:
            frappe.throw(_("At least one workflow state is required"))
        
        state_names = [state.state for state in self.states]
        required_states = ["Draft", "Submitted", "Under Review", "Approved", "Rejected"]
        
        for required_state in required_states:
            if required_state not in state_names:
                frappe.throw(_("Required workflow state '{0}' is missing").format(required_state))
    
    def validate_workflow_transitions(self):
        """Validate workflow transitions are properly configured"""
        if not self.transitions:
            frappe.throw(_("At least one workflow transition is required"))
        
        # Validate that all transitions reference valid states
        state_names = [state.state for state in self.states]
        
        for transition in self.transitions:
            if transition.state not in state_names:
                frappe.throw(_("Transition references invalid state: {0}").format(transition.state))
            
            if transition.next_state not in state_names:
                frappe.throw(_("Transition references invalid next state: {0}").format(transition.next_state))

def setup_business_registration_workflow():
    """Setup the default business registration workflow"""
    workflow_name = "Business Registration Approval"
    
    # Check if workflow already exists
    if frappe.db.exists("Workflow", workflow_name):
        return
    
    # Create workflow document
    workflow = frappe.new_doc("Workflow")
    workflow.workflow_name = workflow_name
    workflow.document_type = "Business Registration"
    workflow.workflow_state_field = "application_status"
    workflow.is_active = 1
    workflow.send_email_alerts = 1
    
    # Define workflow states
    states = [
        {
            "state": "Draft",
            "doc_status": "0",
            "allow_edit": "Business Registration User",
            "style": "Secondary"
        },
        {
            "state": "Submitted",
            "doc_status": "1",
            "allow_edit": "Form Reviewer",
            "style": "Info"
        },
        {
            "state": "Under Review",
            "doc_status": "1",
            "allow_edit": "Form Reviewer",
            "style": "Warning"
        },
        {
            "state": "Approved",
            "doc_status": "1",
            "allow_edit": "Form Reviewer",
            "style": "Success"
        },
        {
            "state": "Rejected",
            "doc_status": "1",
            "allow_edit": "Form Reviewer",
            "style": "Danger"
        }
    ]
    
    # Define workflow transitions
    transitions = [
        {
            "state": "Draft",
            "action": "Submit",
            "next_state": "Submitted",
            "allowed": "Business Registration User",
            "condition": ""
        },
        {
            "state": "Submitted",
            "action": "Start Review",
            "next_state": "Under Review",
            "allowed": "Form Reviewer",
            "condition": ""
        },
        {
            "state": "Submitted",
            "action": "Approve",
            "next_state": "Approved",
            "allowed": "Form Reviewer",
            "condition": ""
        },
        {
            "state": "Submitted",
            "action": "Reject",
            "next_state": "Rejected",
            "allowed": "Form Reviewer",
            "condition": ""
        },
        {
            "state": "Under Review",
            "action": "Approve",
            "next_state": "Approved",
            "allowed": "Form Reviewer",
            "condition": ""
        },
        {
            "state": "Under Review",
            "action": "Reject",
            "next_state": "Rejected",
            "allowed": "Form Reviewer",
            "condition": ""
        },
        {
            "state": "Rejected",
            "action": "Resubmit",
            "next_state": "Submitted",
            "allowed": "Business Registration User",
            "condition": ""
        }
    ]
    
    # Add states to workflow
    for state_data in states:
        workflow.append("states", state_data)
    
    # Add transitions to workflow
    for transition_data in transitions:
        workflow.append("transitions", transition_data)
    
    # Save workflow
    workflow.insert()
    frappe.db.commit()
    
    frappe.msgprint(_("Business Registration Workflow created successfully"))

@frappe.whitelist()
def get_workflow_actions(docname):
    """Get available workflow actions for a business registration"""
    doc = frappe.get_doc("Business Registration", docname)
    
    # Check if user has permission to perform workflow actions
    if not frappe.has_permission("Business Registration", "write", doc=doc):
        return []
    
    workflow_name = get_workflow_name("Business Registration")
    if not workflow_name:
        return []
    
    workflow = frappe.get_doc("Workflow", workflow_name)
    current_state = doc.application_status or "Draft"
    
    # Get available transitions from current state
    available_actions = []
    user_roles = frappe.get_roles()
    
    for transition in workflow.transitions:
        if transition.state == current_state:
            # Check if user has required role
            if transition.allowed in user_roles or "System Manager" in user_roles:
                available_actions.append({
                    "action": transition.action,
                    "next_state": transition.next_state,
                    "allowed": transition.allowed
                })
    
    return available_actions

@frappe.whitelist()
def execute_workflow_action(docname, action):
    """Execute a workflow action on a business registration"""
    doc = frappe.get_doc("Business Registration", docname)
    
    # Check permissions
    if not frappe.has_permission("Business Registration", "write", doc=doc):
        frappe.throw(_("You don't have permission to perform this action"))
    
    # Get workflow
    workflow_name = get_workflow_name("Business Registration")
    if not workflow_name:
        frappe.throw(_("No workflow found for Business Registration"))
    
    workflow = frappe.get_doc("Workflow", workflow_name)
    current_state = doc.application_status or "Draft"
    
    # Find the transition
    transition = None
    user_roles = frappe.get_roles()
    
    for t in workflow.transitions:
        if t.state == current_state and t.action == action:
            if t.allowed in user_roles or "System Manager" in user_roles:
                transition = t
                break
    
    if not transition:
        frappe.throw(_("Action '{0}' is not allowed in current state '{1}'").format(action, current_state))
    
    # Update document state
    old_status = doc.application_status
    doc.application_status = transition.next_state
    
    # Add workflow history
    doc.append("workflow_history", {
        "workflow_state": transition.next_state,
        "action": action,
        "user": frappe.session.user,
        "date": frappe.utils.now()
    })
    
    # Save document (this will trigger validation and notifications)
    doc.save()
    
    frappe.msgprint(_("Status changed from '{0}' to '{1}'").format(old_status, transition.next_state))
    
    return {
        "status": "success",
        "message": f"Status changed from '{old_status}' to '{transition.next_state}'",
        "new_state": transition.next_state
    }

