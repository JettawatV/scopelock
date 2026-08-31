# Final demo readiness audit

Recorded: **2026-08-31**

## Decision

**Core agent and hosted Gmail golden path: PASS.**

The bounded ADK agents, deterministic commerce layer, approval gate, dashboard
workflow, and local replay are ready for the demo scenario. The real Google
Cloud event path has now been exercised end to end on the dedicated Gmail
thread, including final client acceptance and canonical scope promotion.

## Verified in this audit

- Complete deterministic suite: **218/218 passed**.
- Requirement Analyzer live reviewed cases: **12/12 passed**.
- Scope Analyzer live reviewed cases: **35/35 passed**.
- Approval-safe live trajectory cases: **2/2 passed**.
- Focused live-model repeatability: **18/18 passed**.
- Frontend TypeScript check and Vite production build: passed.
- Initial proposal replay: one agent run and one artifact after two identical
  invocations; second invocation returned the prior result.
- Complete local golden path: proposal plus change order, two approvals, two
  send intents, `NO_CHANGE` plus `EXPANSION` plus `CLOSURE`, **+USD 1,500** and
  **+5 days**, final project status `ACTIVE_PROJECT`.
- Client-facing proposal PDF: deterministic, one-page A4 render, text-extraction
  verified, and attached as `application/pdf` in the same-thread Gmail draft.
- Changed-file strong-pattern secret scan: zero matches.

## Hosted golden-path verification

- Cloud Run revision `scopelock-api-00010-s2v` is serving 100% of traffic from an
  immutable Artifact Registry image.
- One real inbound requirement produced one project and one proposal; the
  operator approved and sent the proposal once in the original Gmail thread.
- The client acceptance was confirmed through the dashboard, promoting the
  initial scope to an active canonical baseline at **USD 5,650 / 5 days**.
- A same-thread clarification produced `NO_CHANGE`; a later LINE request
  produced two atomic `EXPANSION` events and one buffered **+USD 1,500 / +5 day**
  delta.
- Finalization, approval, and same-thread send produced Change Order #1 at
  **USD 7,150 / 10 days**. The client accepted it, promoting ScopeVersion 2 to
  `ACCEPTED`, superseding ScopeVersion 1, and applying both buffered events.
- Final project projection is `ACTIVE_PROJECT`, with two accepted artifacts, no
  open buffer, and zero dashboard warnings.

## Hosted correction during final acceptance

The first final-acceptance request exposed a transition-document key collision
when the same project moved from `AWAITING_USER_REVIEW` to `ACTIVE_PROJECT` for a
second accepted artifact. The artifact and scope writes were durable, but the
request returned `500` before the project projection was updated. The workflow
now derives the transition key from the accepted artifact and repairs the
project projection on an idempotent retry. The patched revision returned `200`
and the final projection is consistent. This incident remains visible in Cloud
Logging as a useful reliability/audit record.

## Corrected demo blockers

1. A project now owns one stable scope buffer per accepted baseline. Separate
   expansion and closure messages update that record rather than colliding or
   creating prefix buffers and duplicate revisions.
2. Gmail sends a client-ready PDF derived from the immutable commercial
   artifact and exact scope records. The canonical JSON checksum still governs
   approval and idempotency.
3. The dashboard refreshes automatically every five seconds while visible,
   uses SPA navigation without losing the in-memory operator key, and preserves
   `?demo=1` across demo routes.
4. Client acceptance uses the safe persisted inbox-record ID. The backend
   resolves the private Gmail message ID and revalidates sender, direction, and
   thread before updating the canonical scope.
5. The demo fixture now represents the documented accepted-baseline change
   order: two LINE modules, **+USD 1,500**, **+5 days**, finalized buffer, and a
   change order awaiting review.
6. The commercial review workflow and shared dashboard primitives were split
   from the operator shell to reduce UI coupling before polish.

## Live infrastructure evidence

Follow-up read-only Google Cloud inspection found:

- Cloud Run service `scopelock-api` exists in `asia-southeast1` and has a ready
  revision with the dedicated runtime service account and Secret Manager
  references.
- Firestore database `projects/scopelock-506806/databases/default` exists in
  `asia-southeast1` as `FIRESTORE_NATIVE`.
- The Cloud Run runtime account has `roles/datastore.user` and can access both
  configured Secret Manager secrets.
- The Pub/Sub push account has `roles/run.invoker` on `scopelock-api`.
- Pub/Sub topic `scopelock-gmail` exists with Gmail publisher permission.
- Push subscription `scopelock-gmail-push` exists with authenticated OIDC push,
  retry, and dead-letter configuration.
- The Pub/Sub service agent has token-minting permission on the push account.

The hosted runtime reaches Firestore and the watched Gmail mailbox delivers the
background event loop through Pub/Sub and private Cloud Run.

## Mandatory stop conditions before recording

The following hosted-demo gates are now recorded as passed:

- Authenticated Firestore-backed dashboard and health checks.
- Least-privilege Gmail Pub/Sub topic and authenticated push subscription with
  exact OIDC audience, retry, and dead-letter handling.
- Runtime and push service-account separation with Secret Manager references.
- Real initial proposal, approval, same-thread send, client acceptance,
  clarification, expansion, closure, change-order approval/send, and final
  client acceptance.
- Cloud Run logs and Firestore state/audit evidence captured without exposing
  email bodies, tokens, or operator credentials.

Operational follow-ups for a longer-lived deployment are duplicate Pub/Sub
replay evidence and watch-renewal alerting; they do not block the hackathon
golden-path recording.
- Confirm repository visibility, select exactly one submission category, and
  record a public video no longer than four minutes.
