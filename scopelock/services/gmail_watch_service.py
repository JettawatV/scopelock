"""Application-owned Gmail users.watch registration and renewal state."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from scopelock.domain.workflow_models import GmailHistoryCheckpoint, GmailWatchRecord
from scopelock.repositories.contracts import ApplicationRepository
from scopelock.repositories.model_store import CollectionName, ModelStore
from scopelock.security import require_email_address
from scopelock.services.gmail_gateway import GmailGateway
from scopelock.services.identity import stable_id


class GmailWatchConfigurationError(ValueError):
    pass


class GmailWatchService:
    def __init__(
        self,
        *,
        gateway: GmailGateway,
        repository: ApplicationRepository,
        google_cloud_project: str,
    ) -> None:
        self._gateway = gateway
        self._store = ModelStore(repository, use_boundaries=True)
        self._project = google_cloud_project.strip()
        if not self._project or len(self._project) > 64:
            raise GmailWatchConfigurationError("Google Cloud project id is malformed")

    def register(
        self,
        *,
        mailbox: str,
        topic_name: str,
        now: datetime | None = None,
    ) -> GmailWatchRecord:
        observed_at = now or datetime.now(timezone.utc)
        mailbox = require_email_address(mailbox, label="Gmail watch mailbox")
        topic_pattern = re.compile(
            rf"^projects/{re.escape(self._project)}/topics/"
            r"[A-Za-z][A-Za-z0-9._~+%\-]{2,254}$"
        )
        if topic_pattern.fullmatch(topic_name) is None:
            raise GmailWatchConfigurationError(
                "Gmail watch topic must belong to GOOGLE_CLOUD_PROJECT"
            )
        response = self._gateway.watch(mailbox, topic_name=topic_name)
        history_id = str(response.get("historyId") or "")
        expiration_raw = str(response.get("expiration") or "")
        if (
            not history_id
            or len(history_id) > 32
            or not history_id.isdigit()
            or not expiration_raw
            or len(expiration_raw) > 16
            or not expiration_raw.isdigit()
        ):
            raise RuntimeError("Gmail users.watch returned no historyId or expiration")
        expiration = datetime.fromtimestamp(
            int(expiration_raw) / 1000, tz=timezone.utc
        )
        if expiration <= observed_at or expiration > observed_at + timedelta(days=8):
            raise RuntimeError("Gmail users.watch returned an invalid expiration")
        record = GmailWatchRecord(
            id=stable_id("gmail-watch", mailbox),
            mailbox=mailbox,
            topic_name=topic_name,
            history_id=history_id,
            expiration=expiration,
            created_at=observed_at,
        )
        existing = self._store.get(
            CollectionName.GMAIL_WATCHES, record.id, GmailWatchRecord
        )
        if existing is None:
            self._store.create(
                CollectionName.GMAIL_WATCHES,
                record,
                unique_keys={"mailbox": mailbox},
            )
        else:
            self._store.replace(CollectionName.GMAIL_WATCHES, record)

        checkpoint_id = stable_id("gmail-checkpoint", mailbox)
        checkpoint = self._store.get(
            CollectionName.GMAIL_CHECKPOINTS,
            checkpoint_id,
            GmailHistoryCheckpoint,
        )
        if checkpoint is None:
            self._store.create(
                CollectionName.GMAIL_CHECKPOINTS,
                GmailHistoryCheckpoint(
                    id=checkpoint_id,
                    mailbox=mailbox,
                    history_id=history_id,
                    updated_at=observed_at,
                ),
                unique_keys={"mailbox": mailbox},
            )
        return record

    @staticmethod
    def renewal_due(
        record: GmailWatchRecord,
        *,
        now: datetime,
        renew_before: timedelta = timedelta(days=1),
    ) -> bool:
        return record.expiration <= now + renew_before
