# ScopeLock — Implementation Plan

## Rule

Build the **vertical golden path first**. Do not build by layer for days without an end-to-end flow.

---

## Phase 0 — Freeze and scaffold

Deliverables:
- monorepo/repo structure;
- environment config;
- Firestore collections;
- domain enums/models;
- SOP schema + loader;
- architecture diagram draft;
- initial eval corpus;
- Gemini/Vertex connectivity;
- ADK agent skeleton.

Exit criterion:
A local test can pass an email-like string to Requirement Analyzer and receive valid typed output.

---

## Phase 1 — Intelligence + deterministic commerce

Build:
- Requirement Analyzer;
- Scope Analyzer;
- SOP module validation;
- PricingEngine;
- TimelineEngine;
- Proposal data model;
- 20+ eval cases;
- deterministic unit tests.

Exit criterion:
Given:
1. current scope,
2. new email,
3. SOP,

the system reliably returns:
- classification;
- evidence;
- mapped module;
- deterministic delta.

Do not build UI polish before this works.

---

## Phase 2 — Gmail autonomous trigger

Implementation state: **CODE COMPLETE; LIVE GOOGLE CONFIGURATION PENDING.**

Build:
- Google OAuth setup;
- Gmail `users.watch`;
- Pub/Sub topic + push subscription;
- `/webhooks/gmail`;
- History API resolution;
- inbound message parser;
- dedicated demo mailbox;
- Gmail message idempotency.

Exit criterion:
Sending an email to demo mailbox causes a new Firestore project/event without manually opening ScopeLock.

---

## Phase 3 — Proposal approval and send

Implementation state: **CODE COMPLETE; LIVE SAME-THREAD SEND PENDING.**

Build:
- proposal generator;
- artifact storage;
- user review endpoint/UI;
- approve/reject;
- Gmail draft/send;
- same-thread reply;
- audit events.

Exit criterion:
Inbound requirement email -> generated proposal -> user approval -> Gmail reply with proposal.

---

## Phase 4 — Scope Buffer and revision

Implementation state: **CODE COMPLETE; LIVE THREAD ACCEPTANCE PATH PENDING.**

Build:
- project/thread continuation detection;
- ScopeEvent persistence;
- ScopeBuffer;
- 20-minute quiet-window metadata;
- semantic closure detection;
- manual finalize;
- proposal revision before acceptance;
- change order after acceptance;
- stale-draft invalidation if new client message arrives.

Exit criterion:
Two rapid client scope additions become one consolidated commercial revision.

---

## Phase 5 — Evals, feedback, hardening

Build:
- eval dashboard;
- ADK eval / trajectory test;
- correction action;
- lightweight user policy memory;
- regression run;
- retries/timeouts;
- idempotent send replay test;
- Cloud Run deployment;
- Cloud Logging/Trace visibility.

Exit criterion:
System has measured quality + safe production behavior, not only a successful demo.

---

## Phase 6 — Submission polish

Feature freeze.

Only:
- fix bugs;
- improve UI clarity;
- architecture diagram;
- README spin-up instructions;
- Devpost description;
- 4-minute demo;
- Google Cloud proof;
- optional LinkedIn/social post.

Do not add integrations.

---

## P0 / P1

### P0
- Gmail text body
- autonomous event
- initial proposal
- SOP pricing
- review/approval/send
- ongoing scope classification
- scope buffer
- price/timeline delta
- proposal revision/change order
- audit trail
- eval metrics
- Cloud Run/Firestore/Pub/Sub

### P1 only if P0 is reliable
- PDF attachment requirement ingestion
- richer user-policy memory
- Cloud Scheduler watch renewal
- better PDF styling
- additional eval visualization

### Post-hackathon
- Slack/Teams/WhatsApp
- Drive/Docs
- CRM
- multi-user/multi-tenant
- billing
- full project management
