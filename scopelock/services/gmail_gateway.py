"""Bounded Gmail API adapter and deterministic same-thread MIME composition."""

from __future__ import annotations

import base64
import re
from collections.abc import Mapping
from email.message import EmailMessage
from typing import Any, Protocol

from scopelock.security import (
    require_bounded_identifier,
    require_email_address,
)
from scopelock.services.execution_boundaries import WorkflowExecutionBoundaries


class GmailFullSyncRequired(RuntimeError):
    """The stored history checkpoint is no longer valid for incremental sync."""


class GmailGateway(Protocol):
    def watch(self, mailbox: str, *, topic_name: str) -> Mapping[str, Any]: ...

    def list_history_page(
        self,
        mailbox: str,
        *,
        start_history_id: str,
        page_token: str | None = None,
    ) -> Mapping[str, Any]: ...

    def get_message(self, mailbox: str, message_id: str) -> Mapping[str, Any]: ...

    def get_thread(self, mailbox: str, thread_id: str) -> Mapping[str, Any]: ...

    def create_draft(
        self, mailbox: str, *, message: Mapping[str, Any]
    ) -> Mapping[str, Any]: ...

    def send_draft(self, mailbox: str, *, draft_id: str) -> Mapping[str, Any]: ...


class GoogleGmailGateway:
    """Thin google-api-python-client wrapper with explicit retry boundaries."""

    def __init__(self, credentials: Any) -> None:
        try:
            from googleapiclient.discovery import build
        except ImportError as error:  # pragma: no cover - dependency guard
            raise RuntimeError("Install google-api-python-client first") from error
        self._service = build(
            "gmail", "v1", credentials=credentials, cache_discovery=False
        )

    def watch(self, mailbox: str, *, topic_name: str) -> Mapping[str, Any]:
        return WorkflowExecutionBoundaries.external_read(
            lambda: self._service.users()
            .watch(
                userId=mailbox,
                body={
                    "topicName": topic_name,
                    "labelIds": ["INBOX"],
                    "labelFilterBehavior": "include",
                },
            )
            .execute()
        )

    def list_history_page(
        self,
        mailbox: str,
        *,
        start_history_id: str,
        page_token: str | None = None,
    ) -> Mapping[str, Any]:
        def operation() -> Mapping[str, Any]:
            try:
                return (
                    self._service.users()
                    .history()
                    .list(
                        userId=mailbox,
                        startHistoryId=start_history_id,
                        historyTypes=["messageAdded"],
                        maxResults=500,
                        pageToken=page_token,
                    )
                    .execute()
                )
            except Exception as error:
                status = getattr(getattr(error, "resp", None), "status", None)
                if status == 404:
                    raise GmailFullSyncRequired(
                        "Gmail history checkpoint expired; a controlled full sync is required"
                    ) from error
                raise

        return WorkflowExecutionBoundaries.external_read(operation)

    def get_message(self, mailbox: str, message_id: str) -> Mapping[str, Any]:
        return WorkflowExecutionBoundaries.external_read(
            lambda: self._service.users()
            .messages()
            .get(userId=mailbox, id=message_id, format="full")
            .execute()
        )

    def get_thread(self, mailbox: str, thread_id: str) -> Mapping[str, Any]:
        return WorkflowExecutionBoundaries.external_read(
            lambda: self._service.users()
            .threads()
            .get(userId=mailbox, id=thread_id, format="full")
            .execute()
        )

    def create_draft(
        self, mailbox: str, *, message: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return WorkflowExecutionBoundaries.external_send(
            lambda: self._service.users()
            .drafts()
            .create(userId=mailbox, body={"message": dict(message)})
            .execute()
        )

    def send_draft(self, mailbox: str, *, draft_id: str) -> Mapping[str, Any]:
        return WorkflowExecutionBoundaries.external_send(
            lambda: self._service.users()
            .drafts()
            .send(userId=mailbox, body={"id": draft_id})
            .execute()
        )


def _headers(message: Mapping[str, Any]) -> dict[str, str]:
    payload = message.get("payload")
    if not isinstance(payload, Mapping):
        return {}
    values = payload.get("headers")
    if not isinstance(values, list):
        return {}
    return {
        str(item.get("name", ""))[:128].casefold(): str(
            item.get("value", "")
        )[:8_192]
        for item in values[:200]
        if isinstance(item, Mapping)
    }


_MESSAGE_ID = re.compile(r"<[^<>\s\r\n]{1,500}@[^<>\s\r\n]{1,255}>")
_ATTACHMENT_NAME = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def build_same_thread_reply(
    *,
    thread_id: str,
    source_message: Mapping[str, Any],
    sender_email: str,
    recipient_email: str,
    text_body: str,
    attachment_name: str,
    attachment_bytes: bytes,
) -> dict[str, str]:
    """Build an RFC reply bound to the exact Gmail thread and source message."""

    thread_id = require_bounded_identifier(thread_id, label="Gmail thread id")
    sender_email = require_email_address(sender_email, label="sender email")
    recipient_email = require_email_address(recipient_email, label="recipient email")
    if sender_email == recipient_email:
        raise ValueError("Commercial email recipient cannot be the sending mailbox")
    if len(text_body) > 20_000:
        raise ValueError("Commercial email body exceeds the safe size limit")
    if len(attachment_bytes) > 5 * 1024 * 1024:
        raise ValueError("Commercial attachment exceeds the safe size limit")
    if _ATTACHMENT_NAME.fullmatch(attachment_name) is None:
        raise ValueError("Commercial attachment name is malformed")

    headers = _headers(source_message)
    subject = headers.get("subject", "").strip()
    source_rfc_id = headers.get("message-id", "").strip()
    if (
        not subject
        or len(subject) > 998
        or "\r" in subject
        or "\n" in subject
        or _MESSAGE_ID.fullmatch(source_rfc_id) is None
    ):
        raise ValueError(
            "Same-thread reply requires Gmail threadId, Subject, and RFC Message-ID"
        )
    prior_references = headers.get("references", "").strip()
    reference_ids = _MESSAGE_ID.findall(prior_references)[-19:]
    if source_rfc_id not in reference_ids:
        reference_ids.append(source_rfc_id)
    references = " ".join(reference_ids)

    email = EmailMessage()
    email["From"] = sender_email
    email["To"] = recipient_email
    email["Subject"] = subject
    email["In-Reply-To"] = source_rfc_id
    email["References"] = references
    email.set_content(text_body)
    email.add_attachment(
        attachment_bytes,
        maintype="application",
        subtype="json",
        filename=attachment_name,
    )
    raw = base64.urlsafe_b64encode(email.as_bytes()).decode("ascii").rstrip("=")
    return {"threadId": thread_id, "raw": raw}
