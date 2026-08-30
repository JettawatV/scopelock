"""Redacted structured events for Cloud Logging and local diagnostics."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping
from enum import Enum
from typing import Any


LOGGER_NAME = "scopelock.events"
LOGGER = logging.getLogger(LOGGER_NAME)

_EVENT_NAME = re.compile(r"^[a-z][a-z0-9_.-]{2,100}$")
_ALLOWED_FIELDS = frozenset(
    {
        "action",
        "agent_run_id",
        "approval_id",
        "artifact_id",
        "collection",
        "correlation_id",
        "duration_ms",
        "entity_id",
        "entity_type",
        "error_ref",
        "from_status",
        "method",
        "path",
        "project_id",
        "record_id",
        "request_id",
        "retryable",
        "send_id",
        "status",
        "status_code",
        "to_status",
        "tool_action_id",
    }
)
_MAX_VALUE_LENGTH = 256


def configure_structured_logging() -> None:
    """Emit one raw JSON object per ScopeLock event on process stderr."""

    if LOGGER.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False


def structured_event_payload(event: str, **fields: object) -> dict[str, object]:
    """Build a low-cardinality event while rejecting raw or secret-like fields."""

    if _EVENT_NAME.fullmatch(event) is None:
        raise ValueError("Structured event name is malformed")

    payload: dict[str, object] = {"event": event, "severity": "INFO"}
    for key, value in fields.items():
        if key not in _ALLOWED_FIELDS:
            raise ValueError(f"Structured event field is not allowed: {key}")
        normalized = _normalize_value(value)
        if normalized is not None:
            payload[key] = normalized
    return payload


def emit_structured_event(event: str, **fields: object) -> None:
    """Write a redacted JSON event suitable for Cloud Logging parsing."""

    payload = structured_event_payload(event, **fields)
    LOGGER.info(json.dumps(payload, separators=(",", ":"), sort_keys=True))


def persistence_event_fields(
    collection: str,
    model: object,
) -> dict[str, object]:
    """Extract only safe references from a typed persisted record."""

    fields: dict[str, object] = {"collection": collection}
    field_names = (
        "id",
        "correlation_id",
        "project_id",
        "agent_run_id",
        "artifact_id",
        "approval_id",
        "send_id",
        "entity_id",
        "entity_type",
        "action",
        "status",
        "from_status",
        "to_status",
    )
    aliases = {"id": "record_id"}
    for field_name in field_names:
        value = getattr(model, field_name, None)
        if value is not None:
            fields[aliases.get(field_name, field_name)] = value

    if collection == "tool_actions" and "record_id" in fields:
        fields["tool_action_id"] = fields["record_id"]
    if collection == "approvals" and "record_id" in fields:
        fields["approval_id"] = fields["record_id"]
    if collection in {"sends", "gmail_send_results"} and "record_id" in fields:
        fields["send_id"] = fields["record_id"]
    return fields


def _normalize_value(value: object) -> str | int | float | bool | None:
    if value is None:
        return None
    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized or len(normalized) > _MAX_VALUE_LENGTH:
            return None
        if "\r" in normalized or "\n" in normalized:
            return None
        return normalized
    return None
