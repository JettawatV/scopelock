# ScopeLock Cloud Run deployment runbook

## Gate status

The production container and hosted-configuration preflight are implemented.
Local OAuth for the dedicated demo mailbox passed on 2026-08-29. The private
Cloud Run service is deployed in `asia-southeast1`; authenticated hosted health,
Pub/Sub delivery, logging checks, and Gmail `users.watch` activation remain
incomplete.

Do not create the Gmail watch until every pre-activation check in
`docs/GMAIL_SECURITY_GATE.md` passes. Do not deploy with public/unauthenticated
invocation.

## Deployment contract

- Project: `scopelock-506806`
- Region: `asia-southeast1`
- Cloud Run service: `scopelock-api`
- Artifact Registry repository: `scopelock`
- Runtime service account:
  `scopelock-runtime@scopelock-506806.iam.gserviceaccount.com`
- Pub/Sub push service account:
  `scopelock-pubsub-push@scopelock-506806.iam.gserviceaccount.com`
- Topic: `projects/scopelock-506806/topics/scopelock-gmail`
- Push subscription: `scopelock-gmail-push`
- Endpoint: `https://SERVICE_URL/webhooks/gmail`
- OIDC audience: exact Cloud Run service origin, without the webhook path

The container pins Node, Vite, Python, and uv versions. A Node build stage
exports the operator UI and the non-root Python runtime serves those assets with
the API. It installs only locked dependencies, copies only runtime
packages/configuration, runs as UID/GID `10001`, and starts through
`python -m scopelock.cloud_run`. Both
`.dockerignore` and `.gcloudignore` exclude local environments, OAuth files,
tokens, service-account files, artifacts, tests, and logs.

Cloud Run injects `PORT`. The process rejects malformed ports and fails startup
when hosted Gmail token JSON, the operator key, Vertex mode, mailbox, topic,
audience, or push identity is missing or inconsistent. The topic and push
service account must belong to `GOOGLE_CLOUD_PROJECT`.

`SCOPELOCK_ARTIFACT_ROOT=/tmp/scopelock-artifacts` is intentionally ephemeral.
Those local JSON/Markdown renders are diagnostic copies. Reviewed commercial
bytes and checksums are reconstructed from the Firestore-owned immutable
`CommercialArtifact`; Gmail send never trusts an ephemeral render path.

## Owner console sequence

### 1. Enable required APIs

In project `scopelock-506806`, enable:

- Artifact Registry API;
- Cloud Build API;
- Cloud Run Admin API;
- Secret Manager API;
- Gmail API;
- Pub/Sub API;
- Firestore API;
- Vertex AI API.

Create the Firestore database in Native mode if it does not exist. Keep the
database and Cloud Run region aligned where the console permits.

### 2. Create separate service accounts

Create the runtime and push accounts named above. Do not create or download
service-account keys.

Grant the runtime account:

- `Cloud Datastore User` (`roles/datastore.user`) on the project;
- `Vertex AI User` (`roles/aiplatform.user`) on the project;
- `Secret Manager Secret Accessor` only on the two ScopeLock secrets below.

Do not grant the push account project-wide roles. After Cloud Run exists, grant
it `Cloud Run Invoker` only on `scopelock-api`.

### 3. Create Secret Manager secrets

Create two separate secrets:

- `scopelock-gmail-token` — the complete local authorized-user token JSON;
- `scopelock-operator-key` — the 64-character local operator key.

Upload values through the Secret Manager console without copying them into
commands, logs, screenshots, deployment YAML, or this repository. Grant the
runtime service account access to these two secrets only. Use a numbered secret
version for the first deployment, not `latest`.

Map them into Cloud Run as:

```text
SCOPELOCK_GMAIL_TOKEN_JSON -> scopelock-gmail-token:VERSION
SCOPELOCK_OPERATOR_API_KEY -> scopelock-operator-key:VERSION
```

### 4. Create Artifact Registry and build

Create a Docker repository named `scopelock` in `asia-southeast1`. From the clean
repository root, authenticate `gcloud`, then build an immutable commit-tagged
image:

```powershell
$projectId = "scopelock-506806"
$region = "asia-southeast1"
$tag = git rev-parse --short HEAD
$image = "${region}-docker.pkg.dev/${projectId}/scopelock/scopelock-api:${tag}"
gcloud builds submit --project $projectId --tag $image .
```

The submitted source must report no `.env`, OAuth/token, local virtual
environment, artifact, or service-account file in the Cloud Build source list.

### 5. Deploy the private Cloud Run service

Create `scopelock-api` from the image using:

- region `asia-southeast1`;
- runtime service account `scopelock-runtime@...`;
- **Require authentication**;
- ingress `All` so authenticated Pub/Sub push can reach the generated URL;
- container port `8080`;
- startup HTTP probe `/health` on port `8080`;
- request timeout `300` seconds initially;
- concurrency `1` for the first live gate;
- minimum instances `0`, maximum instances `1` for the first live gate.

