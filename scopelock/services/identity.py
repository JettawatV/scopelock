"""Deterministic application identities shared across workflow services."""

import hashlib


def stable_hash(*parts: str) -> str:
    """Hash length-delimited identity parts using one canonical separator."""

    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def stable_id(prefix: str, *parts: str) -> str:
    """Create a readable deterministic identifier with 96 bits of hash data."""

    return f"{prefix}-{stable_hash(*parts)[:24]}"
