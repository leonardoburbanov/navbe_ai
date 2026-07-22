"""Managed GitHub OAuth token store (never via secret_set)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import aiofiles

from navbe.core.exceptions import NotFoundError


class GitHubOAuthStore:
    """Persist GitHub device-flow tokens in a local JSON file.

    File shape (gitignored)::

        {
          "access_token": "...",
          "token_type": "bearer",
          "scope": "repo",
          "login": "octocat",
          "pending": null | { "device_code": "...", "interval": 5, "expires_at": 0 }
        }

    Values are never returned by status APIs — only presence + login.
    """

    def __init__(self, path: Path) -> None:
        """Bind the store to ``path`` under the data home."""
        self._path = path

    @property
    def path(self) -> Path:
        """Absolute path to the oauth JSON file."""
        return self._path

    async def _read(self) -> dict:
        """Load raw JSON or empty dict."""
        if not self._path.exists():
            return {}
        async with aiofiles.open(self._path, encoding="utf-8") as handle:
            raw = await handle.read()
        if not raw.strip():
            return {}
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}

    async def _write(self, data: dict) -> None:
        """Atomic-ish write with best-effort 0600 mode."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        async with aiofiles.open(tmp, "w", encoding="utf-8") as handle:
            await handle.write(json.dumps(data, indent=2) + "\n")
        tmp.replace(self._path)
        try:
            os.chmod(self._path, 0o600)
        except OSError:
            # ponytail: Windows may ignore chmod — upgrade: explicit ACL.
            pass

    async def get_token(self) -> str:
        """Return the access token or raise NotFoundError."""
        data = await self._read()
        token = data.get("access_token")
        if not token or not isinstance(token, str):
            raise NotFoundError(
                "GitHub OAuth token not found",
                details={
                    "hint": "run navbe login github (or auth_github_begin / auth_github_complete)",
                },
            )
        return token

    async def has_token(self) -> bool:
        """True if an access_token is stored."""
        data = await self._read()
        token = data.get("access_token")
        return bool(token and isinstance(token, str))

    async def get_login(self) -> str | None:
        """Return the cached GitHub login name, if any."""
        data = await self._read()
        login = data.get("login")
        return login if isinstance(login, str) and login else None

    async def save_token(
        self,
        *,
        access_token: str,
        token_type: str = "bearer",
        scope: str = "",
        login: str | None = None,
    ) -> None:
        """Persist a completed device-flow token; clear any pending device code."""
        data = await self._read()
        data["access_token"] = access_token
        data["token_type"] = token_type
        data["scope"] = scope
        if login is not None:
            data["login"] = login
        data.pop("pending", None)
        await self._write(data)

    async def clear(self) -> None:
        """Remove token and pending device session."""
        if self._path.exists():
            self._path.unlink()

    async def save_pending(
        self,
        *,
        device_code: str,
        interval: int,
        expires_at: float,
    ) -> None:
        """Store an in-progress device-flow session (device_code never echoed by status)."""
        data = await self._read()
        data["pending"] = {
            "device_code": device_code,
            "interval": interval,
            "expires_at": expires_at,
        }
        await self._write(data)

    async def get_pending(self) -> dict | None:
        """Return pending device session dict, or None."""
        data = await self._read()
        pending = data.get("pending")
        return pending if isinstance(pending, dict) else None

    async def clear_pending(self) -> None:
        """Drop pending device session only."""
        data = await self._read()
        if "pending" not in data:
            return
        data.pop("pending", None)
        await self._write(data)
