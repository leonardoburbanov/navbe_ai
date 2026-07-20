"""JSON file-backed secrets provider and store (Cursor-style local credentials)."""

import json
import os
import tempfile
from pathlib import Path

import aiofiles

from navbe.core.exceptions import NotFoundError, ValidationError
from navbe.domains.secrets.interfaces import SecretsProvider
from navbe.domains.secrets.models import validate_secret_key


class JsonFileSecretsProvider:
    """Read/write secrets in a local JSON object ``{ "KEY": "value", ... }``.

    ponytail: plaintext on disk — upgrade: OS keychain / age encryption.
    """

    def __init__(self, path: Path) -> None:
        """Bind this provider to ``path`` (created on first write)."""
        self._path = path

    async def _read(self) -> dict[str, str]:
        """Load the credentials map; empty if the file is missing."""
        if not self._path.exists():
            return {}
        async with aiofiles.open(self._path, encoding="utf-8") as handle:
            raw = await handle.read()
        if not raw.strip():
            return {}
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValidationError(
                "Credentials file must be a JSON object",
                details={"path": str(self._path)},
            )
        out: dict[str, str] = {}
        for key, value in data.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValidationError(
                    "Credentials entries must be string keys and string values",
                    details={"path": str(self._path)},
                )
            out[key] = value
        return out

    async def _write(self, data: dict[str, str]) -> None:
        """Atomically write the credentials map with restrictive permissions."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data, indent=2, sort_keys=True) + "\n"
        fd, tmp_name = tempfile.mkstemp(
            dir=str(self._path.parent),
            prefix=".navbe_creds_",
            suffix=".tmp",
        )
        try:
            os.close(fd)
            async with aiofiles.open(tmp_name, "w", encoding="utf-8") as handle:
                await handle.write(payload)
            os.replace(tmp_name, self._path)
            try:
                os.chmod(self._path, 0o600)
            except OSError:
                # Windows may ignore or reject chmod; best-effort only.
                pass
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)

    async def resolve(self, key: str) -> str:
        """Return the plaintext value for ``key`` from the JSON file."""
        data = await self._read()
        if key not in data:
            raise NotFoundError(
                f"Secret '{key}' not found in credentials file",
                details={
                    "key": key,
                    "hint": "use secret_set or add it to navbe_credentials.json",
                },
            )
        return data[key]

    async def set(self, key: str, value: str) -> None:
        """Create or overwrite ``key``."""
        validate_secret_key(key)
        if value == "":
            raise ValidationError(
                "Secret value must not be empty",
                details={"key": key},
            )
        data = await self._read()
        data[key] = value
        await self._write(data)

    async def delete(self, key: str) -> bool:
        """Remove ``key``. Return True if it existed."""
        validate_secret_key(key)
        data = await self._read()
        if key not in data:
            return False
        del data[key]
        await self._write(data)
        return True

    async def list_keys(self) -> list[str]:
        """Return stored key names only (never values)."""
        data = await self._read()
        return sorted(data.keys())

    async def has(self, key: str) -> bool:
        """True if ``key`` is present in the JSON file."""
        data = await self._read()
        return key in data


class ChainedSecretsProvider:
    """Try providers in order; first successful resolve wins."""

    def __init__(self, providers: list[SecretsProvider]) -> None:
        """Create a chain; each item must implement ``async resolve(key)``."""
        self._providers = list(providers)

    async def resolve(self, key: str) -> str:
        """Resolve ``key`` from the first provider that has it."""
        last_error: NotFoundError | None = None
        for provider in self._providers:
            try:
                return await provider.resolve(key)
            except NotFoundError as exc:
                last_error = exc
        if last_error is not None:
            raise NotFoundError(
                f"Secret '{key}' not found in credentials file or environment",
                details={
                    "key": key,
                    "hint": "use secret_set or define it in .env / export it",
                },
            ) from last_error
        raise NotFoundError(
            f"Secret '{key}' not found",
            details={"key": key, "hint": "no secrets providers configured"},
        )
