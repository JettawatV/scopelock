"""Least-privilege Gmail OAuth credential bootstrap and loading."""

from __future__ import annotations

import argparse
import json
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scopelock.settings import PROJECT_ROOT


GMAIL_OAUTH_SCOPES = (
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
)
MAX_OAUTH_JSON_BYTES = 64 * 1024


def _configured_path(name: str, default: str) -> Path:
    value = os.getenv(name, default).strip()
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


@dataclass(frozen=True)
class GmailOAuthConfig:
    client_secret_path: Path
    token_path: Path
    token_json: str | None = field(default=None, repr=False)
    scopes: tuple[str, ...] = GMAIL_OAUTH_SCOPES

    @classmethod
    def from_env(cls) -> "GmailOAuthConfig":
        return cls(
            client_secret_path=_configured_path(
                "SCOPELOCK_GMAIL_CLIENT_SECRET_PATH", "secrets/client_secret.json"
            ),
            token_path=_configured_path(
                "SCOPELOCK_GMAIL_TOKEN_PATH", "secrets/gmail_token.json"
            ),
            token_json=os.getenv("SCOPELOCK_GMAIL_TOKEN_JSON", "").strip() or None,
        )


class GmailCredentialProvider:
    """Load, refresh, or interactively create one offline OAuth credential."""

    def __init__(self, config: GmailOAuthConfig | None = None) -> None:
        self.config = config or GmailOAuthConfig.from_env()
        if self.config.client_secret_path == self.config.token_path:
            raise ValueError("OAuth client and token paths must be different")

    def load(self) -> Any:
        if self.config.token_json is None and not self.config.token_path.exists():
            raise RuntimeError(
                "Gmail OAuth token is missing. Run `scopelock-gmail-auth` once."
            )
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
        except ImportError as error:  # pragma: no cover - dependency guard
            raise RuntimeError("Install the project Gmail dependencies first") from error

        token_payload = (
            self._parse_json_secret(
                self.config.token_json, label="Gmail token secret"
            )
            if self.config.token_json is not None
            else self._read_json_file(
                self.config.token_path, label="Gmail token file"
            )
        )
        credentials = (
            Credentials.from_authorized_user_info(
                token_payload, list(self.config.scopes)
            )
        )
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            if self.config.token_json is None:
                self._write_token(credentials.to_json())
        if not credentials.valid:
            raise RuntimeError(
                "Stored Gmail credentials are invalid. Run `scopelock-gmail-auth` again."
            )
        self._validate_scopes(credentials)
        return credentials

    def _validate_scopes(self, credentials: Any) -> None:
        required = set(self.config.scopes)
        granted = set(credentials.scopes or ())
        missing = required - granted
        if missing:
            raise RuntimeError(
                "Stored Gmail token is missing required scopes: "
                + ", ".join(sorted(missing))
            )
        unexpected = granted - required
        if unexpected:
            raise RuntimeError(
                "Stored Gmail token has unexpected scopes. Reauthorize with the "
                "ScopeLock least-privilege scope set."
            )

    def authorize_local(self) -> Any:
        if not self.config.client_secret_path.exists():
            raise RuntimeError(
                f"OAuth client file not found: {self.config.client_secret_path}"
            )
        client_config = self._read_json_file(
            self.config.client_secret_path, label="OAuth client file"
        )
        if not isinstance(client_config.get("installed"), dict):
            raise RuntimeError(
                "OAuth client file must contain a Desktop app credential"
            )
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError as error:  # pragma: no cover - dependency guard
            raise RuntimeError("Install the project Gmail dependencies first") from error

        flow = InstalledAppFlow.from_client_config(
            client_config, list(self.config.scopes)
        )
        credentials = flow.run_local_server(
            port=0,
            access_type="offline",
            prompt="consent",
            open_browser=True,
        )
        self._validate_scopes(credentials)
        self._write_token(credentials.to_json())
        return credentials

    def _write_token(self, token_json: str) -> None:
        self.config.token_path.parent.mkdir(parents=True, exist_ok=True)
        if self.config.token_path.is_symlink():
            raise RuntimeError("Refusing to overwrite a symlinked Gmail token file")
        parsed = self._parse_json_secret(token_json, label="Gmail token")
        temporary = self.config.token_path.with_suffix(
            self.config.token_path.suffix + ".tmp"
        )
        if temporary.is_symlink():
            raise RuntimeError("Refusing to overwrite a symlinked temporary token file")
        temporary.write_text(
            json.dumps(parsed, separators=(",", ":")), encoding="utf-8"
        )
        os.chmod(temporary, stat.S_IRUSR | stat.S_IWUSR)
        temporary.replace(self.config.token_path)

    @staticmethod
    def _parse_json_secret(value: str, *, label: str) -> dict[str, Any]:
        if len(value.encode("utf-8")) > MAX_OAUTH_JSON_BYTES:
            raise RuntimeError(f"{label} exceeds the safe size limit")
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"{label} is not valid JSON") from error
        if not isinstance(parsed, dict):
            raise RuntimeError(f"{label} must contain a JSON object")
        return parsed

    @classmethod
    def _read_json_file(cls, path: Path, *, label: str) -> dict[str, Any]:
        if path.is_symlink():
            raise RuntimeError(f"Refusing to load a symlinked {label.casefold()}")
        if path.stat().st_size > MAX_OAUTH_JSON_BYTES:
            raise RuntimeError(f"{label} exceeds the safe size limit")
        return cls._parse_json_secret(path.read_text(encoding="utf-8"), label=label)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Authorize ScopeLock to read Gmail and create/send approved drafts."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate the stored token without opening a browser.",
    )
    args = parser.parse_args()
    provider = GmailCredentialProvider()
    provider.load() if args.check else provider.authorize_local()
    print(f"Gmail OAuth credential ready at {provider.config.token_path}")


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
