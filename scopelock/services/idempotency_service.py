"""Canonical unique-key construction for external and commercial identities."""

import hashlib


def _key(namespace: str, *parts: str) -> str:
    normalized = "\x1f".join((namespace, *parts))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class IdempotencyKeys:
    @staticmethod
    def gmail_message(message_id: str) -> str:
        return _key("gmail_message", message_id)

    @staticmethod
    def gmail_thread(thread_id: str) -> str:
        return _key("gmail_thread", thread_id)

    @staticmethod
    def gmail_history(mailbox: str, history_id: str) -> str:
        return _key("gmail_history", mailbox, history_id)

    @staticmethod
    def pubsub_event(event_id: str) -> str:
        return _key("pubsub_event", event_id)

    @staticmethod
    def artifact_version(project_id: str, artifact_type: str, version: int) -> str:
        return _key("artifact_version", project_id, artifact_type, str(version))

    @staticmethod
    def approval(artifact_id: str, version: int, checksum: str) -> str:
        return _key("approval", artifact_id, str(version), checksum)

    @staticmethod
    def send_action(artifact_id: str, version: int, checksum: str, thread_id: str) -> str:
        return _key("send_action", artifact_id, str(version), checksum, thread_id)
