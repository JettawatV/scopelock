# ScopeLock — P0 Risk Register

Last reviewed: **2026-08-29**

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
| R-01 | Vertex credentials, project, API, IAM, quota, or model configuration is missing or inconsistent. | ADK cannot run or the demo fails before analysis. | Root `.env` loading, typed settings, and an environment-driven GCP verification script. | Closed 2026-08-28: configured Vertex calls passed the 25-case scope corpus and two trajectory cases; missing-credential failure remains tested. | Days 0–2 | CLOSED |
| R-02 | Gemini varies across runs, omits evidence, skips the SOP tool, or returns an invalid structure. | Unreliable module mapping and judging demo. | Pydantic output schema, bounded prompt, read-only tools, and native ADK eval scaffold. | Closed 2026-08-27: five stable golden runs, reviewed trace, four edge cases, and five passing native ADK evals are recorded in Day 1–2 evidence. | Day 2 | CLOSED |
| R-03 | Client content or prompt injection attempts to override SOP-only mapping, calculate price, mutate state, or send email. | Safety boundary violation or unsupported commercial output. | Agent instructions prohibit commerce, mutation, and sends; tools are read-only. Requirement and Scope Analyzer safety evals plus Day 6 forbidden-action tests pass. | Closed 2026-08-28 for the local agent boundary; hosted integration is rechecked at release. | Days 2 and 6 | CLOSED |
| R-04 | The model invents an SOP module, quantity, USD price, or timeline. | Incorrect proposal and loss of commercial trust. | Validated SOP keys plus strict semantic-versus-deterministic input contracts. Pricing and timeline engines reject model commercial fields. | Closed 2026-08-28: deterministic pricing/timeline tests and 0/10 invalid module selections in the scope corpus. | Days 2–4 | CLOSED |
| R-05 | Gmail, Pub/Sub, retries, or concurrency deliver the same event more than once. | Duplicate projects, events, artifacts, or revisions. | Durable unique keys, message replay records, atomic event leases, and monotonic CAS checkpoints. | Controlled locally on 2026-08-29: replay, active/stale lease, out-of-order, and checkpoint-regression tests pass; live Pub/Sub replay remains required. | Days 10–11 | CONTROLLED |
| R-06 | A send is duplicated or occurs without current explicit approval. | Unauthorized commercial communication. | Agents have no send tool; deterministic approval policy and idempotent non-sending stub pass locally. | Local missing/stale/rejected/repeated tests pass with zero intents; real Gmail replay remains required on Day 12. | Days 6 and 12 | CONTROLLED |
| R-07 | Approval refers to an obsolete artifact after requirements or content changed. | User approves one version but another is sent. | Approval binds artifact ID, version, and SHA-256 checksum. | Local old-checksum test passes; real artifact/Gmail binding remains required on Day 12. | Days 6 and 12 | CONTROLLED |
| R-08 | Accepted scope is overwritten instead of versioned. | Audit history and canonical commercial baseline become unreliable. | Frozen ScopeVersion records and copy-based acceptance/supersession pass unit tests. | In-memory immutability passes; persistence enforcement remains required on Day 10. | Days 4 and 10 | CONTROLLED |
| R-09 | Gmail watch expires, History API checkpoints are lost, or sent/unrelated mailbox changes are processed. | Missed or incorrect scope events. | Persisted renewal/checkpoint state, monotonic updates, bounded history recovery, and deterministic inbound filtering. | Controlled locally on 2026-08-29; live renewal, expired-history recovery, and hosted alert evidence remain required. | Day 11 | CONTROLLED |
| R-10 | Python or dependency drift makes setup non-reproducible or introduces a known vulnerable package. | Local tests pass on one machine but fail for reviewers/deployment, or tooling exposes the host. | Python 3.13 requirement, 152-package lock, compatibility check, and dependency audit. | Closed 2026-08-29: 203 tests pass; pytest upgraded to 9.1.1; final `pip-audit` reports no known vulnerabilities. | Day 0 | CLOSED |
| R-11 | P1 features or frontend work starts before the agent and deterministic workflow gates pass. | P0 reliability drops and hackathon time is lost. | AGENTS.md and the daily plan explicitly lock later phases. | Days 0–14 gates pass before Day 15 begins; no forbidden feature appears in the release diff. | All days | CONTROLLED |
| R-12 | Network, quota, OAuth, cloud configuration, or demo timing fails during judging. | Four-minute demo stalls or cannot prove hosted execution. | Local fixture path is developed first; a fallback recording and runbook are required. | Hosted path passes repeatedly, timed rehearsal completes with margin, and sanitized fallback evidence is ready. | Days 14–17 | OPEN |
| R-13 | Secrets, OAuth tokens, client email content, or credentials enter Git or logs. | Security incident and invalid submission hygiene. | Ignore rules, bounded/symlink-safe OAuth files, Secret Manager path, redacted external errors, and source/filename secret scans. | Local scans pass 2026-08-29; hosted Secret Manager IAM and Cloud Logging review remain required. | Days 0, 11, 14, 17 | CONTROLLED |
| R-14 | A forged webhook or stolen operator key invokes protected workflow or commercial actions. | Unauthorized analysis, approval, send, or scope mutation. | Mandatory Pub/Sub OIDC binding, Cloud Run IAM requirement, 32+ character operator secret, fixed-length comparison, approval/checksum policy, and evidence-bound acceptance. | Automated auth/policy tests pass; hosted IAM negative tests and key rotation remain required. | Days 11–14 | CONTROLLED |
| R-15 | Untrusted/spam email causes prompt injection, resource exhaustion, cost abuse, or data sent to the wrong recipient. | Data leakage, denial of service, unexpected model cost, or misdirected proposal. | Dedicated mailbox plan, pre-model filtering, bounded messages/MIME/context, no attachment content, read-only agents, deterministic commerce, and client/thread-bound drafts. | Local injection/limit/binding tests pass; dedicated mailbox, quota/budget alerts, and hosted log review remain required. | Days 11–14 | CONTROLLED |

## Immediate mitigation checklist

- [x] Keep local secrets and credentials out of tracked files.
- [x] Load Vertex configuration from the root `.env`.
- [x] Enforce typed RequirementAnalysis output.
- [x] Expose only read-only tools to the Requirement Analyzer.
- [x] Complete five golden runs and the four Day 2 edge cases.
- [x] Record the actual get_sop_catalog tool trajectory.
- [x] Validate a fresh Python 3.13 environment and clean dependency install.
- [x] Add application-owned AgentRun and ToolAction evidence.
- [x] Implement strict SOP validation and deterministic USD pricing that rejects model amount fields.
- [x] Implement and test deterministic idempotency and approval services before external sends.
- [x] Complete the automated pre-Gmail security/refactor gate and record scanner/test evidence.
- [ ] Complete the owner-only Gmail/Cloud Run security checklist before activating real events.

## Escalation rule

If R-03, R-04, R-06, R-07, or R-08 fails, stop progression immediately and return to the owning day. Do not work around these failures in prompts, UI code, manual demo steps, or direct cloud-console actions.
