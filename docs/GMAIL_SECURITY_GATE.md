# Gmail connection security gate

## Decision

**Code gate: PASS. Live OAuth/event activation: HOLD.**

ScopeLock may create the OAuth client and authorize the dedicated demo mailbox,
but `users.watch` and the real Pub/Sub subscription must remain inactive until
the owner-only checklist below is complete. The thin operator UI is deployed,
but it does not authorize Gmail event delivery or email sending.

This gate reduces the risk of credential theft, forged webhooks, prompt
injection, duplicate sends, data leakage, replay races, and cost/availability
abuse. It does not claim that connecting an email account can be made risk-free.

## Protected assets and trust boundaries

- Gmail refresh token and OAuth client configuration;
- email bodies, sender identities, thread/message IDs, and attachment metadata;
- deterministic SOP prices, timelines, proposals, approvals, and accepted scope;
- Pub/Sub push identity and Gmail history checkpoint;
- Firestore audit, idempotency, and commercial records;
- operator command key and Cloud Run invocation permission.

Untrusted inputs are the HTTP request, Pub/Sub envelope, Gmail headers/body,
client instructions, ADK output, and operator-supplied command data. Google-signed
identity is verified before Pub/Sub data is decoded. Agent output is never an
authorization decision.

## Implemented controls

- OAuth accepts exactly `gmail.readonly` plus `gmail.compose`; tokens with
  missing or additional scopes are rejected.
- Desktop OAuth and token JSON are size-bounded, symlink writes/reads are
  rejected, local token writes are atomic, and hosted tokens come from Secret
  Manager rather than the image or source tree.
- The production runtime always constructs a Pub/Sub OIDC verifier. There is no
  environment switch that can disable verification.
- OIDC validation binds signature/expiry/audience through Google Auth, then
  checks the exact push service-account email and verified-email claim.
- The HTTP API disables interactive docs/OpenAPI, limits bodies to 64 KiB,
  emits no-store/frame/nosniff/referrer security headers, bounds command fields,
  compares fixed-length operator-key hashes, and returns redacted error
  references rather than internal exception text.
- Default operator and webhook routes reject invalid credentials before loading
  Gmail OAuth credentials or initializing Gmail/Firestore clients.
- Gmail notification IDs, history IDs, pagination, messages per event, MIME
  depth/part count, headers, text, attachments, and thread context are bounded.
  Attachment contents are never sent to an agent.
- Pub/Sub processing uses an atomic 15-minute lease. A crashed worker can be
  reclaimed, an active worker cannot be duplicated, and mailbox checkpoints
  advance monotonically under concurrent delivery.
- Expired history or an oversized mailbox delta becomes a durable
  `FULL_SYNC_REQUIRED` outcome. It is not silently skipped.
- Commercial MIME headers reject control/header injection. Draft recipients are
  bound to the project's client email, and the source reply must be a message
  from that client in the exact Gmail thread.
- Agents have no Gmail send, approval, pricing, timeline, or state-mutation
  tools. Draft/send requires a current approval bound to artifact version and
  checksum; repeat execution returns the durable prior result.
- Canonical scope acceptance requires the ID of a persisted inbound Gmail
  message from the bound client in the bound thread. Free-text operator claims
  are insufficient.
- External failures persisted in event/send records are redacted and carry only
  a diagnostic reference.

## Owner-only Google Cloud checklist

- [x] Use a dedicated demo Gmail account with no personal or unrelated client
  mail. Keep the OAuth app in Testing and add only that mailbox as a test user.
- [x] Confirm the OAuth consent screen requests only `gmail.readonly` and
  `gmail.compose`; never approve `https://mail.google.com/`.
- [ ] Store the refresh-token JSON and operator key as separate Secret Manager
  secrets. Grant `Secret Manager Secret Accessor` only to the Cloud Run runtime
  service account and pin environment-secret references to a specific version.
- [ ] Deploy Cloud Run as **Require authentication**. Do not grant
  `allUsers`/`allAuthenticatedUsers` and do not use `--allow-unauthenticated`.
- [ ] Use separate least-privilege service accounts for Cloud Run runtime and
  Pub/Sub push. Grant the push account `Cloud Run Invoker` on this service only.
- [ ] Configure authenticated Pub/Sub push with the exact Cloud Run URL as the
  OIDC audience. Confirm the Pub/Sub service agent can mint the push identity's
  OIDC token as required by Google Cloud.
- [ ] Grant topic publish access only to
  `gmail-api-push@system.gserviceaccount.com`; remove broad topic publishers.
- [ ] Give the runtime service account only the Firestore and Secret Manager
  permissions required by ScopeLock. Do not deploy service-account key files.
- [ ] Set Pub/Sub retry/dead-letter monitoring, Cloud Run request/error alerts,
  Vertex quota/budget alerts, and a daily Gmail watch-renewal job.
- [ ] Verify Cloud Logging does not contain Authorization headers, OAuth JSON,
  full email bodies, attachment contents, operator keys, or unredacted errors.
- [ ] Generate a unique 32-byte-or-longer operator secret, store it in Secret
  Manager, and share Cloud Run Invoker only with the operator identity.
- [ ] Record sanitized IAM, subscription, secret-version, and log-review
  evidence without screenshots containing tokens or client mail.

Local OAuth and local operator-key evidence is recorded in
`docs/evidence/DAY_11_LOCAL_OAUTH_EVIDENCE.md`. All hosted checklist items remain
open. The exact private deployment sequence is
`docs/CLOUD_RUN_DEPLOYMENT.md`.

Google documents that authenticated Pub/Sub push uses a signed OIDC token and
that subscribers should validate its audience, email, and verified-email claims:
[Pub/Sub push authentication](https://docs.cloud.google.com/pubsub/docs/authenticate-push-subscriptions).
Cloud Run services are private by default and support Secret Manager-backed
configuration: [Cloud Run configuration](https://docs.cloud.google.com/run/docs/configuring)
and [Cloud Run secrets](https://docs.cloud.google.com/run/docs/configuring/services/secrets).
Gmail requires publisher access for its push service account:
[Gmail push notifications](https://developers.google.com/workspace/gmail/api/guides/push).

## Live attack/recovery checks before activation

- [ ] Invalid/missing Pub/Sub bearer token returns 401 and creates no record.
- [ ] Valid token with the wrong audience or service-account email is rejected.
- [ ] Oversized/malformed webhook body returns 400/413 without exposing content.
- [ ] Duplicate active delivery creates no second agent call or artifact.
- [ ] An expired processing lease is reclaimed exactly once.
- [ ] Out-of-order delivery cannot move the Gmail checkpoint backward.
- [ ] Email from the ScopeLock mailbox, automated mail, empty mail, and irrelevant
  mail invoke no model or commercial action.
- [ ] Prompt-injection email cannot expose SOP commerce, mutate state, approve,
  draft, or send.
- [ ] Missing/stale/rejected approval creates zero Gmail drafts/sends.
- [ ] Same send command twice produces one Gmail send result and one message.
- [ ] A draft cannot target an address different from the bound project client.
- [ ] A fake acceptance message from another sender/thread cannot update scope.
- [ ] Revoking the Gmail token makes the runtime fail closed; reauthorization
  restores service without changing accepted scope or replay records.

## Incident stop conditions

Immediately disable the Gmail watch and Pub/Sub subscription, revoke the Gmail
OAuth grant, rotate the operator secret, and preserve audit records if a token is
exposed, an unauthorized send occurs, a duplicate send is suspected, the
checkpoint moves backward, or logs contain email/credential content. Do not
resume until the cause is fixed and this gate is rerun.
