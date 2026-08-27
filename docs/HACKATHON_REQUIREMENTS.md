# ScopeLock — Hackathon Guardrails

## Source of truth

This file is a working summary.

**The official hackathon Rules, Overview, FAQ, and Submission Checklist provided by the user are authoritative and override this document.**

The coding agent must not reinterpret official requirements.

---

## Category

**Taskmaster**

Reason:
ScopeLock intercepts a real work event and completes a multi-step background workflow rather than acting as a chat-only assistant.

---

## Mandatory technology requirements

The project must use:

1. **Gemini 3.5 or newer**
2. At least one Google agent framework:
   - ScopeLock uses **Google ADK**
3. At least one Google Cloud infrastructure service:
   - ScopeLock uses **Cloud Run, Firestore, and Pub/Sub**

---

## New-project constraint

The submitted project must be newly created during the hackathon submission period.

Standard frameworks/libraries/AI coding assistants are allowed subject to the official rules.

Disclose pre-existing work/code where required.

Do not copy an existing JVL product into the submission and present it as newly built.

JVL is the **problem context / SOP example**, not pre-existing ScopeLock code.

---

## Judging focus to optimize for

### Innovation & Operational Utility — 40%
ScopeLock should prove:
- real-world friction;
- unique personal/business-context friction;
- autonomous multi-step execution;
- action rather than chat.

### Architectural Discipline & Tech Stack — 30%
ScopeLock should show:
- clean module boundaries;
- persistent state;
- deterministic vs probabilistic separation;
- secure/scoped tools;
- failure tolerance;
- idempotency;
- evaluation.

### Demo & Production Readiness — 30%
ScopeLock should show:
- unambiguous live execution;
- Cloud Run / Google Cloud proof;
- state changes/logs/UI;
- clean architecture diagram;
- reproducible README.

---

## Submission constraints to remember

- Select one category.
- Hosted project is highly encouraged.
- Repository required.
- README must contain spin-up instructions.
- Architecture diagram required.
- Demo video must be public and <= 4 minutes.
- Demo should show Google Cloud backend execution.
- English required (or English translation/subtitles).
- Include project description, technologies, data sources, findings/learnings.
- Disclose third-party/pre-existing code as required.

---

## Demo optimization rule

The first 10–15 seconds should show ScopeLock working, not a long title screen.

Show one strong scenario.

Do not spend video time on:
- account setup;
- OAuth screens;
- typing long requirements live;
- feature tours;
- repeated examples.

---

## Optional bonus work

Only after submission-critical work is done:
- public build write-up;
- social post with required hackathon hashtag;
- additional qualifying Google AI model integration if useful.

Do not add an extra model solely for bonus points if it risks the core demo.
