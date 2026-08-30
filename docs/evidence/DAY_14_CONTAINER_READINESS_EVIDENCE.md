# Day 14 container-readiness evidence

Date: 2026-08-29

## Implemented

- Multi-stage `Dockerfile` pinned to Python 3.13.15 slim Bookworm and uv 0.11.28.
- Locked production dependency installation with no project/dev install in the
  builder environment.
- Non-root runtime user `10001:10001`.
- Fail-closed `scopelock.cloud_run` entry point with bounded `PORT`, exact
  project/topic binding, same-project push identity, HTTPS audience, Vertex
  mode, hosted token presence/size, and operator-key checks.
- `/health` does not initialize Gmail OAuth, Gmail API, or Firestore.
- Cloud Run diagnostic renders are directed to ephemeral `/tmp`; reviewed send
  bytes remain reconstructed from immutable Firestore-owned commercial data.
- Explicit `.dockerignore` and `.gcloudignore` runtime whitelists.

## Automated verification

```powershell
.\.venv313\Scripts\python.exe -m pytest -q
```

Result: **203 passed**, 0 failed. Two dependency deprecation warnings remain and
are unrelated to the deployment security boundary.

Additional checks:

- Container/startup contract tests: `tests/unit/test_cloud_run_deployment.py`.
- Python compile and `git diff --check`: pass.
- Bandit over `scopelock` and `app`: **0 unsuppressed findings**. The one narrow
  `B104` suppression documents Cloud Run's required `0.0.0.0` bind.
- `pip-audit`: **no known vulnerabilities**; local package `scopelock` is
  correctly skipped because it is not a PyPI release.
- `uv pip check`: **150 installed packages compatible**.
- Google API key, OAuth access/refresh token, and private-key signature scan:
  **0 matching files** outside ignored local `.env`/environments.
- Repository sensitive-filename scan: **0 matches**.

## Cloud Build upload audit

`gcloud meta list-files-for-upload` was run against `.gcloudignore`. The final
upload list contains only:

- `.dockerignore`, `Dockerfile`, `pyproject.toml`, and `uv.lock`;
- runtime `app/` Python files, excluding `app/.adk` session/eval state;
- `config/jvl_sop.example.yaml`;
- runtime `scopelock/` Python files, excluding `scopelock/testing`.

It excludes `.env`, OAuth/token/client files, service-account files, ADK local
state, virtual environments, artifacts, tests, docs, scripts, legacy backend
code, and Git metadata.

## Remaining live gate

Docker is not installed on this workstation, so no local Linux image build was
claimed. The first actual build must run in Cloud Build, followed by Artifact
Registry inspection, private Cloud Run deployment, Secret Manager/IAM review,
hosted negative authentication checks, and log review. `users.watch` remains
disabled.
