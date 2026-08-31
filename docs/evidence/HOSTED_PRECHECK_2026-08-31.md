# ScopeLock hosted activation preflight — 2026-08-31

Status: **hosted Gmail golden path verified; watch active**

This record contains only sanitized deployment metadata and response status.
It does not contain OAuth tokens, operator keys, message bodies, Gmail message
IDs, or attachment content.

## Deployed contract

- Project: `scopelock-506806`
- Region: `asia-southeast1`
- Service: `scopelock-api`
- Ready revision: `scopelock-api-00010-s2v`
- Firestore database: `default` (Firestore Native)
- Intake topic: `projects/scopelock-506806/topics/scopelock-gmail`
- Push subscription: `scopelock-gmail-push`
- Push endpoint: `/webhooks/gmail`
- OIDC audience: the exact stable Cloud Run service origin
- Retry: 10 seconds minimum, 600 seconds maximum
- Dead letter: `scopelock-gmail-dead-letter`, five delivery attempts
- Cloud Run: private, runtime service account, maximum one instance,
  concurrency one
- Gmail watch: registered for the dedicated demo mailbox; expiration is
  visible in the protected dashboard

## Pre-activation and post-activation probes

| Probe | Observed result |
| --- | --- |
| Unauthenticated `/health` | `403` from Cloud Run IAM |
| Authenticated `/health` | `200`, body exactly `{"status":"ok"}` |
| Missing operator key | `401` |
| Wrong operator key | `401` |
| Correct operator session | `200` |
| Firestore-backed dashboard | `200`, no warnings |
| Non-Pub/Sub identity at Gmail webhook | `401` |
| `users.watch` registration | `200` |

## Real Gmail golden-path evidence

The dedicated mailbox completed the production replay without opening
ScopeLock to trigger processing:

- One inbound requirement created one project, one agent run, one proposal, and
  one review item.
- The operator approved the proposal and ScopeLock created and sent exactly one
  same-thread Gmail reply with the proposal PDF.
- The client acceptance reply was confirmed through the dashboard; the project
  became `ACTIVE_PROJECT` at **USD 5,650 / 5 days**.
- A clarification was classified `NO_CHANGE` with no price or timeline delta.
- The LINE request produced two atomic `EXPANSION` events, consolidated into one
  buffer at **+USD 1,500 / +5 days**.
- Manual finalization produced Change Order #1 at **USD 7,150 / 10 days**.
- The operator approved and sent Change Order #1 exactly once in the original
  Gmail thread.
- The client acceptance reply was confirmed; ScopeVersion 2 became `ACCEPTED`,
  ScopeVersion 1 became `SUPERSEDED`, and the project became `ACTIVE_PROJECT` at
  **USD 7,150 / 10 days**. Both buffered events became `APPLIED`.
- Final dashboard projection: two accepted commercial artifacts, four scope
  events (two expansions, one clarification, one closure), no open buffer, and
  zero dashboard warnings.

## Reliability correction recorded during replay

The first final-acceptance request exposed a deterministic transition-key
collision after the artifact and scope writes had succeeded. The endpoint
returned `500`, leaving the project projection behind the accepted records. The
acceptance workflow was patched to use an artifact-specific transition key and
to converge project state on a retry. Cloud Run revision `00010-s2v` was
deployed from an immutable image; the retry returned `200` and repaired the
canonical project projection. The regression suite now passes **217 tests**.

## Remaining release evidence

The core hosted demo path is complete. These operational follow-ups are still
recommended before a longer-lived deployment:

1. Exercise an intentional duplicate Pub/Sub replay in the hosted environment
   and retain the no-duplicate evidence.
2. Add watch-renewal monitoring and alert/recovery evidence for a longer-lived
   deployment.

These follow-ups do not block the four-minute hackathon golden-path recording;
the production demo path and its approval gates have been verified.
