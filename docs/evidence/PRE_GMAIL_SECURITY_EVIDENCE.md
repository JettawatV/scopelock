# Pre-Gmail security and refactor evidence

Recorded: 2026-08-29

## Gate result

**Automated code security gate: PASS. Real Gmail activation: HOLD pending the
owner-only IAM/OAuth/logging checklist.**

No OAuth token, Gmail account, Pub/Sub subscription, Cloud Run service, external
draft, or external send was created by this pass.

## Security refactor evidence

- Production Pub/Sub OIDC verification can no longer be disabled by an
  environment flag.
- API request bodies are limited to 64 KiB; docs/OpenAPI are disabled; security
  headers and redacted error references are enforced.
- Operator keys require 32+ characters in the real runtime and are compared as
  fixed-length SHA-256 digests using constant-time comparison.
- Gmail event processing has atomic expiring leases, bounded pages/messages,
  bounded MIME/thread context, and monotonic CAS checkpoint updates.
- Same-thread commercial drafts validate safe RFC headers and bind both source
  sender and recipient to the project's client/thread.
- Canonical acceptance now requires persisted client-message evidence from the
  same thread.
- OAuth files are size-bounded, desktop-client-only, symlink-safe, atomic, and
  checked for an exact least-privilege scope set.
- Raw external exception text is no longer stored in Gmail event/send errors or
  returned from runtime initialization/webhook failures.

## Automated tests

Command:

```powershell
.\.venv313\Scripts\python.exe -m pytest -q
```

Result: **187 passed**, 0 failed, under Python 3.13.14 and pytest 9.1.1.

The Gmail integration corpus contains 21 tests, including active/stale
processing leases, monotonic checkpoints, event/body limits, future-thread
exclusion, header injection, exact OAuth scopes, client/thread recipient
binding, acceptance evidence, error redaction, disabled docs, security headers,
and invalid topic names.

## Static, secret, and dependency checks

- `bandit -r app scopelock -q`: **0 findings** after replacing six optimization-
  unsafe runtime assertions with explicit fail-closed exceptions.
- `uv pip check --python .venv313\Scripts\python.exe`: **150 packages compatible**.
- Tracked/untracked source scan for Google API keys, OAuth access/refresh tokens,
  private-key blocks, and service-account private keys: **0 matches**.
- Tracked filename scan: no token, OAuth client-secret, credential, PEM, or P12
  artifact is tracked; `.env.example` is the expected non-secret template.
- `git check-ignore` confirms `.env`, `secrets/client_secret.json`, and
  `secrets/gmail_token.json` are ignored.
- Initial `pip-audit` found `PYSEC-2026-1845` in pytest 8.4.2. The dev
  requirement and lock were upgraded to pytest 9.1.1. Final `pip-audit`:
  **no known vulnerabilities found** (the local unpublished `scopelock` package
  is correctly reported as not present on PyPI).
- `git diff --check` and Python compile checks pass.

The pytest advisory is local/Unix and development-only, but it was removed
rather than waived. The patched range starts at pytest 9.0.3:
[GitHub reviewed advisory](https://github.com/advisories/GHSA-6w46-j5rx-g56g).

## Residual live controls

The automated pass cannot prove Google Cloud IAM, Secret Manager access,
authenticated Pub/Sub delivery, Gmail consent, hosted log redaction, quota
alerts, token revocation, or a real same-thread send. Those checks remain open
in `docs/GMAIL_SECURITY_GATE.md` and block automatic Gmail events.
