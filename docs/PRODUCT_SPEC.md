# ScopeLock — Product Specification

## 1. Product thesis

Client project requirements rarely stay fixed. They evolve through normal conversation, often as innocent-sounding requests. Freelancers and small agencies can accidentally absorb additional implementation work without formally changing price or timeline.

**ScopeLock prevents commercial scope drift by continuously maintaining the authoritative project scope and translating client-request changes into explicit proposal revisions or change orders.**

The hackathon demo uses an AI automation consultancy (JVL) as the operating context, but the product should be business-SOP driven rather than hard-coded to one consultancy.

---

## 2. Primary user

A freelancer, consultant, or small agency owner who:

- receives project requirements through Gmail;
- prices work from an internal SOP/service catalog;
- manually creates proposals;
- negotiates requirements over email;
- is vulnerable to unnoticed scope expansion;
- wants automation but still wants approval before commercial messages are sent.

---

## 3. Jobs to be done

### Before a project is accepted

> When a client emails project requirements, create a commercially consistent proposal from my SOP without making me manually translate the request into line items.

### During negotiation / delivery

> When the client changes what they want, tell me whether it changes the agreed scope, quantify the impact immediately, and prepare the correct commercial revision.

### Trust

> Show me why ScopeLock made the decision and never send a commercial commitment without my approval.

---

## 4. Core value proposition

**Inbound client email → SOP-aligned proposal → approval → send → autonomous scope monitoring → commercial delta → approval → revision.**

No chat prompt is required to start or continue the workflow.

---

## 5. P0 user flows

### Flow A — Initial proposal

1. Client sends a requirements email.
2. Gmail event triggers ScopeLock.
3. System resolves the Gmail message/thread.
4. Agent determines that it is a project request.
5. Agent extracts normalized requirements.
6. Agent maps requirements to SOP service modules.
7. Deterministic pricing engine calculates:
   - line items;
   - price;
   - timeline;
   - dependencies/assumptions;
   - exclusions.
8. Proposal artifact is generated.
9. Project enters `AWAITING_USER_REVIEW`.
10. User reviews:
    - extracted requirements;
    - chosen service modules;
    - price/timeline;
    - evidence/reasoning;
    - generated proposal.
11. User approves or edits.
12. Gmail send action sends the proposal in the original thread.
13. Project enters `PROPOSAL_SENT` / `NEGOTIATING`.

### Flow B — No-scope-change communication

Client:
> Can you rename the dashboard title to "Operations Overview"?

ScopeLock:
- classifies as `NO_CHANGE` or `CLARIFICATION`;
- records the event;
- does not create a commercial revision.

### Flow C — Scope expansion before acceptance

Client:
> Can you also add LINE notifications and a manager approval flow?

ScopeLock:
- detects 2 scope additions;
- maps them to SOP modules;
- recalculates price/timeline immediately;
- adds them to the `ScopeBuffer`;
- waits to consolidate;
- generates Proposal Revision v2;
- asks user to approve;
- sends only after approval.

### Flow D — Scope expansion after acceptance

Accepted Proposal v2 becomes immutable.

Client:
> Can you add an OCR intake flow as well?

ScopeLock:
- classifies as `EXPANSION`;
- generates a commercial delta;
- adds it to pending changes;
- produces `Change Order #001`;
- user approves;
- client receives the change order;
- accepted change mutates canonical project scope.

---

## 6. Scope event taxonomy

Every relevant client message can produce zero or more scope events.

Allowed classifications:

- `NO_CHANGE`
- `CLARIFICATION`
- `AMBIGUOUS`
- `EXPANSION`
- `REDUCTION`
- `REPLACEMENT`

Do not call every change "scope creep." `ScopeEvent` is the neutral system primitive.

---

## 7. Scope Buffer

Commercially meaningful changes are detected immediately but not immediately sent.

### Rule

> **Calculate instantly. Communicate deliberately.**

Pending changes accumulate in a `ScopeBuffer`.

A buffer is finalized when one of these occurs:

1. **Quiet window:** no new client email in the thread for 20 minutes (configurable).
2. **Semantic closure:** message indicates closure, e.g. "that's everything", "please send the revised quote".
3. **Manual finalize:** user clicks `Finalize Revision`.

When finalized:
- before proposal acceptance → proposal revision;
- after proposal acceptance → change order.

If a new relevant client message arrives while the artifact is still unapproved, recalculate the draft rather than generating duplicate revisions.

---

## 8. Approval policy

### May happen autonomously
- read email;
- extract requirements;
- classify messages;
- map to SOP;
- calculate pricing/timeline;
- build proposal/revision;
- create Gmail draft;
- update internal state;
- run eval checks.

### Requires explicit user approval
- sending initial proposal;
- sending revised proposal;
- sending change order;
- applying a commercially significant ambiguous change.

For P0, do not let the agent send autonomous commercial emails.

---

## 9. Missing / ambiguous initial requirements

Do not hallucinate critical scope.

If the initial project request lacks required information:

- extract what is known;
- mark missing fields;
- classify proposal readiness;
- generate a clarification draft for the user to review.

For the golden hackathon demo, the initial client email will contain enough information to produce a proposal.

---

## 10. Proposal contents

P0 proposal:

1. Project title
2. Client
3. Problem / objective
4. Proposed solution
5. Scope / deliverables
6. Integrations
7. Assumptions
8. Explicit exclusions
9. Timeline
10. Pricing line items
11. Total price
12. Validity / change-control note

Every price-bearing line item should map back to an SOP rule.

---

## 11. Revision / change-order display

Show deltas, not only a new total.

Example:

- Existing project: USD 4,000 / 4 weeks
- + LINE integration: +USD 750 / +3 days
- + Manager approval workflow: +USD 750 / +2 days
- Revised: USD 5,500 / 5 weeks

The user/client should understand:
**new request → additional work → commercial impact.**

---

## 12. Success criteria

### Product success
- user does not manually prompt the agent to start;
- proposal is SOP-aligned;
- true scope expansions are caught;
- harmless changes are not over-flagged;
- user understands why classification/price was chosen;
- no commercial send happens without approval.

### Hackathon success
- autonomous Gmail trigger is visible;
- state changes are visible;
- Gemini is responsible for semantic understanding, not arbitrary pricing;
- Google Cloud execution is visible;
- evals demonstrate reliability;
- one end-to-end scenario is undeniable in <4 minutes.
