# ScopeLock — Firestore Persistence Contract

## Ownership

Application code owns every write. ADK agents receive only narrow read-only
tools and never receive arbitrary Firestore access.

| Collection | Owner | Canonical identity / immutability |
| --- | --- | --- |
| `projects` | application workflow | one project per Gmail thread; CAS updates |
| `scope_versions` | commercial service | project + scope version; accepted records immutable |
| `scope_events` | scope workflow | one record per Gmail message and semantic event |
| `buffers` | scope buffer service | baseline + pending event set; CAS updates |
| `artifacts` | proposal service | project + artifact type + version; prior versions preserved |
| `agent_runs` | audited ADK boundary | trigger + agent + prompt version |
| `tool_actions` | audited ADK boundary | agent run + ordered action ID |
| `approvals` | approval policy | artifact ID + version + checksum; immutable |
| `sends` | deterministic send service | artifact + checksum + Gmail thread; immutable |
| `eval_results` | evaluation runner | eval set + prompt/SOP version + run ID; immutable |

The adapter also owns `_scopelock_unique_keys`. Each index document hashes the
collection, key name, and key value, then points to one canonical business
document. Business records and unique-index records are written in the same
Firestore transaction.

## Record envelope

Every collection document uses the repository envelope:

```text
collection
document_id
payload
revision
immutable
unique_keys
created_at
updated_at
```

`compare_and_set(expected_revision=...)` protects project, buffer, artifact,
and event updates from races. An accepted `scope_versions` document is written
with `immutable=true`; a later non-no-op update fails.

## Required unique keys

- Gmail message ID
- Gmail thread ID
- Gmail history record (`mailbox + historyId`)
- Pub/Sub event/message ID
- artifact project/type/version
- approval artifact/version/checksum
- send artifact/version/checksum/thread

`scopelock.services.idempotency_service.IdempotencyKeys` creates namespaced
SHA-256 keys for all seven identities.

## Retry and timeout boundary

- Model calls: 45-second timeout, up to 3 transient attempts.
- Persistence calls: 10-second timeout, up to 4 transient attempts.
- External reads: 20-second timeout, up to 3 transient attempts.
- External sends: 20-second timeout, exactly 1 attempt at this layer. A send is
  retried only after the idempotency record and provider state are reconciled.

## Local and emulator verification

The deterministic suite uses the same repository contract with an atomic,
thread-safe in-memory adapter and a transaction-capable Firestore fake. The
controlled replay fixture is `tests/fixtures/firestore_replay_cases.json`.

For an optional real emulator run, start the Google Cloud Firestore emulator,
set `FIRESTORE_EMULATOR_HOST`, and construct
`google.cloud.firestore_v1.Client(project="scopelock-emulator")`. The official
server client automatically routes to the emulator when that environment
variable is present.
