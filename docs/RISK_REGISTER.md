# ScopeLock — P0 Risk Register

Last reviewed: **2026-08-27**

## Purpose

This register tracks risks that can break the frozen Gmail-to-proposal-to-scope-revision demo or violate ScopeLock's safety rules. A risk remains open until its listed exit evidence is recorded. Any risk involving approval bypass, duplicate commercial sends, invented commercial values, or mutable accepted scope is release-blocking.

## Status meanings

- **OPEN** — controls or evidence are incomplete.
- **CONTROLLED** — preventive controls exist, but the release evidence is not complete.
- **CLOSED** — the exit evidence passed and is linked.
- **BLOCKING** — current failure prevents work from advancing past its owning gate.

## Active risks

| ID | Risk and trigger | Impact | Current control | Required exit evidence | Owner gate | Status |
| --- | --- | --- | --- | --- | --- | --- |
| R-01 | Vertex credentials, project, API, IAM, quota, or model configuration is missing or inconsistent. | ADK cannot run or the demo fails before analysis. | Root `.env` loading, typed settings, and an environment-driven GCP verification script. | Successful configured-project model call plus missing-credential failure test. | Days 0–2 | CONTROLLED |
| R-02 | Gemini varies across runs, omits evidence, skips the SOP tool, or returns an invalid structure. | Unreliable module mapping and judging demo. | Pydantic output schema, bounded prompt, read-only tools, and native ADK eval scaffold. | Five stable golden runs, reviewed tool trace, edge-case suite, and native eval result. | Day 2 | OPEN |
| R-03 | Client content or prompt injection attempts to override SOP-only mapping, calculate price, mutate state, or send email. | Safety boundary violation or unsupported commercial output. | Agent instructions prohibit commerce, mutation, and sends; tools are read-only. | Prompt-injection eval proves the boundaries remain intact. | Days 2 and 6 | OPEN |
| R-04 | The model invents an SOP module, quantity, USD price, or timeline. | Incorrect proposal and loss of commercial trust. | Validated SOP keys and a strict semantic-versus-deterministic boundary. | Invalid-module eval plus deterministic pricing/timeline tests proving model totals are ignored. | Days 2–4 | OPEN |
| R-05 | Gmail, Pub/Sub, retries, or concurrency deliver the same event more than once. | Duplicate projects, events, artifacts, or revisions. | Idempotency is a frozen architecture requirement. | Replay and concurrent-delivery tests produce one canonical result. | Days 10–11 | OPEN |
| R-06 | A send is duplicated or occurs without current explicit approval. | Unauthorized commercial communication. | Agents have no send tool; planned deterministic approval and send policy. | Missing/stale/rejected approval tests and repeated-send test show zero unauthorized or duplicate sends. | Days 6 and 12 | OPEN |
| R-07 | Approval refers to an obsolete artifact after requirements or content changed. | User approves one version but another is sent. | Planned artifact version and checksum binding. | Editing invalidates prior approval; only the approved checksum can be sent. | Days 6 and 12 | OPEN |
| R-08 | Accepted scope is overwritten instead of versioned. | Audit history and canonical commercial baseline become unreliable. | Immutable baseline is a frozen domain rule. | Unit and persistence tests prove accepted ScopeVersion records cannot be edited in place. | Days 4 and 10 | OPEN |
| R-09 | Gmail watch expires, History API checkpoints are lost, or sent/unrelated mailbox changes are processed. | Missed or incorrect scope events. | Planned watch renewal, persisted history checkpoint, and inbound-message filtering. | Renewal, checkpoint recovery, same-thread, and unrelated-message tests pass. | Day 11 | OPEN |
| R-10 | Python or dependency drift makes setup non-reproducible. | Local tests pass on one machine but fail for reviewers or deployment. | `pyproject.toml` requires Python 3.13, package discovery is limited to active code, and `uv.lock` pins 107 packages. | Closed 2026-08-27: `.venv313` installed and locked successfully with Python 3.13.14; ADK discovery passed; current 14-test suite passed. | Day 0 | CLOSED |
| R-11 | P1 features or frontend work starts before the agent and deterministic workflow gates pass. | P0 reliability drops and hackathon time is lost. | AGENTS.md and the daily plan explicitly lock later phases. | Days 0–14 gates pass before Day 15 begins; no forbidden feature appears in the release diff. | All days | CONTROLLED |
| R-12 | Network, quota, OAuth, cloud configuration, or demo timing fails during judging. | Four-minute demo stalls or cannot prove hosted execution. | Local fixture path is developed first; a fallback recording and runbook are required. | Hosted path passes repeatedly, timed rehearsal completes with margin, and sanitized fallback evidence is ready. | Days 14–17 | OPEN |
| R-13 | Secrets, OAuth tokens, client email content, or credentials enter Git or logs. | Security incident and invalid submission hygiene. | Secret-safe ignore rules and planned structured/sanitized logs. | Tracked-file secret scan and hosted log review pass with no sensitive values. | Days 0, 11, 14, 17 | CONTROLLED |

## Immediate mitigation checklist

- [x] Keep local secrets and credentials out of tracked files.
- [x] Load Vertex configuration from the root `.env`.
- [x] Enforce typed RequirementAnalysis output.
- [x] Expose only read-only tools to the Requirement Analyzer.
- [ ] Complete five golden runs and the four Day 2 edge cases.
- [x] Record the actual get_sop_catalog tool trajectory.
- [x] Validate a fresh Python 3.13 environment and clean dependency install.
- [x] Add application-owned AgentRun and ToolAction evidence.
- [ ] Implement and test deterministic idempotency and approval services before external sends.

## Escalation rule

If R-03, R-04, R-06, R-07, or R-08 fails, stop progression immediately and return to the owning day. Do not work around these failures in prompts, UI code, manual demo steps, or direct cloud-console actions.
