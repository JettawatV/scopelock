"""Runtime configuration shared by ADK agents and application services."""

import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.models import Gemini
from google.genai import types


PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Load the project configuration for every entry point, including ADK Web,
# CLI runners, evals, and later FastAPI/Cloud Run processes. Existing shell
# values win so deployed environments can override local development settings.
load_dotenv(PROJECT_ROOT / ".env", override=False)


def project_id() -> str:
    """Return the configured Google Cloud project or fail with a clear message."""
    value = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
    if not value:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT is missing from .env or the runtime environment")
    return value


def model_name() -> str:
    """Return the configured Vertex model without embedding credentials in code."""
    return os.getenv("SCOPELOCK_MODEL", "gemini-3.5-flash")


def build_model() -> Gemini:
    """Create an ADK Gemini model with a small, explicit transient-retry policy."""
    return Gemini(
        model=model_name(),
        retry_options=types.HttpRetryOptions(attempts=3),
    )
