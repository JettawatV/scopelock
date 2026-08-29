# Day 11 local OAuth evidence

Date: 2026-08-29

## Sanitized result

- A dedicated demo Gmail account exists and is the configured local mailbox.
- The Google OAuth application remains in Testing mode with that mailbox as a
  test user.
- The Desktop OAuth client is stored outside the repository.
- `scopelock-gmail-auth` completed its localhost callback flow.
- `scopelock-gmail-auth --check` loaded the resulting token successfully.
- The token is stored outside the repository and its contents were not printed.
- Application code enforces exactly `gmail.readonly` and `gmail.compose`.
- A unique 64-character operator key is present only in ignored `.env` local
  configuration; its value was not displayed or recorded.

## Still held

- No OAuth token has been copied to Secret Manager.
- No Cloud Run service or runtime service account has been configured.
- No Pub/Sub topic or authenticated push subscription has been configured.
- Gmail `users.watch` has not been called.
- No live Gmail message, draft, or send has been processed.

This evidence permits the hosted configuration stage. It does not pass Day 11
or authorize continuous mailbox delivery.
