"""Runtime configuration shared by ADK agents and application services."""

import os

from google.adk.models import Gemini
from google.genai import types


def model_name() -> str:
    """Return the configured Vertex model without embedding credentials in code."""
    return os.getenv("SCOPELOCK_MODEL", "gemini-3.5-flash")


def build_model() -> Gemini:
    """Create an ADK Gemini model with a small, explicit transient-retry policy."""
    return Gemini(
        model=model_name(),
        retry_options=types.HttpRetryOptions(attempts=3),
    )

