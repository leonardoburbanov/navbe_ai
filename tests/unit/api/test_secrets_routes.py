"""Tests for /api/v1/secrets routes (never return values)."""


import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from navbe.api.v1.routes import secrets as secrets_routes
from navbe.core.exceptions import ValidationError
from navbe.dependencies import get_secrets_service
from navbe.domains.secrets.models import CredentialHint, mask_secret


class FakeSecretsService:
    """Minimal secrets service for route tests."""

    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.apps: dict[str, str | None] = {}
        self.set_error: Exception | None = None

    async def set(self, key: str, value: str, *, app: str | None = None) -> CredentialHint:
        if self.set_error is not None:
            raise self.set_error
        resolved_app = app if app is not None else self.apps.get(key)
        self.data[key] = value
        self.apps[key] = resolved_app
        return CredentialHint(
            key=key,
            hint=mask_secret(value),
            app=resolved_app,
            source="store",
        )

    async def delete(self, key: str) -> bool:
        if key not in self.data:
            return False
        del self.data[key]
        self.apps.pop(key, None)
        return True

    async def list_keys(self) -> list[str]:
        return sorted(self.data.keys())

    async def list_credentials(self) -> list[CredentialHint]:
        return [
            CredentialHint(
                key=key,
                hint=mask_secret(self.data[key]),
                app=self.apps.get(key),
                source="store",
            )
            for key in sorted(self.data.keys())
        ]

    async def get_hint(self, key: str) -> CredentialHint:
        from navbe.core.exceptions import NotFoundError

        if key not in self.data:
            raise NotFoundError(f"Secret '{key}' not found", details={"key": key})
        return CredentialHint(
            key=key,
            hint=mask_secret(self.data[key]),
            app=self.apps.get(key),
            source="store",
        )

    async def has(self, key: str) -> bool:
        return key in self.data


@pytest.fixture
def fake_secrets() -> FakeSecretsService:
    return FakeSecretsService()


@pytest.fixture
async def client(fake_secrets: FakeSecretsService):
    app = FastAPI()
    app.include_router(secrets_routes.router, prefix="/api/v1/secrets")
    app.dependency_overrides[get_secrets_service] = lambda: fake_secrets
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_put_list_has_delete(
    client: AsyncClient,
    fake_secrets: FakeSecretsService,
) -> None:
    """PUT stores; GET lists keys + items; has/delete work without echoing values."""
    response = await client.put(
        "/api/v1/secrets/API_KEY",
        json={"value": "sk-hidden", "app": "crm"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["key"] == "API_KEY"
    assert body["stored"] is True
    assert body["hint"] == "****dden"
    assert body["app"] == "crm"
    assert "sk-hidden" not in response.text

    listed = await client.get("/api/v1/secrets")
    assert listed.status_code == 200
    listed_body = listed.json()
    assert listed_body["keys"] == ["API_KEY"]
    assert listed_body["items"][0]["hint"] == "****dden"
    assert listed_body["items"][0]["app"] == "crm"
    assert "sk-hidden" not in listed.text

    hint = await client.get("/api/v1/secrets/API_KEY/hint")
    assert hint.json()["hint"] == "****dden"
    assert hint.json()["source"] == "store"

    has = await client.get("/api/v1/secrets/API_KEY/has")
    assert has.json() == {"key": "API_KEY", "present": True}

    deleted = await client.delete("/api/v1/secrets/API_KEY")
    assert deleted.json() == {"key": "API_KEY", "deleted": True}
    assert fake_secrets.data == {}


async def test_put_invalid_key_returns_422(
    client: AsyncClient,
    fake_secrets: FakeSecretsService,
) -> None:
    """ValidationError maps to HTTP 422."""
    fake_secrets.set_error = ValidationError(
        "Invalid secret key",
        details={"key": "bad-key"},
    )
    response = await client.put("/api/v1/secrets/bad-key", json={"value": "x"})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "validation_error"
