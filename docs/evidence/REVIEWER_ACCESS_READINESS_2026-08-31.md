# Asynchronous reviewer access readiness — 2026-08-31

## Status

**Application code ready; hosted reviewer gateway pending Firebase setup and
deployment.** The existing `scopelock-api` remains private and operator-key
protected. It must not be made unauthenticated.

## Implemented

- `/review/` reviewer SPA with Firebase email-link sign-in.
- Short-lived Firebase ID tokens held in session storage and refreshed through
  the Firebase Secure Token endpoint.
- Private `/api/reviewer/*` routes with verified-email project scoping.
- Separate public gateway entry point (`scopelock.reviewer_gateway`) that only
  forwards the explicit reviewer route allowlist to the private core using a
  Cloud Run IAM identity token.
- Reviewer dashboard labels the intake as **ScopeLock demo inbox** and never
  presents it as the judge's personal Gmail inbox.
- Reviewer actions still use the existing approval-gated backend policy.

## Remaining hosted steps

1. Initialize Firebase Authentication/Identity Platform in project
   `scopelock-506806` and enable Email link sign-in.
2. Add the deployed gateway hostname to Firebase Authentication authorized
   domains.
3. Set the public Firebase web configuration on the private core, deploy the
   `scopelock-reviewer` gateway with `SCOPELOCK_PRIVATE_API_URL`, and grant its
   service account only `roles/run.invoker` on `scopelock-api`.
4. Verify: sign in with a judge email, send a test requirement from that same
   address to the dedicated demo mailbox, close the browser, return later, and
   review the asynchronously generated artifact.

Firestore creation alone does not initialize Firebase Authentication. Until
these steps are complete, `/api/reviewer/config` intentionally returns a
configuration error and no public reviewer URL should be submitted.
