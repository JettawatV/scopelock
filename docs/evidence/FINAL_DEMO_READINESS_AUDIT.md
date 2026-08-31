# Final demo readiness audit

Recorded: **2026-08-31**

## Decision

**Core agent and local demo loop: PASS. Hosted Gmail golden path: HOLD.**

The bounded ADK agents, deterministic commerce layer, approval gate, dashboard
workflow, and local replay are ready for the demo scenario. Recording the final
end-to-end demo remains blocked until the real Google Cloud event path is
activated and verified.

## Verified in this audit

- Complete deterministic suite: **216/216 passed**.
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
- Pub/Sub topic `scopelock-gmail`: **not found**.
- Push subscription `scopelock-gmail-push`: **not found**.
- Pub/Sub service-agent token-minting binding on the push account: **not
  present**.

Therefore the hosted runtime can reach Firestore, but Gmail `users.watch` cannot
yet deliver the required background event loop.

## Mandatory stop conditions before recording

Do not record or claim the hosted end-to-end path until all of these pass:

- Verify one authenticated repository write/read against the existing Firestore
  database after the current revision is deployed.
- Create the Gmail Pub/Sub topic and authenticated push subscription, including
  least-privilege IAM, exact OIDC audience, retry policy, and dead-letter
  handling.
- Grant the Google-managed Pub/Sub service agent
  `service-PROJECT_NUMBER@gcp-sa-pubsub.iam.gserviceaccount.com` the
  `roles/iam.serviceAccountTokenCreator` role on
  `scopelock-pubsub-push@scopelock-506806.iam.gserviceaccount.com`.
- Redeploy the current code after UI polish and verify authenticated health.
- Activate `users.watch` only after the security checklist passes.
- Send a real initial client email and verify exactly one Firestore project,
  agent run, proposal, and dashboard review item without opening ScopeLock.
- Approve and send the PDF in the same Gmail thread; repeat the command and
  prove no duplicate send.
- Persist an explicit client acceptance reply, then send clarification,
  expansion, and closure messages and verify one consolidated change order.
- Approve/send the change order and capture Cloud Run logs plus Firestore audit
  history without exposing email bodies, tokens, or operator credentials.
- Confirm repository visibility, select exactly one submission category, and
  record a public video no longer than four minutes.
