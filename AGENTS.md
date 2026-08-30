# ScopeLock — Instructions for Coding Agents

## Read this first

You are building **ScopeLock**, a new project for the **All Things Agentic Hackathon**.

Before changing architecture or implementing features, read these files in order:

1. `docs/PRODUCT_SPEC.md`
2. `docs/ARCHITECTURE.md`
3. `docs/DOMAIN_MODEL.md`
4. `docs/AGENT_DESIGN.md`
5. `docs/JVL_SOP_SPEC.md`
6. `docs/EVAL_PLAN.md`
7. `docs/IMPLEMENTATION_PLAN.md`
8. `docs/HACKATHON_REQUIREMENTS.md`
9. `docs/DEMO_GOLDEN_PATH.md`

The user will also provide the official hackathon Rules / Overview / Submission Checklist. **Those official files override this context pack if there is any conflict.**

---

## Product in one sentence

**ScopeLock is an event-driven agent that turns an inbound client email into an SOP-aligned proposal for user approval, then continuously monitors the Gmail thread for scope changes and prepares price/timeline revisions without prompting.**

## Core product principle

> **Calculate instantly. Communicate deliberately.**

The system may autonomously read, analyze, classify, price, calculate timeline impact, generate proposal revisions, and prepare email drafts.

The system **must never send an initial proposal or commercial scope revision without explicit user approval**.

---

## Frozen MVP

Build only this loop:

1. Client sends project requirements by Gmail.
2. Gmail push notification wakes ScopeLock.
3. ScopeLock reads the message/thread.
4. Gemini extracts requirements and maps them to the business SOP.
5. Deterministic code calculates price and timeline from the SOP.
6. ScopeLock generates a proposal.
7. User reviews and approves in the dashboard.
8. ScopeLock sends the approved proposal in the same Gmail thread.
9. Future client messages are analyzed automatically.
10. Each message becomes a `ScopeEvent`.
11. Scope expansions/reductions/replacements are buffered.
12. Price/timeline impact is recalculated immediately.
13. Related changes are consolidated after a quiet window, explicit client closure, or manual finalize.
14. User reviews the revision/change order.
15. ScopeLock sends only after user approval.
16. Accepted changes update the canonical project scope.
17. Every important decision/action is logged and evaluable.

---

## Do not build unless all P0 work is stable

- Slack, Teams, WhatsApp, Calendar, Drive or CRM integrations
- payment or billing
- multi-tenant SaaS
- complex authentication/roles
- vector database / RAG stack
- autonomous outbound prospecting
- arbitrary LLM-generated pricing
- 10+ agents
- "Scope Court"
- fine-tuning
- self-modifying production prompts
- client portal
- full project-management suite
- PDF attachment ingestion (P1 only)
- fancy analytics unrelated to evals
- automatic commercial sends without approval

When tempted to add a feature, ask: **Does this improve the 4-minute judging demo or a scored rubric item?** If not, do not add it.

---

## Frozen technology choices

### AI / agents
- Google Agent Development Kit (ADK), Python
- Gemini `gemini-3.5-flash` via Vertex AI
- Structured outputs / typed Pydantic models for all business-critical LLM results
- ADK evals / trajectory evaluation where practical

### Backend
- Python 3.13
- FastAPI-compatible HTTP service around the ADK application where custom endpoints are needed
- Pydantic v2
- Google Cloud Run

### Eventing
- Gmail API `users.watch`
- Google Cloud Pub/Sub
- Gmail History API to resolve mailbox changes from `historyId`

### State
- Google Cloud Firestore
- Cloud Storage only if needed for generated proposal PDFs/artifacts

### Frontend
- Vite 7.3.x with React and TypeScript
- TypeScript
- Tailwind CSS
- Minimal review/dashboard UI

### Email
- Gmail API only
- OAuth scopes should be least-privilege: prefer Gmail read-only + compose/send capabilities rather than full mailbox access
- Initial hackathon demo may use a dedicated Gmail account

### Proposal artifact
- Generate a clean proposal PDF with a simple deterministic template (ReportLab is acceptable)
- Do not spend a day building a document-layout engine

---

## Engineering rules

1. **Probabilistic understanding; deterministic commerce.**
   - Gemini decides what the client is asking for and which SOP modules apply.
   - Normal code calculates price, duration, totals, deltas, state transitions, quiet-window logic, and approval rules.

2. **Immutable accepted baselines.**
   - Never silently overwrite an accepted proposal.
   - Before acceptance: create proposal revisions.
   - After acceptance: create change orders.

3. **Evidence-backed classifications.**
   - Scope decisions must cite the current baseline requirement(s), relevant client message, and SOP rule where applicable.

4. **Idempotent external actions.**
   - Pub/Sub redelivery or repeated webhooks must never cause duplicate proposals or duplicate emails.

5. **Human approval for commercial communication.**
   - Send tools are only callable after the corresponding artifact is in an approved state.

6. **Explicit state machines.**
   - Do not infer workflow state from prose.

7. **Observability from day one.**
   - Persist `AgentRun`, `ScopeDecision`, `ToolAction`, and `EvalResult` records.
   - Add correlation IDs.

8. **Golden path before edge cases.**
   - The primary demo must work reliably before adding P1 features.

---

## Definition of done for MVP

ScopeLock is MVP-complete when this can be shown end-to-end:

- A client email arrives without the user prompting ScopeLock.
- Cloud event wakes the backend.
- A proposal is generated from the requirements + SOP.
- Price/timeline can be traced to deterministic SOP rules.
- User approves.
- Email is sent in the same Gmail thread.
- Client replies with one harmless clarification and one true scope expansion.
- ScopeLock correctly distinguishes them.
- ScopeLock recalculates commercial impact.
- It consolidates the change into one revision/change order.
- User approves.
- Revision is sent.
- Firestore/UI shows canonical scope, event history, audit trail, and eval evidence.
- Cloud Run / Google Cloud execution is visible for the hackathon demo.

Do not expand scope before this path is reliable.
