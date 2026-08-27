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
- `docs/HACKATHON_REQUIREMENTS.md` — concise guardrails; official uploaded rules override it
- `docs/DEMO_GOLDEN_PATH.md` — one scenario the entire build should optimize around
- `config/jvl_sop.example.yaml` — illustrative machine-readable SOP
- `evals/scopelock_eval_cases.jsonl` — 25 starter semantic eval cases
- `app/agent.py` — ADK-native `ScopeLock` root agent
- `app/sub_agents/requirement_analyzer.py` — first active sub-agent
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
2026-08-27 with Python 3.13.14, ADK 2.8.0, 107 locked packages, successful ADK
discovery, and 14 passing tests. This uv-managed environment does not require an
embedded `pip` module.

## Development workflow

ScopeLock is developed ADK-first. The current hierarchy is:

```text
ScopeLock (root agent)
└── Requirement Analyzer (active P0 sub-agent)
```

The Scope Analyzer is deliberately not created until the Requirement Analyzer
passes its typed-output, evidence, tool-trajectory, and safety gates. Do not
build frontend UI/UX before those gates pass.

The ADK app selector displays `app` because that name must match the
discoverable `app/` package. The root agent inside it is named `scopelock`.

After activating `.venv313`, use native ADK tools from the repository root:

```powershell
adk web . --port 8000 --no-reload
adk run app
adk eval app tests/eval/requirement_analyzer.evalset.json `
  --config_file_path tests/eval/requirement_analyzer.config.json `
  --print_detailed_results
```

`adk web` should be the main interactive development loop. The local `.adk/`
directory it creates is ignored. The JSONL corpus remains the human-labelled
source set; promote reviewed cases into `tests/eval/` for native ADK runs.

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
