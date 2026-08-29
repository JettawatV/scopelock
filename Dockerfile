# syntax=docker/dockerfile:1.7

FROM python:3.13.15-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project


FROM python:3.13.15-slim-bookworm AS runtime

ENV PATH="/app/.venv/bin:${PATH}" \
    PORT=8080 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    SCOPELOCK_ARTIFACT_ROOT=/tmp/scopelock-artifacts

WORKDIR /app

RUN groupadd --system --gid 10001 scopelock \
    && useradd --system --uid 10001 --gid 10001 --no-create-home \
        --shell /usr/sbin/nologin scopelock

COPY --from=builder --chown=10001:10001 /app/.venv /app/.venv
COPY --chown=10001:10001 app /app/app
COPY --chown=10001:10001 config /app/config
COPY --chown=10001:10001 scopelock /app/scopelock

USER 10001:10001

EXPOSE 8080

CMD ["python", "-m", "scopelock.cloud_run"]
