# Day 14 — Hosted private-route evidence

Recorded: **2026-08-30**

> Historical route-smoke snapshot. Hosted Gmail activation and the complete
> golden path were subsequently verified; see
> `HOSTED_PRECHECK_2026-08-31.md` and `FINAL_DEMO_READINESS_AUDIT.md` for the
> current release status.

## Verified

The combined FastAPI and Vite image is deployed to an IAM-authenticated Cloud
Run service. An owner-authenticated request using a Google identity token
returned the following results:

```text
/health -> 200
/ -> 200
/projects -> 200
/evals -> 200
```

This proves that the private Cloud Run service, health endpoint, Vite static
asset mount, and SPA routes are reachable by an authorized owner. The service
is intentionally not public.

## Corrective note

The original `/healthz` endpoint was replaced with `/health`. Cloud Run reserves
some paths ending in `z`, so `/healthz` can be rejected before the request
reaches the FastAPI application.

## Not yet proven

- least-privilege IAM review and Secret Manager version review;
- authenticated Pub/Sub push delivery and dead-letter/retry configuration;
- real Gmail History API resolution, duplicate delivery, and same-thread replay;
- approval-gated same-thread draft/send and revision send;
- redacted hosted workflow logs and demo Trace/Logging view.

`users.watch` remains disabled until those Day 11–14 gates are recorded.
