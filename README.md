# ScopeLock

ScopeLock is an ADK-first, approval-gated agent that turns an inbound client
email into an SOP-aligned proposal, then monitors the same thread for material
scope changes.

Start with `AGENTS.md`. Official hackathon rules override this repository's
context documents if there is a conflict.

## Contents

- `AGENTS.md` — authoritative build instructions and anti-drift rules
- `docs/PRODUCT_SPEC.md` — what ScopeLock does and does not do
- `docs/ARCHITECTURE.md` — system and Google Cloud architecture
- `docs/DOMAIN_MODEL.md` — entities, state machines, lifecycle rules
- `docs/AGENT_DESIGN.md` — ADK/Gemini agent responsibilities and tool boundaries
- `docs/JVL_SOP_SPEC.md` — how business SOP drives deterministic pricing/timeline
- `docs/EVAL_PLAN.md` — evals, trajectory tests, safety invariants
- `docs/IMPLEMENTATION_PLAN.md` — build order for the remaining hackathon days
- `docs/DAILY_IMPLEMENTATION_PLAN.md` — granular daily checklists, evidence, and move-on gates
- `docs/RISK_REGISTER.md` — active delivery, safety, integration, and demo risks
- `docs/FIRESTORE_SCHEMA.md` — persistent collection ownership, unique keys, and CAS rules
- `docs/GMAIL_OAUTH_AND_PUBSUB_SETUP.md` — exact owner actions and live Gmail gate
- `docs/GMAIL_SECURITY_GATE.md` — pre-connection threat model, owner controls, attack checks, and stop conditions
- `docs/LOCAL_DEMO_RUNBOOK.md` — exact non-UI golden-path rehearsal
- `docs/MIDPOINT_REFACTOR.md` — shared persistence, identity, state, and workflow boundaries
- `docs/HACKATHON_REQUIREMENTS.md` — concise guardrails; official uploaded rules override it
- `docs/DEMO_GOLDEN_PATH.md` — one scenario the entire build should optimize around
- `config/jvl_sop.example.yaml` — illustrative machine-readable SOP
- `evals/scopelock_eval_cases.jsonl` — 25 starter semantic eval cases
- `app/agent.py` — ADK-native `ScopeLock` root agent
- `app/sub_agents/requirement_analyzer.py` — typed new-project analyzer
- `app/sub_agents/scope_analyzer.py` — typed existing-project scope analyzer
- `app/tools/` — narrow, read-only ADK tools
- `scopelock/` — deterministic domain and application code, outside agents
- `tests/` — unit, integration, and native ADK evaluation assets

## One-line product

ScopeLock turns an inbound client email into an SOP-aligned proposal for review, sends it after approval, and then autonomously monitors the Gmail thread for commercially meaningful scope changes.

## Reproducible local setup

ScopeLock requires Python 3.13. The verified ADK development environment is
`.venv313`.

From the repository root:

```powershell
uv python install 3.13
uv venv --python 3.13 .venv313
$env:UV_PROJECT_ENVIRONMENT = ".venv313"
uv sync --locked --python 3.13 --extra dev
.\.venv313\Scripts\Activate.ps1
python --version
python -m pytest -q
```

The project `uv.lock` pins the resolved dependency set. Verified on
2026-08-29 with Python 3.13.14, ADK 2.8.0, the Gmail API/OAuth clients,
successful ADK discovery, pytest 9.1.1, and 191 passing tests. This uv-managed environment
does not require an embedded `pip` module.

## Development workflow

ScopeLock is developed ADK-first. The current hierarchy is:

```text
ScopeLock (root agent)
├── Requirement Analyzer (typed new-project analysis)
└── Scope Analyzer (typed existing-project change analysis)
```

Requirement Analyzer v5 passes 12/12, Scope Analyzer v4 passes 35/35, both
native ADK trajectory cases pass, and the focused repeatability gate passes
18/18. The Days 11–13 application code is implemented; real Gmail/Google Cloud
activation remains held until the owner completes
`docs/GMAIL_SECURITY_GATE.md`, `docs/GMAIL_OAUTH_AND_PUBSUB_SETUP.md`, and the
live mailbox gates.
Frontend UI/UX remains locked.

