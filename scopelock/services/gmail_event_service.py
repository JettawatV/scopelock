"""Authenticated, bounded, and idempotent Gmail History API processing."""

from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import uuid4

from scopelock.domain.enums import InboundProcessingStatus
from scopelock.domain.workflow_models import (
    GmailEventBatchResult,
    GmailHistoryCheckpoint,
    InboundProcessingResult,
)
from scopelock.repositories.contracts import (
    ApplicationRepository,
    DocumentConflictError,
)
from scopelock.repositories.model_store import CollectionName, ModelStore
from scopelock.security import (
    redacted_error,
    require_bounded_identifier,
    require_email_address,
)
from scopelock.services.gmail_gateway import GmailFullSyncRequired, GmailGateway
from scopelock.services.gmail_message_normalizer import (
    bounded_thread_context,
    normalize_gmail_message,
)
from scopelock.services.idempotency_service import IdempotencyKeys
from scopelock.services.identity import stable_id


MAX_NOTIFICATION_DATA_LENGTH = 4_096
MAX_HISTORY_PAGES = 20
MAX_MESSAGES_PER_EVENT = 100
PROCESSING_LEASE = timedelta(minutes=15)
CLAIM_ATTEMPTS = 4


class InboundWorkflow(Protocol):
    async def process(self, email, *, prior_messages=()) -> InboundProcessingResult: ...


class ReadyBufferFinalizer(Protocol):
    def finalize_ready_for_project(
        self, project_id: str, *, finalized_at: datetime
    ) -> object | None: ...


class PubSubEnvelopeError(ValueError):
    pass


class GmailEventInProgress(RuntimeError):
    """A valid retry arrived while another worker still owns the event."""


class GmailEventLimitExceeded(RuntimeError):
    """A mailbox delta exceeded the bounded automatic-processing policy."""


def decode_gmail_notification(
    envelope: Mapping[str, Any],
) -> tuple[str, str, str]:
    message = envelope.get("message")
    if not isinstance(message, Mapping):
        raise PubSubEnvelopeError("Pub/Sub envelope has no message object")
    event_value = message.get("messageId") or message.get("message_id")
    encoded_value = message.get("data")
    if not isinstance(event_value, str) or not isinstance(encoded_value, str):
        raise PubSubEnvelopeError("Pub/Sub messageId and data are required")
    try:
        event_id = require_bounded_identifier(
            event_value, label="Pub/Sub messageId"
        )
    except ValueError as error:
        raise PubSubEnvelopeError(str(error)) from error
    encoded = encoded_value.strip()
    if not encoded or len(encoded) > MAX_NOTIFICATION_DATA_LENGTH:
        raise PubSubEnvelopeError("Pub/Sub data is empty or oversized")
    try:
        padding = "=" * (-len(encoded) % 4)
        decoded = base64.b64decode(
            encoded + padding, altchars=b"-_", validate=True
        ).decode("utf-8")
        payload = json.loads(decoded)
    except (ValueError, UnicodeError, json.JSONDecodeError) as error:
        raise PubSubEnvelopeError("Pub/Sub data is not valid base64url JSON") from error
    if not isinstance(payload, Mapping):
        raise PubSubEnvelopeError("Pub/Sub data must contain a JSON object")
    mailbox_value = str(payload.get("emailAddress") or "").strip()
    history_id = str(payload.get("historyId") or "").strip()
    if (
        len(history_id) > 32
        or not history_id.isdigit()
    ):
        raise PubSubEnvelopeError(
            "Gmail notification requires a bounded emailAddress and numeric historyId"
        )
    try:
        mailbox = require_email_address(
            mailbox_value, label="Gmail notification emailAddress"
        )
    except ValueError as error:
        raise PubSubEnvelopeError(str(error)) from error
    return event_id, mailbox, history_id


