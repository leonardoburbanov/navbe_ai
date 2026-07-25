"""JSON file-backed secrets provider and store (Cursor-style local credentials)."""

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiofiles

from navbe.core.exceptions import NotFoundError, ValidationError
from navbe.domains.secrets.models import CredentialRecord, validate_app, validate_secret_key


class JsonFileSecretsProvider:
    """Read/write secrets in a local JSON object (string or record per key).

    ponytail: plaintext on disk — upgrade: OS keychain / age encryption.
    """

    def __init__(self, path: Path) -> None:
        """Bind this provider to ``path`` (created on first write)."""
        self._path = path

    def _parse_entry(self, key: str, raw: Any) -> CredentialRecord:
        """Normalize a legacy string or record object into ``CredentialRecord``."""
        if isinstance(raw, str):
            if raw == "":
                raise ValidationError(
                    "Credentials entries must not have empty values",
                    details={"path": str(self._path), "key": key},
                )
            return CredentialRecord(value=raw)
        if isinstance(raw, dict):
            value = raw.get("value")
            if not isinstance(value, str) or value == "":
                raise ValidationError(
                    "Credential record must include a non-empty string value",
                    details={"path": str(self._path), "key": key},
                )
            app = raw.get("app")
            if app is not None and not isinstance(app, str):
                raise ValidationError(
                    "Credential record app must be a string or null",
                    details={"path": str(self._path), "key": key},
                )
            updated_at = raw.get("updated_at")
            if updated_at is not None and not isinstance(updated_at, str):
                raise ValidationError(
                    "Credential record updated_at must be an ISO string or null",
                    details={"path": str(self._path), "key": key},
                )
            record_data: dict[str, Any] = {"value": value, "app": app}
            if updated_at is not None:
                record_data["updated_at"] = updated_at
            return CredentialRecord.model_validate(record_data)
        raise ValidationError(
            "Credentials entries must be strings or record objects",
            details={"path": str(self._path), "key": key},
        )

    async def _read_records(self) -> dict[str, CredentialRecord]:
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
        out: dict[str, CredentialRecord] = {}
        for key, value in data.items():
            if not isinstance(key, str):
                raise ValidationError(
                    "Credentials entries must be string keys",
                    details={"path": str(self._path)},
                )
            out[key] = self._parse_entry(key, value)
        return out

    def _serialize_records(self, data: dict[str, CredentialRecord]) -> dict[str, Any]:
        """Serialize records for disk (always record shape)."""
        payload: dict[str, Any] = {}
        for key, record in data.items():
            entry: dict[str, Any] = {"value": record.value}
            if record.app is not None:
                entry["app"] = record.app
            if record.updated_at is not None:
                entry["updated_at"] = record.updated_at.isoformat()
            payload[key] = entry
        return payload

    async def _write_records(self, data: dict[str, CredentialRecord]) -> None:
        """Atomically write the credentials map with restrictive permissions."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            self._serialize_records(data),
            indent=2,
            sort_keys=True,
        ) + "\n"
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
        data = await self._read_records()
        if key not in data:
            raise NotFoundError(
                f"Secret '{key}' not found in credentials file",
                details={
                    "key": key,
                    "hint": "use secret_set or add it to navbe_credentials.json",
                },
            )
        return data[key].value

    async def set(self, key: str, value: str, *, app: str | None = None) -> None:
        """Create or overwrite ``key`` as a credential record."""
        validate_secret_key(key)
        if value == "":
            raise ValidationError(
                "Secret value must not be empty",
                details={"key": key},
            )
        if app is not None:
            validate_app(app)
        data = await self._read_records()
        existing = data.get(key)
        resolved_app = app if app is not None else (existing.app if existing else None)
        data[key] = CredentialRecord(
            value=value,
            app=resolved_app,
            updated_at=datetime.now(UTC),
        )
        await self._write_records(data)

    async def delete(self, key: str) -> bool:
        """Remove ``key``. Return True if it existed."""
        validate_secret_key(key)
        data = await self._read_records()
        if key not in data:
            return False
        del data[key]
        await self._write_records(data)
        return True

    async def list_keys(self) -> list[str]:
        """Return stored key names only (never values)."""
        data = await self._read_records()
        return sorted(data.keys())

    async def has(self, key: str) -> bool:
        """True if ``key`` is present in the JSON file."""
        data = await self._read_records()
        return key in data

    async def get_record(self, key: str) -> CredentialRecord | None:
        """Return the stored record for ``key``, or None if missing."""
        data = await self._read_records()
        return data.get(key)

    async def list_records(self) -> dict[str, CredentialRecord]:
        """Return all stored records keyed by secret name."""
        return await self._read_records()