The ADK app selector displays `app` because that name must match the
discoverable `app/` package. The root agent inside it is named `scopelock`.

After activating `.venv313`, use native ADK tools from the repository root:

```powershell
adk web . --port 8000 --no-reload
adk run app
adk eval app tests/eval/requirement_analyzer.evalset.json `
  --config_file_path tests/eval/requirement_analyzer.config.json `
  --print_detailed_results
adk eval app tests/eval/scope_analyzer.evalset.json `
  --config_file_path tests/eval/scope_analyzer.config.json
adk eval app tests/eval/workflow_trajectories.evalset.json `
  --config_file_path tests/eval/workflow_trajectories.config.json
```

Run the complete agent-plan regression gate with one command:

```powershell
.\scripts\test-agent-plan.ps1
.\scripts\test-agent-plan.ps1 -LiveAdk
```

The first command runs all deterministic contract, unit, and integration tests.
`-LiveAdk` then runs all three reviewed eval sets against Vertex AI and inspects
ADK's result JSON, because the ADK command can return exit code zero even when a
custom semantic metric fails a case.

`adk web` should be the main interactive development loop. The local `.adk/`
directory it creates is ignored. The JSONL corpus remains the curated source
set; promote specification-reviewed cases into `tests/eval/` for native ADK runs.

### Deterministic local workflow

Use the reviewed fixture to run the application-owned proposal path without a
frontend or live Gmail call:

```powershell
python -m scopelock.cli initial-proposal --repeat 2
python -m scopelock.cli golden-path
```

The first command proves initial-proposal idempotency and ends at
`AWAITING_USER_REVIEW`. The second rehearses the documented post-acceptance
change-order story: initial approval, `NO_CHANGE`, LINE `EXPANSION`, semantic
closure, +USD 1,500 / +5 days, and a second approval-bound local send intent.
Generated proposal data and Markdown are written under the ignored
`artifacts/local_workflow/` directory.

### Audited Requirement Analyzer runner

Use the application-owned runner when a development run must persist validated
metadata and tool actions independently of ADK's internal session format:

```powershell
python -m scopelock.adk_runner "Paste an inbound project-requirement email here."
```

Each run writes an ignored local bundle under
`artifacts/agent_runs/<run-id>/`:

- `agent_run.json` contains correlation ID, agent, model, prompt version, input
  hash, status, validated output, error metadata, and timestamps.
- `tool_actions.jsonl` contains ordered tool calls and results.

Schema-invalid output, missing final output, or unknown SOP modules become
`NEEDS_REVIEW`. Configuration or transport failures become `FAILED`. Neither
path has access to a send tool.

### One-time Google Cloud setup

The application loads `GOOGLE_CLOUD_PROJECT`, location, Vertex mode, and model
from `.env`. The gcloud CLI does not automatically read `.env`, so use the
project setup script instead of repeatedly typing the project ID:

```powershell
.\scripts\configure-gcp.ps1
```

The script sets the gcloud project, enables `aiplatform.googleapis.com`, sets
the Application Default Credentials quota project, and verifies that the API
is enabled. To check configuration without changing cloud state:

```powershell
.\scripts\configure-gcp.ps1 -VerifyOnly
```

### Gmail runtime

The FastAPI-compatible Gmail/event and operator-command surface lives at
`scopelock.http_api:app`. It keeps OAuth, History API, approval, draft/send,
and scope-version mutation outside ADK tools.

```powershell
uvicorn scopelock.http_api:app --host 127.0.0.1 --port 8080
```

Pass `docs/GMAIL_SECURITY_GATE.md`, then follow
`docs/GMAIL_OAUTH_AND_PUBSUB_SETUP.md` before calling `/gmail/watch` or
connecting a Pub/Sub push subscription. No commercial email is sent without a
current approval bound to the exact artifact version and checksum; accepted
scope also requires a persisted same-client/same-thread Gmail message.

## Repository layout

```text
app/                        # ADK entry point, root agent, sub-agents, tools
scopelock/                  # deterministic business code, never agent tools
tests/                      # unit, integration, ADK eval assets
config/                     # validated business SOP
docs/                       # product, architecture, plan, demo documents
evals/                      # human-labelled semantic corpus
```