class GmailEventService:
    def __init__(
        self,
        *,
        gateway: GmailGateway,
        workflow: InboundWorkflow,
        repository: ApplicationRepository,
        mailbox: str,
        ready_buffer_finalizer: ReadyBufferFinalizer | None = None,
    ) -> None:
        self._gateway = gateway
        self._workflow = workflow
        self._store = ModelStore(repository, use_boundaries=True)
        self._mailbox = require_email_address(mailbox, label="Gmail event mailbox")
        self._ready_buffer_finalizer = ready_buffer_finalizer

    async def process_pubsub(
        self,
        envelope: Mapping[str, Any],
        *,
        received_at: datetime | None = None,
    ) -> GmailEventBatchResult:
        now = received_at or datetime.now(timezone.utc)
        event_id, mailbox, notification_history_id = decode_gmail_notification(
            envelope
        )
        if mailbox != self._mailbox:
            raise PubSubEnvelopeError("Notification mailbox does not match configuration")

        event_key = IdempotencyKeys.pubsub_event(event_id)
        event_document_id = stable_id("pubsub-event", event_id)
        prior = self._event(event_document_id)
        if prior is not None and prior.status not in {"FAILED", "PROCESSING"}:
            return prior.model_copy(update={"replayed": True})

        checkpoint = self._checkpoint(mailbox)
        if int(notification_history_id) <= int(checkpoint.history_id):
            result = GmailEventBatchResult(
                id=event_document_id,
                pubsub_message_id=event_id,
                mailbox=mailbox,
                notification_history_id=notification_history_id,
                start_history_id=checkpoint.history_id,
                checkpoint_history_id=checkpoint.history_id,
                status="IGNORED_OUT_OF_ORDER",
                created_at=prior.created_at if prior else now,
                completed_at=now,
            )
            return self._persist_terminal(result, event_key, now=now)

        attempt_id = uuid4().hex
        processing = GmailEventBatchResult(
            id=event_document_id,
            pubsub_message_id=event_id,
            mailbox=mailbox,
            notification_history_id=notification_history_id,
            start_history_id=checkpoint.history_id,
            status="PROCESSING",
            processing_attempt_id=attempt_id,
            lease_expires_at=now + PROCESSING_LEASE,
            created_at=prior.created_at if prior else now,
        )
        claimed = self._claim_processing(processing, event_key, now=now)
        if claimed.status != "PROCESSING":
            return claimed.model_copy(update={"replayed": True})

        try:
            message_ids, final_history_id = await asyncio.to_thread(
                self._list_message_ids,
                mailbox,
                checkpoint.history_id,
                notification_history_id,
            )
            result_ids: list[str] = []
            for message_id in message_ids:
                raw = await asyncio.to_thread(
                    self._gateway.get_message, mailbox, message_id
                )
                current = normalize_gmail_message(raw, account_email=mailbox)
                thread = await asyncio.to_thread(
                    self._gateway.get_thread, mailbox, current.thread_id
                )
                prior_raw_messages = self._bounded_prior_resources(
                    thread.get("messages", []), current_resource=raw
                )
                normalized_prior = tuple(
                    normalize_gmail_message(item, account_email=mailbox)
                    for item in prior_raw_messages
                )
                outcome = await self._workflow.process(
                    current,
                    prior_messages=bounded_thread_context(
                        normalized_prior, current_message_id=current.message_id
                    ),
                )
                if outcome.status == InboundProcessingStatus.FAILED:
                    raise RuntimeError(
                        f"Inbound workflow returned FAILED for message {message_id}"
                    )
                result_ids.append(outcome.idempotency_key)
                if (
                    self._ready_buffer_finalizer is not None
                    and outcome.project_id is not None
                    and outcome.status
                    == InboundProcessingStatus.SCOPE_EVENTS_RECORDED
                ):
                    await asyncio.to_thread(
                        self._ready_buffer_finalizer.finalize_ready_for_project,
                        outcome.project_id,
                        finalized_at=now,
                    )

            advanced = self._advance_checkpoint(
                mailbox, final_history_id=final_history_id, updated_at=now
            )
            completed = processing.model_copy(
                update={
                    "status": "COMPLETED",
                    "checkpoint_history_id": advanced.history_id,
                    "gmail_message_ids": tuple(message_ids),
                    "processing_result_ids": tuple(result_ids),
                    "lease_expires_at": None,
                    "completed_at": now,
                }
            )
            return self._replace_owned(completed, attempt_id=attempt_id)
        except (GmailFullSyncRequired, GmailEventLimitExceeded) as error:
            failed = processing.model_copy(
                update={
                    "status": "FULL_SYNC_REQUIRED",
                    "error": redacted_error(error, operation="gmail history sync"),
                    "lease_expires_at": None,
                    "completed_at": now,
                }
            )
            return self._replace_owned(failed, attempt_id=attempt_id)
        except Exception as error:
            failed = processing.model_copy(
                update={
                    "status": "FAILED",
                    "error": redacted_error(error, operation="gmail event processing"),
                    "lease_expires_at": None,
                    "completed_at": now,
                }
            )
            self._replace_owned(failed, attempt_id=attempt_id)
            raise

    def _checkpoint(self, mailbox: str) -> GmailHistoryCheckpoint:
        checkpoint = self._store.find_by_unique_key(
            CollectionName.GMAIL_CHECKPOINTS,
            key_name="mailbox",
            key_value=mailbox,
            model_type=GmailHistoryCheckpoint,
        )
        if checkpoint is None:
            raise RuntimeError(
                "No Gmail history checkpoint exists; register users.watch first"
            )
        return checkpoint

    def _advance_checkpoint(
        self,
        mailbox: str,
        *,
        final_history_id: str,
        updated_at: datetime,
    ) -> GmailHistoryCheckpoint:
        if len(final_history_id) > 32 or not final_history_id.isdigit():
            raise RuntimeError("Gmail History API returned an invalid historyId")
        checkpoint_id = stable_id("gmail-checkpoint", mailbox)
        for _ in range(CLAIM_ATTEMPTS):
            document = self._store.get_document(
                CollectionName.GMAIL_CHECKPOINTS, checkpoint_id
            )
            if document is None:
                raise RuntimeError("Gmail history checkpoint disappeared")
            current = GmailHistoryCheckpoint.model_validate(document.payload)
            if int(final_history_id) <= int(current.history_id):
                return current
            advanced = current.model_copy(
                update={"history_id": final_history_id, "updated_at": updated_at}
            )
            try:
                stored = self._store.replace(
                    CollectionName.GMAIL_CHECKPOINTS,
                    advanced,
                    expected_revision=document.revision,
                )
                return GmailHistoryCheckpoint.model_validate(stored.payload)
            except DocumentConflictError:
                continue
        raise RuntimeError("Could not advance Gmail checkpoint after concurrent updates")

    def _list_message_ids(
        self, mailbox: str, start_history_id: str, notification_history_id: str
    ) -> tuple[tuple[str, ...], str]:
        page_token: str | None = None
        seen_page_tokens: set[str] = set()
        seen: set[str] = set()
        ordered: list[str] = []
        final_history_id = notification_history_id
        for _ in range(MAX_HISTORY_PAGES):
            page = self._gateway.list_history_page(
                mailbox,
                start_history_id=start_history_id,
                page_token=page_token,
            )
            for history in page.get("history", []) or []:
                if not isinstance(history, Mapping):
                    continue
                for added in history.get("messagesAdded", []) or []:
                    if not isinstance(added, Mapping):
                        continue
                    message = added.get("message")
                    if not isinstance(message, Mapping):
                        continue
                    message_id = str(message.get("id") or "").strip()
                    if not message_id or message_id in seen:
                        continue
                    try:
                        require_bounded_identifier(
                            message_id, label="Gmail message id"
                        )
                    except ValueError as error:
                        raise GmailEventLimitExceeded(str(error)) from error
                    seen.add(message_id)
                    ordered.append(message_id)
                    if len(ordered) > MAX_MESSAGES_PER_EVENT:
                        raise GmailEventLimitExceeded(
                            "Gmail event exceeds the automatic message batch limit"
                        )
            candidate_history_id = str(page.get("historyId") or final_history_id)
            if (
                len(candidate_history_id) > 32
                or not candidate_history_id.isdigit()
            ):
                raise RuntimeError("Gmail History API returned an invalid historyId")
            final_history_id = candidate_history_id
            next_page = str(page.get("nextPageToken") or "").strip() or None
            if next_page is None:
                return tuple(ordered), final_history_id
            if next_page in seen_page_tokens or len(next_page) > 1_024:
                raise GmailEventLimitExceeded(
                    "Gmail History API returned an invalid pagination sequence"
                )
            seen_page_tokens.add(next_page)
            page_token = next_page
        raise GmailEventLimitExceeded("Gmail event exceeds the history page limit")

    @staticmethod
    def _bounded_prior_resources(
        resources: object,
        *,
        current_resource: Mapping[str, Any],
    ) -> tuple[Mapping[str, Any], ...]:
        if not isinstance(resources, list):
            return ()
        current_id = str(current_resource.get("id") or "")
        try:
            current_time = int(str(current_resource.get("internalDate") or 0))
        except ValueError:
            current_time = 0
        candidates: list[tuple[int, Mapping[str, Any]]] = []
        for item in resources:
            if not isinstance(item, Mapping) or str(item.get("id") or "") == current_id:
                continue
            try:
                observed = int(str(item.get("internalDate") or 0))
            except ValueError:
                observed = 0
            if current_time and observed > current_time:
                continue
            candidates.append((observed, item))
        selected = sorted(candidates, key=lambda pair: pair[0], reverse=True)[:5]
        return tuple(item for _, item in reversed(selected))

    def _event(self, document_id: str) -> GmailEventBatchResult | None:
        document = self._store.get_document(CollectionName.PUBSUB_EVENTS, document_id)
        return (
            GmailEventBatchResult.model_validate(document.payload)
            if document is not None
            else None
        )

    def _claim_processing(
        self,
        desired: GmailEventBatchResult,
        event_key: str,
        *,
        now: datetime,
    ) -> GmailEventBatchResult:
        for _ in range(CLAIM_ATTEMPTS):
            document = self._store.get_document(
                CollectionName.PUBSUB_EVENTS, desired.id
            )
            if document is None:
                try:
                    stored = self._store.create(
                        CollectionName.PUBSUB_EVENTS,
                        desired,
                        unique_keys={"pubsub_event_id": event_key},
                    )
                except DocumentConflictError:
                    continue
                claimed = GmailEventBatchResult.model_validate(stored.payload)
                if claimed.processing_attempt_id == desired.processing_attempt_id:
                    return claimed
                continue
            current = GmailEventBatchResult.model_validate(document.payload)
            if (
                current.pubsub_message_id != desired.pubsub_message_id
                or current.mailbox != desired.mailbox
                or current.notification_history_id
                != desired.notification_history_id
            ):
                raise PubSubEnvelopeError(
                    "Pub/Sub messageId was replayed with different Gmail data"
                )
            if current.status not in {"FAILED", "PROCESSING"}:
                return current
            if (
                current.status == "PROCESSING"
                and current.lease_expires_at is not None
                and current.lease_expires_at > now
            ):
                raise GmailEventInProgress("Pub/Sub event is already processing")
            reclaimed = desired.model_copy(update={"created_at": current.created_at})
            try:
                stored = self._store.replace(
                    CollectionName.PUBSUB_EVENTS,
                    reclaimed,
                    expected_revision=document.revision,
                )
                return GmailEventBatchResult.model_validate(stored.payload)
            except DocumentConflictError:
                continue
        raise GmailEventInProgress("Could not acquire the Pub/Sub processing lease")

    def _replace_owned(
        self,
        event: GmailEventBatchResult,
        *,
        attempt_id: str,
    ) -> GmailEventBatchResult:
        document = self._store.get_document(CollectionName.PUBSUB_EVENTS, event.id)
        if document is None:
            raise RuntimeError("Pub/Sub processing record disappeared")
        current = GmailEventBatchResult.model_validate(document.payload)
        if current.processing_attempt_id != attempt_id:
            raise GmailEventInProgress("Pub/Sub processing lease is no longer owned")
        stored = self._store.replace(
            CollectionName.PUBSUB_EVENTS,
            event,
            expected_revision=document.revision,
        )
        return GmailEventBatchResult.model_validate(stored.payload)

    def _persist_terminal(
        self,
        event: GmailEventBatchResult,
        event_key: str,
        *,
        now: datetime,
    ) -> GmailEventBatchResult:
        for _ in range(CLAIM_ATTEMPTS):
            document = self._store.get_document(CollectionName.PUBSUB_EVENTS, event.id)
            if document is None:
                try:
                    stored = self._store.create(
                        CollectionName.PUBSUB_EVENTS,
                        event,
                        unique_keys={"pubsub_event_id": event_key},
                    )
                    return GmailEventBatchResult.model_validate(stored.payload)
                except DocumentConflictError:
                    continue
            current = GmailEventBatchResult.model_validate(document.payload)
            if (
                current.pubsub_message_id != event.pubsub_message_id
                or current.mailbox != event.mailbox
                or current.notification_history_id
                != event.notification_history_id
            ):
                raise PubSubEnvelopeError(
                    "Pub/Sub messageId was replayed with different Gmail data"
                )
            if (
                current.status == "PROCESSING"
                and current.lease_expires_at is not None
                and current.lease_expires_at > now
            ):
                raise GmailEventInProgress("Pub/Sub event is already processing")
            if current.status not in {"FAILED", "PROCESSING"}:
                return current.model_copy(update={"replayed": True})
            try:
                stored = self._store.replace(
                    CollectionName.PUBSUB_EVENTS,
                    event.model_copy(update={"created_at": current.created_at}),
                    expected_revision=document.revision,
                )
                return GmailEventBatchResult.model_validate(stored.payload)
            except DocumentConflictError:
                continue
        raise GmailEventInProgress("Could not persist the Pub/Sub terminal result")
