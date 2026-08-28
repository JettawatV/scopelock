"""Runtime configuration shared by ADK agents and application services."""

import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.models import Gemini
from google.genai import types

from scopelock.domain.models import ConfidenceThresholds


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


def agent_generate_config() -> types.GenerateContentConfig:
    """Bound local agent output for repeatable typed development runs."""

    return types.GenerateContentConfig(
        temperature=0,
        max_output_tokens=8192,
        thinking_config=types.ThinkingConfig(
            thinking_level=types.ThinkingLevel.MINIMAL,
        ),
    )


def _confidence_percentage(name: str, default: str) -> int:
    """Accept either an integer percentage or legacy 0-to-1 decimal."""

    value = float(os.getenv(name, default))
    percentage = value * 100 if value <= 1 else value
    if not percentage.is_integer():
        raise ValueError(f"{name} must resolve to a whole percentage")
    return int(percentage)


def scope_confidence_thresholds() -> ConfidenceThresholds:
    """Load configurable semantic-routing thresholds from the environment."""
    return ConfidenceThresholds(
        high=_confidence_percentage("SCOPELOCK_SCOPE_CONFIDENCE_HIGH", "85"),
        medium=_confidence_percentage("SCOPELOCK_SCOPE_CONFIDENCE_MEDIUM", "60"),
        low=_confidence_percentage("SCOPELOCK_SCOPE_CONFIDENCE_LOW", "0"),
    )
