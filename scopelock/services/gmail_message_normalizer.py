"""Pure Gmail payload normalization before any model is invoked."""

from __future__ import annotations

import base64
import hashlib
import html
import json
import re
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any

from scopelock.domain.enums import EmailBodyFormat, EmailDirection
from scopelock.domain.workflow_models import (
    EmailAttachmentMetadata,
    InboundEmail,
    ThreadMessageContext,
)
from scopelock.security import require_bounded_identifier, require_email_address


CURRENT_BODY_LIMIT = 20_000
PRIOR_MESSAGE_LIMIT = 4_000
PRIOR_MESSAGE_COUNT = 5
MAX_MIME_PARTS = 200
MAX_MIME_DEPTH = 20
MAX_ENCODED_TEXT_PART_LENGTH = 512 * 1024
MAX_ATTACHMENTS = 50
MAX_HEADERS = 200


class _TextExtractor(HTMLParser):
    _VOID_TAGS = frozenset(
        {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._suppressed_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.casefold(): (value or "") for key, value in attrs}
        classes = set(attributes.get("class", "").casefold().split())
        if self._suppressed_depth and tag.casefold() not in self._VOID_TAGS:
            self._suppressed_depth += 1
        elif tag.casefold() in {"script", "style", "blockquote"} or "gmail_quote" in classes:
            self._suppressed_depth = 1

    def handle_endtag(self, tag: str) -> None:
        if self._suppressed_depth:
            self._suppressed_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._suppressed_depth:
            self._parts.append(data)

    def text(self) -> str:
        return " ".join(part.strip() for part in self._parts if part.strip())


def _decode_data(value: str | None) -> str:
    if not value:
        return ""
    if len(value) > MAX_ENCODED_TEXT_PART_LENGTH:
        value = value[:MAX_ENCODED_TEXT_PART_LENGTH]
        value = value[: len(value) - (len(value) % 4)]
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding).decode("utf-8", errors="replace")
    except (ValueError, UnicodeError):
        return ""


def _headers(payload: Mapping[str, Any]) -> dict[str, str]:
    return {
        str(item.get("name", ""))[:128].casefold(): _clean_header(
            str(item.get("value", ""))
        )
        for item in (payload.get("headers", []) or [])[:MAX_HEADERS]
        if isinstance(item, Mapping)
    }


