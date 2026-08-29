# Gmail OAuth and Pub/Sub setup

## What is already implemented

The repository now owns the complete non-UI Gmail runtime:

- OAuth credential bootstrap with exactly `gmail.readonly` and `gmail.compose`;
- `users.watch` registration and expiration tracking;
- authenticated Pub/Sub push handling at `POST /webhooks/gmail`;
- Gmail History API pagination and durable mailbox checkpoints;
- message/thread fetch, normalization, deterministic routing, and replay control;
- operator-key-protected artifact read/approve/reject/revise/draft/send commands;
- same-thread RFC replies with the reviewed commercial bytes attached;
- no-retry uncertain-send handling and send idempotency;
- closure/manual/quiet-window scope-buffer finalization;
- canonical scope update only after a sent artifact is explicitly accepted.

The automated security gate is recorded in `docs/GMAIL_SECURITY_GATE.md`.
Complete its owner-only checklist before registering a real Gmail watch.

Agents do not receive OAuth credentials and cannot call Gmail draft/send,
approval, pricing, timeline, Firestore mutation, or state-transition services.

## One-time actions for the project owner

### 1. Confirm the Google Cloud project and APIs

Use the same project for Vertex AI and the Gmail watch Pub/Sub topic. In Google
Cloud Console, select `scopelock-506806`, then enable:

- Gmail API;
- Pub/Sub API;
- Firestore API;
- Vertex AI API.

The topic project must match the developer project that creates the Gmail
watch. This repository validates that constraint before calling `users.watch`.

### 2. Configure the OAuth consent screen

In **Google Auth Platform**:

1. Complete **Branding** with the demo application name and support email.
2. Under **Audience**, use External/Test unless the demo account belongs to a
   suitable Google Workspace internal organization.
3. Add the dedicated demo Gmail address as a test user.
4. Under **Data Access**, confirm the app requests only:
   - `https://www.googleapis.com/auth/gmail.readonly`
   - `https://www.googleapis.com/auth/gmail.compose`

Do not add `https://mail.google.com/`.

### 3. Create the local OAuth client

In **Google Auth Platform → Clients**:

1. Create an OAuth client of type **Desktop app**.
2. Download its JSON.
3. For local development only, save it as the ignored
   `secrets/client_secret.json`, or preferably set
   `SCOPELOCK_GMAIL_CLIENT_SECRET_PATH` to a protected path outside the
   repository.

The `secrets/client_secret.json`, `client_secret*.json`, and Gmail token names
are ignored by Git.

Activate the existing environment and authorize the dedicated mailbox once:

```powershell
.\.venv313\Scripts\Activate.ps1
scopelock-gmail-auth
scopelock-gmail-auth --check
```

The first command opens Google's consent flow and stores the refresh credential
at `secrets/gmail_token.json` by default. Do not send either JSON file to source
control or include it in logs/screenshots.

The loader accepts only a Desktop-app client, rejects oversized/symlinked JSON,
and rejects a token whose granted scope set differs from the two approved Gmail
scopes. On Windows, verify the token file ACL grants access only to your user;
do not place it in a synchronized/shared folder.

For Cloud Run, store the authorized-user token JSON in Secret Manager and
inject it as `SCOPELOCK_GMAIL_TOKEN_JSON`. Pin an environment-secret reference
to a specific secret version and grant Secret Accessor only to the Cloud Run
runtime service account. Do not copy the token into the container image. The
local token file remains the simplest development path.

### 4. Create the Pub/Sub topic

Create this topic in `scopelock-506806`:

```text
projects/scopelock-506806/topics/scopelock-gmail
```

On that topic, grant **Pub/Sub Publisher** to Google's Gmail push service
account:

```text
gmail-api-push@system.gserviceaccount.com
```

### 5. Create the authenticated push identity and subscription

Create a service account such as:

```text
scopelock-pubsub-push@scopelock-506806.iam.gserviceaccount.com
```

After the FastAPI service has a public HTTPS Cloud Run URL, create a push
subscription for the topic with:

- endpoint: `https://YOUR_SERVICE_URL/webhooks/gmail`;
- push authentication: enabled;
- service account: the dedicated Pub/Sub push account above;
- OIDC audience: the exact value placed in `SCOPELOCK_PUBSUB_AUDIENCE`.

Grant that push service account **Cloud Run Invoker** on only the ScopeLock API
service. The application additionally verifies the token audience, verified
email, and exact service-account email before decoding a notification.

Ensure the Pub/Sub service agent
`service-PROJECT_NUMBER@gcp-sa-pubsub.iam.gserviceaccount.com` can mint the
push account's OIDC token (Google documents the required Service Account Token
Creator permission). Keep the Cloud Run service on **Require authentication**;
do not grant `allUsers` or deploy with `--allow-unauthenticated`.

