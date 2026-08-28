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

ScopeLock requires Python 3.13. The verified development environment is
`.venv313`; the older `.venv` uses Python 3.11 and is preserved only so an
existing ADK session is not disrupted.

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
2026-08-28 with Python 3.13.14, ADK 2.8.0, Firestore 2.29.0, 144 locked
packages, successful ADK discovery, and 121 passing tests. This uv-managed environment does not require an
embedded `pip` module.

## Development workflow

ScopeLock is developed ADK-first. The current hierarchy is:

```text
ScopeLock (root agent)
├── Requirement Analyzer (typed new-project analysis)
└── Scope Analyzer (typed existing-project change analysis)
```

The Requirement Analyzer gate, 25-case Scope Analyzer corpus, and two native
ADK trajectory cases pass. Frontend UI/UX remains locked until the later cloud
integration gates in `docs/DAILY_IMPLEMENTATION_PLAN.md` pass.

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

## Repository layout

```text
app/                        # ADK entry point, root agent, sub-agents, tools
scopelock/                  # deterministic business code, never agent tools
tests/                      # unit, integration, ADK eval assets
config/                     # validated business SOP
docs/                       # product, architecture, plan, demo documents
evals/                      # human-labelled semantic corpus
```
