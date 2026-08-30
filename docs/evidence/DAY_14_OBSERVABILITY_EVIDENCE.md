# Day 14 — Structured observability evidence

Recorded: **2026-08-30**

## Implemented

- `scopelock.observability` emits raw JSON events suitable for Cloud Logging.
- The schema allowlists only correlation, application-record, status, action,
  and timing references. It rejects unapproved fields such as authorization
  material, email bodies, keys, tokens, and persistence payloads.
- `ModelStore` emits one redacted event for every create-or-get and
  compare-and-set operation. The event includes collection, record ID, and any
  available project, agent-run, tool-action, artifact, approval, send,
  transition, correlation, action, or status reference. It never emits the
  stored model payload.
- The HTTP boundary emits a redacted completion event with a generated request
  ID, method, path, HTTP status, and duration. It does not log headers, query
  values, or request body bytes.
- The Cloud Run entry point configures the event logger before Uvicorn begins
  accepting traffic.

## Automated verification

```text
34 focused tests passed
Vite production build passed
212 full Python tests passed
```

`tests/unit/test_observability.py` proves that secret-like fields are rejected
and persistence audit payloads are excluded from structured events.

## Remaining hosted evidence

The owner must still inspect Cloud Logging after a hosted request and real
workflow event to prove that the expected JSON events are present and that no
Authorization header, OAuth JSON, operator key, email body, or attachment
content appears. This local implementation result does not satisfy that hosted
review gate.
