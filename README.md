# ScopeLock Coding-Agent Context Pack

This pack is intended to be uploaded into an AI coding agent together with the official hackathon rules/guidelines.

Start with `AGENTS.md`.

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

## One-line product

ScopeLock turns an inbound client email into an SOP-aligned proposal for review, sends it after approval, and then autonomously monitors the Gmail thread for commercially meaningful scope changes.
