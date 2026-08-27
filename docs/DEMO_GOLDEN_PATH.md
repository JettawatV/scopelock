# ScopeLock — Golden Demo Scenario

## Goal

Demonstrate the entire Taskmaster story in one scenario:

**event -> autonomous reasoning -> real artifact -> user approval -> external action -> later scope drift -> commercial protection**

---

## Demo business

AI automation consultancy using a structured service SOP.

All prices below are demo values and must match the final demo SOP.

---

## Scene 1 — Client email arrives

Client sends:

> Subject: Automation project requirements
>
> Hi,
>
> We want to automate our incoming customer requests. Requests currently arrive in a shared Gmail inbox and the team copies them into Google Sheets manually.
>
> We'd like the system to classify each request, store the structured data, and show the team a simple operations dashboard. We also need email notifications when a request needs manual review.
>
> Please send us a proposal with price and timeline.
>
> Thanks.

Do not open ScopeLock first.

Show:
- Gmail arrival;
- Cloud event/log;
- ScopeLock project appears automatically.

---

## Scene 2 — Proposal generated

ScopeLock displays:

- extracted requirements;
- mapped SOP modules;
- price line items;
- timeline;
- assumptions/exclusions;
- evidence;
- generated proposal.

Show that Gemini chose the modules, but deterministic SOP logic produced price/timeline.

User clicks:
**Approve & Send**

Show Gmail thread receiving/sending the proposal.

---

## Scene 3 — Harmless follow-up

Client replies:

> Could you call the dashboard "Operations Overview" instead?

ScopeLock:
- `NO_CHANGE`;
- no commercial delta.

This proves it is not keyword-triggered.

---

## Scene 4 — Real expansion

Shortly after, client replies:

> One more thing — can managers also approve requests from LINE and receive LINE alerts?

ScopeLock immediately:
- detects material scope addition;
- maps LINE module(s);
- calculates price delta;
- calculates timeline delta;
- adds to Scope Buffer.

Dashboard headline example:

> **Scope expansion detected — +THB 27,000 / +5 days**

Do not instantly send.

---

## Scene 5 — Consolidation

Option A for demo:
Client sends:

> That's everything. Please send the revised proposal.

Gemini detects semantic closure and finalizes the buffer immediately.

This is better for a demo than waiting 20 minutes.

ScopeLock prepares:
- Proposal Revision v2 (if original not yet accepted), or
- Change Order #001 (if demo marks proposal accepted).

User clicks:
**Approve & Send**

Show:
- revised artifact;
- same Gmail thread;
- state updated;
- audit log.

---

## Scene 6 — Proof / eval

Quickly show:
- ScopeEvent history;
- evidence for NO_CHANGE vs expansion;
- current canonical/proposed scope;
- eval dashboard;
- approval-gate violations = 0;
- Google Cloud Run logs/trace.

---

## One-line pitch

**ScopeLock turns client email into an SOP-aligned proposal automatically, then keeps watching the conversation so extra work never quietly becomes free work.**

---

## What judges should understand without explanation

1. The workflow starts itself.
2. Gemini understands messy client language.
3. Price is not hallucinated.
4. Scope changes are stateful across a conversation.
5. Commercial changes are consolidated intelligently.
6. Human approval gates risky external actions.
7. The system can be evaluated.
8. It runs on Google Cloud.
