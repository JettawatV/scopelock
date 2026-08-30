# Proposal — Customer Request Intake and Dashboard Automation

Client: Golden Path Client <client@example.com>

## Objective

Automate customer-request intake, classification, structured storage, operations visibility, and manual-review alerts.

## Requirements

- REQ-01: Automate customer request classification and structured storage.
- REQ-02: Read requests from one shared Gmail inbox.
- REQ-03: Show structured request records in a simple operations dashboard.
- REQ-04: Email the team when a request needs manual review.

## Scope and deterministic pricing

- core_workflow_automation x1: USD 4,000
- email_intake x1: USD 500
- operations_dashboard x1: USD 750
- email_notifications x1: USD 400

**Total: USD 5,650**

**Timeline: 5 days**

## Assumptions

- One shared Gmail inbox is the only intake channel.
- The dashboard uses standard status tables, charts, and filters.

## Exclusions

- Multi-mailbox routing is excluded.
- Advanced BI modeling and custom mobile dashboards are excluded.

## Evidence

- [gmail:gmail-golden-001] Please send us a proposal with price and timeline.
- [gmail:gmail-golden-001] classify each request, store the structured data
- [sop:core_workflow_automation] Automate one defined business workflow from intake through structured output.
- [gmail:gmail-golden-001] Requests currently arrive in a shared Gmail inbox
- [sop:email_intake] Read and process inbound Gmail messages for the workflow.
- [gmail:gmail-golden-001] show the team a simple operations dashboard
- [sop:operations_dashboard] Simple dashboard for structured workflow records and statuses.
- [gmail:gmail-golden-001] email notifications when a request needs manual review
- [sop:email_notifications] Email alerts for predefined workflow events.

## Change control

This proposal is valid for 14 days. Any material scope
change requires a reviewed proposal revision or change order.

---
SOP version: jvl-demo-v1  
Source scope version: 1 (scope-abea35d39e252a1bb24b2cd3)  
Proposal data SHA-256: 1f6a5ba1de53229d39f8f52ca3380f1f5fde4962e6b0e20a1e60ae359b28583c
