# Day 15 — Frontend implementation evidence

Recorded: **2026-08-30**

Status: **IMPLEMENTATION AND HOSTED ROUTES VERIFIED; FRESH-REVIEWER FLOW STILL OPEN**

## Implemented surface

- Added a Vite 7.3.6 static React SPA with TypeScript and Tailwind.
- Added three deliberately narrow operator views: overview/action required, project scope and commercial history, and agent-readiness evidence.
- Added authenticated, bounded read endpoints for the dashboard and project detail.
- Reused the existing policy-checked approval, rejection, revision, draft, send, and scope-buffer finalization endpoints for every mutation.
- Kept pricing, timeline, state transitions, idempotency, approval, and sending rules in application services.
- Packaged the static frontend and FastAPI-compatible service in one Cloud Run container while keeping their source boundaries separate.

## Security and data-boundary evidence

- The operator API key is held only in React memory and is cleared on disconnect; it is not written to local storage, session storage, cookies, URLs, or the static build.
- The optional operator identity is stored separately in session storage and is not an authorization credential.
- Dashboard projections exclude raw email bodies, model output, input hashes, Gmail message contents, tool payloads, OAuth material, commercial catalog internals, and credentials.
- Demo mode is visibly labelled and disables all mutation and external-action controls.
- The frontend uses same-origin API calls, no third-party scripts, no raw HTML rendering, and a same-origin Content Security Policy.
- Approval and send remain separate actions, and send requires a second confirmation in the UI plus the existing backend approval/checksum policy.

## Verification recorded

| Check | Result |
| --- | --- |
| Focused API, projection, static-hosting, deployment, and Vite contract tests | `17 passed` |
| Frontend type check | Passed |
| Vite production build | Passed for the SPA entrypoint and client routes `/`, `/projects/`, and `/evals` |
| Frontend dependency audit | `0 vulnerabilities` |
| Full Python suite | `212 passed` |
| Docker packaging contract tests | Passed; local image build unavailable because Docker is not installed on this workstation |
| Fresh Vite desktop visual review | Passed for overview, projects, and agent readiness; no console errors observed |
| Fresh Vite narrow visual review | Passed at 390 × 1000 with no horizontal overflow |
| Live Cloud Run deployment of the combined image | Authorized requests returned `200` for `/health`, `/`, `/projects`, and `/evals`; see `docs/evidence/DAY_14_HOSTED_ROUTE_EVIDENCE.md` |

## Remaining Day 15 gate

- Have a fresh reviewer identify the required action, trace the module/price evidence, and complete an approval flow without explanation.
- Record hosted screenshots and usability notes.

The real Gmail `users.watch` activation remains held. This frontend work does not authorize Gmail event delivery or email sending.