### 6. Complete runtime configuration

Copy the following keys into the local `.env` or Cloud Run environment. Generate
a unique random operator key of at least 32 characters; do not reuse a Google
credential. In Cloud Run, inject it from a separate Secret Manager secret.

```dotenv
SCOPELOCK_GMAIL_ACCOUNT=your-dedicated-demo@gmail.com
SCOPELOCK_GMAIL_CLIENT_SECRET_PATH=secrets/client_secret.json
SCOPELOCK_GMAIL_TOKEN_PATH=secrets/gmail_token.json
SCOPELOCK_GMAIL_PUBSUB_TOPIC=projects/scopelock-506806/topics/scopelock-gmail
SCOPELOCK_PUBSUB_AUDIENCE=https://YOUR_SERVICE_URL
SCOPELOCK_PUBSUB_PUSH_SERVICE_ACCOUNT=scopelock-pubsub-push@scopelock-506806.iam.gserviceaccount.com
SCOPELOCK_OPERATOR_API_KEY=GENERATE_AT_LEAST_32_RANDOM_CHARACTERS
```

OIDC verification is mandatory in the production runtime and has no disable
flag. A 64-character operator secret can be generated locally without printing
any Google credential:

```powershell
[Convert]::ToHexString(
  [Security.Cryptography.RandomNumberGenerator]::GetBytes(32)
).ToLowerInvariant()
```

Use `SCOPELOCK_GMAIL_TOKEN_JSON` instead of the token path only when Secret
Manager injects the value into Cloud Run.

## Runtime and live gate

Run the API locally for health and operator-command checks:

```powershell
.\.venv313\Scripts\Activate.ps1
uvicorn scopelock.http_api:app --host 127.0.0.1 --port 8080
```

After the hosted endpoint and authenticated subscription exist, register the
watch exactly once (and again for renewal) through the protected command:

```powershell
$serviceUrl = "https://YOUR_SERVICE_URL"
$identityToken = gcloud auth print-identity-token --audiences=$serviceUrl
$headers = @{
  "Authorization" = "Bearer $identityToken"
  "X-ScopeLock-Operator-Key" = $env:SCOPELOCK_OPERATOR_API_KEY
}
Invoke-RestMethod -Method Post -Uri "https://YOUR_SERVICE_URL/gmail/watch" -Headers $headers
```

The operator identity also needs **Cloud Run Invoker** on the API service. The
Google identity token satisfies Cloud Run; the separate operator key satisfies
ScopeLock's application command policy.

Gmail watches expire. Renew at least every seven days; the recommended demo
schedule is daily. Renewal updates the watch expiration but deliberately does
not jump an existing History API checkpoint.

If the application records `FULL_SYNC_REQUIRED`, stop automatic activation and
perform the documented controlled history recovery. Do not manually advance the
checkpoint or delete idempotency records.

Do not mark Day 11 passed until all of these live checks are recorded:

- a new inbound email creates exactly one Firestore project/result;
- the expected Gmail message and thread IDs appear in the event record;
- replaying the same Pub/Sub envelope creates no second model run or artifact;
- a second message in the same Gmail thread resolves to the same project;
- the stored watch expiration and history checkpoint are visible.

Then verify Day 12 with one explicit approval and one same-thread send, including
a repeated send request that returns the original send result. Verify Day 13 by
sending clarification, expansion, and closure messages, approving the one
consolidated revision, and confirming that the accepted baseline changes only
after client acceptance is recorded.

The acceptance command now requires `source_gmail_message_id`; that message must
already be persisted as inbound mail from the project's bound client in the
same Gmail thread. The operator still confirms the semantics of the acceptance,
but cannot substitute a free-text identity.

## References

- [Gmail push notifications](https://developers.google.com/workspace/gmail/api/guides/push)
- [Gmail `users.watch`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users/watch)
- [Gmail `history.list`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.history/list)
- [Gmail thread behavior](https://developers.google.com/workspace/gmail/api/guides/threads)
- [Gmail OAuth scopes](https://developers.google.com/workspace/gmail/api/auth/scopes)
- [Server-side OAuth](https://developers.google.com/workspace/gmail/api/auth/web-server)
- [Authenticated Pub/Sub push](https://docs.cloud.google.com/pubsub/docs/authenticate-push-subscriptions)
- [Cloud Run service authentication](https://docs.cloud.google.com/run/docs/authenticating/service-to-service)
- [Cloud Run Secret Manager integration](https://docs.cloud.google.com/run/docs/configuring/services/secrets)
