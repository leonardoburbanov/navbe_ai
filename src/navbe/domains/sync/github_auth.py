"""GitHub Device Flow auth and thin REST helpers for sync_connect."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
from pydantic import BaseModel, Field

from navbe.core.exceptions import ConfigurationError, ExecutionError, ValidationError
from navbe.domains.sync.oauth_store import GitHubOAuthStore

# Device Flow endpoints (GitHub.com).
_DEVICE_CODE_URL = "https://github.com/login/device/code"
_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
_API_BASE = "https://api.github.com"

# repo: create/push private+public workspace repos.
DEFAULT_SCOPES = "repo"


class DeviceBeginResult(BaseModel):
    """User-facing device-flow start (never includes device_code or tokens)."""

    user_code: str
    verification_uri: str
    expires_in: int
    interval: int = 5


class GitHubAuthStatus(BaseModel):
    """Presence-only OAuth status (never the token)."""

    logged_in: bool
    login: str | None = None
    pending: bool = False


class GitHubAuthService:
    """Device-flow login against a public OAuth App client_id."""

    def __init__(
        self,
        *,
        store: GitHubOAuthStore,
        client_id: str,
        scopes: str = DEFAULT_SCOPES,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """Create an auth service bound to ``store`` and OAuth ``client_id``."""
        self._store = store
        self._client_id = client_id.strip()
        self._scopes = scopes
        self._http = http_client

    def _require_client_id(self) -> str:
        """Raise if the OAuth App client_id is not configured."""
        if not self._client_id:
            raise ConfigurationError(
                "GitHub OAuth client_id is not configured",
                details={
                    "hint": (
                        "Set NAVBE_GITHUB_OAUTH_CLIENT_ID to a GitHub OAuth App "
                        "client id with Device Flow enabled"
                    ),
                },
            )
        return self._client_id

    async def _client(self) -> httpx.AsyncClient:
        """Return injected client or a short-lived default."""
        if self._http is not None:
            return self._http
        return httpx.AsyncClient(
            headers={"Accept": "application/json", "User-Agent": "navbe"},
            timeout=30.0,
        )

    async def status(self) -> GitHubAuthStatus:
        """Return whether a token is stored (never the token value)."""
        pending = await self._store.get_pending()
        return GitHubAuthStatus(
            logged_in=await self._store.has_token(),
            login=await self._store.get_login(),
            pending=pending is not None,
        )

    async def begin(self) -> DeviceBeginResult:
        """Start device flow; persist device_code locally; return user_code + URI."""
        client_id = self._require_client_id()
        owns_client = self._http is None
        client = await self._client()
        try:
            response = await client.post(
                _DEVICE_CODE_URL,
                data={"client_id": client_id, "scope": self._scopes},
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise ExecutionError(
                "GitHub device-code request failed",
                details={"error": str(exc)},
            ) from exc
        finally:
            if owns_client:
                await client.aclose()

        if "error" in payload:
            raise ExecutionError(
                "GitHub device-code error",
                details={
                    "error": payload.get("error"),
                    "description": payload.get("error_description"),
                },
            )

        device_code = payload["device_code"]
        interval = int(payload.get("interval") or 5)
        expires_in = int(payload.get("expires_in") or 900)
        await self._store.save_pending(
            device_code=device_code,
            interval=interval,
            expires_at=time.time() + expires_in,
        )
        return DeviceBeginResult(
            user_code=payload["user_code"],
            verification_uri=payload.get("verification_uri")
            or payload.get("verification_uri_complete")
            or "https://github.com/login/device",
            expires_in=expires_in,
            interval=interval,
        )

    async def complete(self, *, timeout: float = 300.0) -> GitHubAuthStatus:
        """Poll until the user authorizes, then store the token.

        Uses the pending device_code from ``begin``. Never returns the token.
        """
        client_id = self._require_client_id()
        pending = await self._store.get_pending()
        if not pending or not pending.get("device_code"):
            raise ValidationError(
                "no pending GitHub device login",
                details={"hint": "call auth_github_begin / navbe login github first"},
            )
        device_code = str(pending["device_code"])
        interval = max(int(pending.get("interval") or 5), 1)
        expires_at = float(pending.get("expires_at") or (time.time() + timeout))
        deadline = min(time.time() + timeout, expires_at)

        owns_client = self._http is None
        client = await self._client()
        try:
            while time.time() < deadline:
                try:
                    response = await client.post(
                        _ACCESS_TOKEN_URL,
                        data={
                            "client_id": client_id,
                            "device_code": device_code,
                            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                        },
                        headers={"Accept": "application/json"},
                    )
                    response.raise_for_status()
                    payload = response.json()
                except httpx.HTTPError as exc:
                    raise ExecutionError(
                        "GitHub token poll failed",
                        details={"error": str(exc)},
                    ) from exc

                error = payload.get("error")
                if error is None and payload.get("access_token"):
                    token = str(payload["access_token"])
                    login = await self._fetch_login(client, token)
                    await self._store.save_token(
                        access_token=token,
                        token_type=str(payload.get("token_type") or "bearer"),
                        scope=str(payload.get("scope") or ""),
                        login=login,
                    )
                    return await self.status()

                if error == "authorization_pending":
                    await asyncio.sleep(interval)
                    continue
                if error == "slow_down":
                    interval += 5
                    await asyncio.sleep(interval)
                    continue
                if error in {"expired_token", "access_denied"}:
                    await self._store.clear_pending()
                    raise ValidationError(
                        f"GitHub device login {error}",
                        details={"error": error, "description": payload.get("error_description")},
                    )
                raise ExecutionError(
                    "GitHub device login failed",
                    details={"error": error, "description": payload.get("error_description")},
                )
        finally:
            if owns_client:
                await client.aclose()

        await self._store.clear_pending()
        raise ValidationError(
            "GitHub device login timed out",
            details={"hint": "run navbe login github again"},
        )

    async def logout(self) -> GitHubAuthStatus:
        """Clear the stored token and any pending session."""
        await self._store.clear()
        return await self.status()

    async def get_token(self) -> str:
        """Return the access token for sync (internal use)."""
        return await self._store.get_token()

    async def _fetch_login(self, client: httpx.AsyncClient, token: str) -> str | None:
        """Best-effort fetch of the authenticated username."""
        try:
            response = await client.get(
                f"{_API_BASE}/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            if response.status_code == 200:
                return str(response.json().get("login") or "") or None
        except httpx.HTTPError:
            return None
        return None

    async def ensure_repo(
        self,
        *,
        owner: str,
        name: str,
        private: bool = True,
    ) -> dict[str, Any]:
        """Create ``owner/name`` if missing; return ``{html_url, clone_url, created}``.

        Uses the stored OAuth token. Never returns the token.
        """
        token = await self.get_token()
        owner = owner.strip()
        name = name.strip()
        if not owner or not name:
            raise ValidationError(
                "owner and name are required",
                details={"owner": owner, "name": name},
            )

        owns_client = self._http is None
        client = await self._client()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "navbe",
        }
        try:
            get_resp = await client.get(
                f"{_API_BASE}/repos/{owner}/{name}",
                headers=headers,
            )
            if get_resp.status_code == 200:
                data = get_resp.json()
                return {
                    "html_url": data.get("html_url", ""),
                    "clone_url": data.get("clone_url", f"https://github.com/{owner}/{name}.git"),
                    "full_name": data.get("full_name", f"{owner}/{name}"),
                    "created": False,
                    "private": bool(data.get("private")),
                }
            if get_resp.status_code not in {403, 404}:
                raise ExecutionError(
                    "GitHub get repo failed",
                    details={"status": get_resp.status_code, "body": get_resp.text[:500]},
                )

            # Create under authenticated user or org.
            me = await client.get(f"{_API_BASE}/user", headers=headers)
            me.raise_for_status()
            my_login = str(me.json().get("login") or "")
            body = {
                "name": name,
                "private": private,
                "auto_init": True,
                "description": "Navbe workspace sync (flows + versionable metadata)",
            }
            if owner.lower() == my_login.lower():
                create_resp = await client.post(
                    f"{_API_BASE}/user/repos",
                    headers=headers,
                    json=body,
                )
            else:
                create_resp = await client.post(
                    f"{_API_BASE}/orgs/{owner}/repos",
                    headers=headers,
                    json=body,
                )
            if create_resp.status_code not in {201, 200}:
                raise ExecutionError(
                    "GitHub create repo failed",
                    details={"status": create_resp.status_code, "body": create_resp.text[:500]},
                )
            data = create_resp.json()
            return {
                "html_url": data.get("html_url", ""),
                "clone_url": data.get("clone_url", f"https://github.com/{owner}/{name}.git"),
                "full_name": data.get("full_name", f"{owner}/{name}"),
                "created": True,
                "private": bool(data.get("private", private)),
            }
        except httpx.HTTPError as exc:
            raise ExecutionError(
                "GitHub API request failed",
                details={"error": str(exc)},
            ) from exc
        finally:
            if owns_client:
                await client.aclose()


class AssetChangeSet(BaseModel):
    """Added / updated / removed ids for one workspace asset kind."""

    added: list[str] = Field(default_factory=list)
    updated: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