Set these non-secret environment variables:

```dotenv
GOOGLE_CLOUD_PROJECT=scopelock-506806
GOOGLE_CLOUD_LOCATION=asia-southeast1
GOOGLE_GENAI_USE_VERTEXAI=true
SCOPELOCK_MODEL=gemini-3.5-flash
SCOPELOCK_PROMPT_VERSION=requirement_analyzer_v5
SCOPELOCK_SOP_PATH=config/jvl_sop.example.yaml
SCOPELOCK_GMAIL_ACCOUNT=THE_DEDICATED_DEMO_MAILBOX
SCOPELOCK_FIRESTORE_DATABASE=default
SCOPELOCK_GMAIL_PUBSUB_TOPIC=projects/scopelock-506806/topics/scopelock-gmail
SCOPELOCK_PUBSUB_AUDIENCE=https://TEMPORARY.invalid
SCOPELOCK_PUBSUB_PUSH_SERVICE_ACCOUNT=scopelock-pubsub-push@scopelock-506806.iam.gserviceaccount.com
SCOPELOCK_ARTIFACT_ROOT=/tmp/scopelock-artifacts
```

Attach the two Secret Manager values as environment-secret references. After
the first revision returns its generated `https://...run.app` service URL,
replace `SCOPELOCK_PUBSUB_AUDIENCE` with that exact origin and deploy a new
revision before creating the subscription.

### 6. Create the topic and authenticated push subscription

Create topic `scopelock-gmail`. On that topic, grant `Pub/Sub Publisher` only
to:

```text
gmail-api-push@system.gserviceaccount.com
```

Grant the push service account `Cloud Run Invoker` on `scopelock-api` only.
Ensure the Google-managed Pub/Sub service agent
`service-PROJECT_NUMBER@gcp-sa-pubsub.iam.gserviceaccount.com` can mint the
push identity's token through `Service Account Token Creator` as documented by
Google.

Create `scopelock-gmail-push` with:

- delivery type: Push;
- endpoint: exact service URL plus `/webhooks/gmail`;
- authentication: enabled;
- service account: `scopelock-pubsub-push@...`;
- audience: exact value in `SCOPELOCK_PUBSUB_AUDIENCE`;
- payload unwrapping: disabled;
- dead-letter topic and retry monitoring configured before watch activation.

### 7. Run hosted negative checks before Gmail watch

Record sanitized evidence that:

- an unauthenticated request is rejected by Cloud Run IAM;
- an authorized operator request with a missing/wrong operator key is rejected
  by ScopeLock before Gmail/Firestore initialization;
- a Pub/Sub push token with the wrong audience or identity is rejected;
- `/health` returns only `{"status":"ok"}` for an authorized caller;
- Cloud Logging contains no Authorization header, OAuth/token JSON, operator
  key, full email body, or attachment content.

Only after these checks should the protected `/gmail/watch` command be called.

### 8. Validate the combined operator UI

The Cloud Run service remains private. A normal browser navigation to the
`run.app` URL does not attach a Cloud Run identity token, so it must not be used
as the operator access path. For the hackathon and owner-only validation, run
an authenticated local proxy and keep that terminal open:

```powershell
gcloud run services proxy scopelock-api `
  --project scopelock-506806 `
  --region asia-southeast1 `
  --port 8082
```

Then open `http://127.0.0.1:8082/?demo=1` in a second terminal/browser. If port
8082 is occupied, choose another unused local port. The active `gcloud`
principal must be allowed to invoke `scopelock-api`. Direct hosted browser
access for other reviewers requires a separately reviewed identity-aware access
layer; do not make the service unauthenticated just to expose the UI.

Through the authenticated proxy:

- `/` serves the operator-key connection screen;
- `/?demo=1`, `/projects/?demo=1`, and `/evals/?demo=1` show the labelled,
  non-mutating reviewed fixture;
- `/api/dashboard` rejects a missing or wrong operator key;
- a correct key returns only the redacted dashboard projection;
- no operator key appears in HTML, JavaScript bundles, browser storage, logs,
  or screenshots;
- approve, draft, and send remain separate actions and backend policy rejects
  any invalid sequence.

## Required references

- [Cloud Run container contract](https://docs.cloud.google.com/run/docs/container-contract)
- [Cloud Run service authentication](https://docs.cloud.google.com/run/docs/authenticating/service-to-service)
- [Cloud Run Secret Manager integration](https://docs.cloud.google.com/run/docs/configuring/services/secrets)
- [Authenticated Pub/Sub push](https://docs.cloud.google.com/pubsub/docs/authenticate-push-subscriptions)
- [Gmail push notifications](https://developers.google.com/workspace/gmail/api/guides/push)
- [uv Docker integration](https://docs.astral.sh/uv/guides/integration/docker/)
