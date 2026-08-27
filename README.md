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

## Development workflow

ScopeLock is developed ADK-first. The current hierarchy is:

```text
ScopeLock (root agent)
└── Requirement Analyzer (active P0 sub-agent)
```

The Scope Analyzer is deliberately not created until the Requirement Analyzer
passes its typed-output, evidence, tool-trajectory, and safety gates. Do not
build frontend UI/UX before those gates pass.

Use native ADK tools from the repository root:

```powershell
adk web . --port 8000 --reload_agents
adk run app
adk eval app tests/eval/requirement_analyzer.evalset.json --print_detailed_results
```

`adk web` should be the main interactive development loop. The local `.adk/`
directory it creates is ignored. The JSONL corpus remains the human-labelled
source set; promote reviewed cases into `tests/eval/` for native ADK runs.

## Repository layout

```text
app/                        # ADK entry point, root agent, sub-agents, tools
scopelock/                  # deterministic business code, never agent tools
tests/                      # unit, integration, ADK eval assets
config/                     # validated business SOP
docs/                       # product, architecture, plan, demo documents
evals/                      # human-labelled semantic corpus
```
