"""Shared ADK event parsing with privacy-safe tool trajectory records."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Iterable
from uuid import uuid4

from google.adk.events import Event

from scopelock.domain.models import (
    ToolAction,
    ToolActionPhase,
    ToolActionStatus,
)


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        default=str,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _event_time(event: Event) -> datetime:
    timestamp = getattr(event, "timestamp", None)
    if isinstance(timestamp, (int, float)):
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    return datetime.now(timezone.utc)


def redact_tool_payload(tool_name: str, payload: Any) -> dict[str, Any]:
    """Keep identifiers and shape, never raw bodies or commerce catalog data."""

    summary: dict[str, Any] = {"payload_hash": _canonical_hash(payload)}
    if not isinstance(payload, dict):
        summary["payload_type"] = type(payload).__name__
        return summary
    for key in ("project_id", "scope_version_id", "status", "version"):
        value = payload.get(key)
        if isinstance(value, (str, int, float, bool)) or value is None:
            summary[key] = value
    if tool_name == "get_sop_catalog":
        modules = payload.get("modules")
        if isinstance(modules, list):
            summary["module_keys"] = [
                item.get("key") for item in modules if isinstance(item, dict)
            ]
            summary["module_count"] = len(modules)
    elif tool_name == "get_recent_thread_context":
        messages = payload.get("messages")
        if isinstance(messages, list):
            summary["message_ids"] = [
                item.get("message_id") for item in messages if isinstance(item, dict)
            ]
            summary["message_count"] = len(messages)
    elif tool_name == "get_current_scope":
        requirements = payload.get("requirements")
        if isinstance(requirements, list):
            summary["requirement_ids"] = [
                item.get("requirement_id")
                for item in requirements
                if isinstance(item, dict)
            ]
    return summary


def extract_redacted_tool_actions(
    events: Iterable[Event],
    *,
    agent_run_id: str,
) -> list[ToolAction]:
    actions: list[ToolAction] = []
    call_times: dict[str, datetime] = {}
    sequence = 1
    for event in events:
        if event.content is None:
            continue
        recorded_at = _event_time(event)
        for part in event.content.parts or []:
            function_call = getattr(part, "function_call", None)
            if function_call is not None:
                call_id = function_call.id or event.id or str(uuid4())
                call_times[call_id] = recorded_at
                actions.append(
                    ToolAction(
                        id=str(uuid4()),
                        agent_run_id=agent_run_id,
                        sequence=sequence,
                        call_id=call_id,
                        tool_name=function_call.name or "unknown_tool",
                        phase=ToolActionPhase.CALL,
                        status=ToolActionStatus.REQUESTED,
                        payload=redact_tool_payload(
                            function_call.name or "unknown_tool",
                            function_call.args or {},
                        ),
                        event_id=event.id,
                        author=event.author,
                        recorded_at=recorded_at,
                    )
                )
                sequence += 1

            function_response = getattr(part, "function_response", None)
            if function_response is not None:
                response = function_response.response or {}
                response_error = (
                    response.get("error") if isinstance(response, dict) else None
                )
                call_id = function_response.id or event.id or str(uuid4())
                started_at = call_times.get(call_id)
                duration_ms = None
                if started_at is not None:
                    duration_ms = max(
                        0,
                        int((recorded_at - started_at).total_seconds() * 1000),
                    )
                actions.append(
                    ToolAction(
                        id=str(uuid4()),
                        agent_run_id=agent_run_id,
                        sequence=sequence,
                        call_id=call_id,
                        tool_name=function_response.name or "unknown_tool",
                        phase=ToolActionPhase.RESULT,
                        status=(
                            ToolActionStatus.FAILED
                            if response_error is not None
                            else ToolActionStatus.COMPLETED
                        ),
                        payload=redact_tool_payload(
                            function_response.name or "unknown_tool",
                            response,
                        ),
                        event_id=event.id,
                        author=event.author,
                        recorded_at=recorded_at,
                        duration_ms=duration_ms,
                        error=(
                            str(response_error) if response_error is not None else None
                        ),
                    )
                )
                sequence += 1
    return actions


def final_text_from_events(events: Iterable[Event]) -> str | None:
    final_text: str | None = None
    for event in events:
        if not event.is_final_response() or event.content is None:
            continue
        text_parts = [
            part.text
            for part in event.content.parts or []
            if getattr(part, "text", None)
        ]
        if text_parts:
            final_text = "".join(text_parts)
    return final_text