def _walk_parts(payload: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    stack: list[tuple[Mapping[str, Any], int]] = [(payload, 0)]
    observed = 0
    while stack and observed < MAX_MIME_PARTS:
        part, depth = stack.pop()
        observed += 1
        yield part
        if depth >= MAX_MIME_DEPTH:
            continue
        children = part.get("parts", []) or []
        if isinstance(children, list):
            stack.extend(
                (child, depth + 1)
                for child in reversed(children)
                if isinstance(child, Mapping)
            )


def _clean_header(value: str, *, limit: int = 998) -> str:
    cleaned = "".join(" " if ord(character) < 32 else character for character in value)
    return " ".join(cleaned.split())[:limit]


def _html_to_text(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value)
    parser.close()
    return html.unescape(parser.text())


_QUOTED_REPLY_PATTERNS = (
    re.compile(r"(?im)^On .+wrote:\s*$"),
    re.compile(r"(?im)^-{2,}\s*Original Message\s*-{2,}\s*$"),
    re.compile(r"(?im)^_{5,}\s*$"),
)


def strip_quoted_history_and_signature(value: str) -> str:
    """Remove obvious quoted history/signatures while preserving new content."""

    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    cut_at = len(normalized)
    for pattern in _QUOTED_REPLY_PATTERNS:
        match = pattern.search(normalized)
        if match:
            cut_at = min(cut_at, match.start())
    signature = normalized.find("\n-- \n")
    if signature >= 0:
        cut_at = min(cut_at, signature)
    return "\n".join(line.rstrip() for line in normalized[:cut_at].splitlines()).strip()


def _received_at(message: Mapping[str, Any], headers: Mapping[str, str]) -> datetime:
    internal_date = message.get("internalDate")
    if internal_date is not None:
        try:
            return datetime.fromtimestamp(int(str(internal_date)) / 1000, tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            pass
    if headers.get("date"):
        try:
            parsed = parsedate_to_datetime(headers["date"])
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError, OverflowError):
            pass
    return datetime.now(timezone.utc)


def normalize_gmail_message(
    message: Mapping[str, Any],
    *,
    account_email: str | None = None,
) -> InboundEmail:
    """Convert one Gmail API message resource to bounded immutable text."""

    payload = message.get("payload")
    if not isinstance(payload, Mapping):
        payload = {}
    headers = _headers(payload)
    plain_parts: list[str] = []
    html_parts: list[str] = []
    attachments: list[EmailAttachmentMetadata] = []

    for part in _walk_parts(payload):
        mime_type = str(part.get("mimeType", "")).casefold()
        body = part.get("body") if isinstance(part.get("body"), Mapping) else {}
        filename = str(part.get("filename", ""))
        attachment_id = body.get("attachmentId")
        if filename or attachment_id:
            if len(attachments) < MAX_ATTACHMENTS:
                attachments.append(
                    EmailAttachmentMetadata(
                        filename=_clean_header(filename, limit=255),
                        mime_type=(mime_type or "application/octet-stream")[:255],
                        size=min(int(body.get("size") or 0), 50 * 1024 * 1024),
                        attachment_id=(
                            str(attachment_id)[:256] if attachment_id else None
                        ),
                    )
                )
            continue
        decoded = _decode_data(body.get("data"))
        if not decoded:
            continue
        if mime_type == "text/plain":
            plain_parts.append(decoded)
        elif mime_type == "text/html":
            html_parts.append(decoded)

    if plain_parts:
        raw_body = "\n".join(plain_parts)
        body_format = EmailBodyFormat.PLAIN
    elif html_parts:
        raw_body = _html_to_text("\n".join(html_parts))
        body_format = EmailBodyFormat.HTML_FALLBACK
    else:
        raw_body = ""
        body_format = EmailBodyFormat.EMPTY

    body_text = strip_quoted_history_and_signature(raw_body)[:CURRENT_BODY_LIMIT]
    sender_name, parsed_sender_email = parseaddr(headers.get("from", ""))
    try:
        sender_email = require_email_address(
            parsed_sender_email, label="Gmail sender address"
        )
    except ValueError:
        sender_email = ""
    recipients = tuple(
        normalized
        for _, address in getaddresses(
            [headers.get("to", ""), headers.get("cc", "")]
        )
        if address
        for normalized in _validated_email(address)
    )
    normalized_account = account_email.casefold() if account_email else None
    auto_submitted = headers.get("auto-submitted", "").casefold()
    precedence = headers.get("precedence", "").casefold()
    if normalized_account and sender_email == normalized_account:
        direction = EmailDirection.OUTBOUND
    elif (
        not sender_email
        or
        (auto_submitted and auto_submitted != "no")
        or precedence in {"bulk", "junk", "list"}
        or "mailer-daemon" in sender_email
    ):
        direction = EmailDirection.AUTOMATED
    else:
        direction = EmailDirection.INBOUND

    raw_hash = hashlib.sha256(
        json.dumps(message, default=str, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    message_id = require_bounded_identifier(
        str(message.get("id") or ""), label="Gmail message id"
    )
    thread_id = require_bounded_identifier(
        str(message.get("threadId") or ""), label="Gmail thread id"
    )
    return InboundEmail(
        message_id=message_id,
        thread_id=thread_id,
        history_id=str(message.get("historyId")) if message.get("historyId") else None,
        sender_name=_clean_header(sender_name or sender_email, limit=320),
        sender_email=sender_email,
        recipient_emails=recipients,
        subject=headers.get("subject", "").strip(),
        body=body_text,
        received_at=_received_at(message, headers),
        direction=direction,
        body_format=body_format,
        raw_content_hash=raw_hash,
        attachments=tuple(attachments),
    )


def _validated_email(value: str) -> tuple[str, ...]:
    try:
        return (require_email_address(value, label="Gmail recipient address"),)
    except ValueError:
        return ()


def bounded_thread_context(
    messages: Iterable[InboundEmail],
    *,
    current_message_id: str,
) -> tuple[ThreadMessageContext, ...]:
    candidates = sorted(
        (message for message in messages if message.message_id != current_message_id),
        key=lambda item: item.received_at,
        reverse=True,
    )[:PRIOR_MESSAGE_COUNT]
    return tuple(
        ThreadMessageContext(
            message_id=message.message_id,
            direction=message.direction,
            sender_email=message.sender_email,
            subject=message.subject,
            body=message.body[:PRIOR_MESSAGE_LIMIT],
            received_at=message.received_at,
        )
        for message in reversed(candidates)
    )
