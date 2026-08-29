"""Small security primitives shared by external adapters and HTTP surfaces."""

from __future__ import annotations

import hashlib
import logging
import re
from email.utils import parseaddr


LOGGER = logging.getLogger("scopelock.security")

MAX_API_REQUEST_BYTES = 64 * 1024
MAX_IDENTIFIER_LENGTH = 256
MIN_OPERATOR_KEY_LENGTH = 32
MAX_BEARER_TOKEN_LENGTH = 16 * 1024

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9._:@/+\-=]+$")


def require_bounded_identifier(value: str, *, label: str) -> str:
    """Reject control characters and oversized external identifiers."""

    normalized = value.strip()
    if (
        not normalized
        or len(normalized) > MAX_IDENTIFIER_LENGTH
        or _SAFE_IDENTIFIER.fullmatch(normalized) is None
    ):
        raise ValueError(f"{label} is malformed")
    return normalized


def require_email_address(value: str, *, label: str) -> str:
    """Validate one plain mailbox address without accepting display-name input."""

    normalized = value.strip().casefold()
    parsed = parseaddr(normalized)[1].casefold()
    if (
        not normalized
        or len(normalized) > 320
        or "\r" in normalized
        or "\n" in normalized
        or parsed != normalized
        or "@" not in normalized
    ):
        raise ValueError(f"{label} is malformed")
    return normalized


def error_reference(error: BaseException) -> str:
    material = f"{type(error).__module__}.{type(error).__name__}:{error}"
    return hashlib.sha256(material.encode("utf-8", errors="replace")).hexdigest()[:12]


def redacted_error(error: BaseException, *, operation: str) -> str:
    """Return a diagnosable error reference without persisting untrusted text."""

    reference = error_reference(error)
    LOGGER.error(
        "%s failed error_type=%s error_ref=%s",
        operation,
        type(error).__name__,
        reference,
    )
    return f"{operation} failed; reference={reference}"
