"""GitHub App Device Flow auth and thin REST helpers for sync_connect."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
from pydantic import BaseModel, Field

from navbe.core.config import DEFAULT_GITHUB_APP_SLUG
from navbe.core.exceptions import ConfigurationError, ExecutionError, ValidationError
from navbe.domains.sync.oauth_store import GitHubOAuthStore

# Device Flow endpoints (GitHub.com).
_DEVICE_CODE_URL = "https://github.com/login/device/code"
_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
_API_BASE = "https://api.github.com"

# Refresh when fewer than this many seconds remain on the access token.
_REFRESH_SKEW_SECONDS = 300.0


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    """Parse JSON body or return an empty dict."""
    try:
        data = response.json()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _github_error_details(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract GitHub OAuth error fields for Navbe exceptions."""
    return {
        "error": payload.get("error"),
        "description": payload.get("error_description"),
        "error_uri": payload.get("error_uri"),
    }


def _device_flow_http_error(
    response: httpx.Response,
    payload: dict[str, Any],
) -> ExecutionError:
    """Build a clear ExecutionError for failed device-code / token requests."""
    details = _github_error_details(payload)
    details["status"] = response.status_code
    error_code = str(payload.get("error") or "")
    if error_code == "device_flow_disabled" or (
        response.status_code == 400 and not error_code
    ):
        details["hint"] = (
            "Enable Device Flow on the GitHub App: "
            "Settings → Developer settings → GitHub Apps → Navbe AI → "
            "Optional features → Device Flow"
        )
        return ExecutionError(
            "GitHub Device Flow is disabled for this app",
            details=details,
        )
    if payload.get("error_description"):
        return ExecutionError(
            f"GitHub device-code request failed: {payload.get('error_description')}",
            details=details,
        )
    return ExecutionError(
        "GitHub device-code request failed",
        details={**details, "body": response.text[:500]},
    )


class DeviceBeginResult(BaseModel):
    """User-facing device-flow start (never includes device_code or tokens)."""

    user_code: str
    verification_uri: str
    expires_in: int
    interval: int = 5


class GitHubAuthStatus(BaseModel):
    """Presence-only GitHub App auth status (never the token)."""

    logged_in: bool
    login: str | None = None
    pending: bool = False
    app_installed: bool | None = None
    install_url: str | None = None
    uninstall_url: str | None = None
    configure_url: str | None = None


class GitHubRepoRef(BaseModel):
    """A repository the installed GitHub App can access (never tokens)."""

    full_name: str
    owner: str
    name: str
    private: bool = False
    html_url: str = ""
    clone_url: str = ""


class GitHubAuthService:
    """Device-flow login against a public GitHub App client_id (no client secret)."""

    def __init__(
        self,
        *,
        store: GitHubOAuthStore,
        client_id: str,
        app_slug: str = DEFAULT_GITHUB_APP_SLUG,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """Create an auth service bound to ``store`` and GitHub App ``client_id``."""
        self._store = store
        self._client_id = client_id.strip()
        self._app_slug = (app_slug or DEFAULT_GITHUB_APP_SLUG).strip() or DEFAULT_GITHUB_APP_SLUG
        self._http = http_client

    @property
    def install_url(self) -> str:
        """URL to install the GitHub App on a user or org account."""
        return f"https://github.com/apps/{self._app_slug}/installations/new"

    @property
    def installations_list_url(self) -> str:
        """GitHub settings page listing installed apps (uninstall from here)."""
        return "https://github.com/settings/installations"

    def _require_client_id(self) -> str:
        """Raise if the GitHub App client_id is not configured."""
        if not self._client_id:
            raise ConfigurationError(
                "GitHub App client_id is not configured",
                details={
                    "hint": (
                        "Set NAVBE_GITHUB_APP_CLIENT_ID to a GitHub App client id "
                        "with Device Flow enabled"
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
        logged_in = await self._store.has_token()
        login = await self._store.get_login()
        app_installed: bool | None = None
        install_url: str | None = None
        uninstall_url: str | None = self.installations_list_url
        configure_url: str | None = None
        if logged_in:
            try:
                installation = await self._get_installation()
                app_installed = installation is not None
                if installation is not None:
                    inst_id = installation.get("id")
                    if inst_id is not None:
                        configure_url = (
                            f"https://github.com/settings/installations/{inst_id}"
                        )
                        uninstall_url = configure_url
                else:
                    install_url = self.install_url
            except Exception:
                app_installed = None
        return GitHubAuthStatus(
            logged_in=logged_in,
            login=login,
            pending=pending is not None,
            app_installed=app_installed,
            install_url=install_url,
            uninstall_url=uninstall_url,
            configure_url=configure_url,
        )

    async def begin(self) -> DeviceBeginResult:
        """Start device flow; persist device_code locally; return user_code + URI.

        GitHub Apps do not use OAuth ``scope`` — permissions come from the app.
        """
        client_id = self._require_client_id()
        owns_client = self._http is None
        client = await self._client()
        try:
            response = await client.post(
                _DEVICE_CODE_URL,
                data={"client_id": client_id},
                headers={"Accept": "application/json"},
            )
            payload = _safe_json(response)
            if response.status_code >= 400:
                raise _device_flow_http_error(response, payload)
            if "error" in payload:
                raise ExecutionError(
                    "GitHub device-code error",
                    details=_github_error_details(payload),
                )
        except ExecutionError:
            raise
        except httpx.HTTPError as exc:
            raise ExecutionError(
                "GitHub device-code request failed",
                details={"error": str(exc)},
            ) from exc
        finally:
            if owns_client:
                await client.aclose()

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
        """Poll until the user authorizes, then store access + refresh tokens.

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
                    await self._persist_token_payload(payload, login=login)
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
                        details={
                            "error": error,
                            "description": payload.get("error_description"),
                        },
                    )
                raise ExecutionError(
                    "GitHub device login failed",
                    details={
                        "error": error,
                        "description": payload.get("error_description"),
                    },
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
        """Return a valid access token, refreshing if near expiry."""
        return await self.get_valid_token()

    async def get_valid_token(self) -> str:
        """Return access token, refreshing via refresh_token when needed.

        Device-flow refresh does not require a client secret.
        """
        if not await self._store.has_token():
            raise ConfigurationError(
                "GitHub App token not found",
                details={
                    "hint": "run navbe login github (or auth_github_begin / auth_github_complete)",
                },
            )
        if not await self._store.access_token_expiring_soon(skew_seconds=_REFRESH_SKEW_SECONDS):
            return await self._store.get_token()

        refresh = await self._store.get_refresh_token()
        if not refresh:
            # Non-expiring or legacy store without refresh — use access token as-is.
            return await self._store.get_token()

        client_id = self._require_client_id()
        owns_client = self._http is None
        client = await self._client()
        try:
            response = await client.post(
                _ACCESS_TOKEN_URL,
                data={
                    "client_id": client_id,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh,
                },
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            await self._store.clear()
            raise ConfigurationError(
                "GitHub token refresh failed",
                details={
                    "hint": "run navbe login github again",
                    "error": str(exc),
                },
            ) from exc
        finally:
            if owns_client:
                await client.aclose()

        if payload.get("error") or not payload.get("access_token"):
            await self._store.clear()
            raise ConfigurationError(
                "GitHub token refresh failed",
                details={
                    "hint": "run navbe login github again",
                    "error": payload.get("error"),
                    "description": payload.get("error_description"),
                },
            )

        login = await self._store.get_login()
        await self._persist_token_payload(payload, login=login)
        return str(payload["access_token"])

    async def _persist_token_payload(
        self,
        payload: dict[str, Any],
        *,
        login: str | None,
    ) -> None:
        """Save access/refresh tokens and expiry fields from a token response."""
        expires_in = payload.get("expires_in")
        refresh_expires_in = payload.get("refresh_token_expires_in")
        await self._store.save_token(
            access_token=str(payload["access_token"]),
            token_type=str(payload.get("token_type") or "bearer"),
            scope=str(payload.get("scope") or ""),
            login=login,
            refresh_token=(
                str(payload["refresh_token"]) if payload.get("refresh_token") else None
            ),
            expires_in=int(expires_in) if expires_in is not None else None,
            refresh_token_expires_in=(
                int(refresh_expires_in) if refresh_expires_in is not None else None
            ),
            token_kind="github_app",
        )

    async def _get_installation(self) -> dict[str, Any] | None:
        """Return the first installation of this app for the user, if any."""
        token = await self._store.get_token()
        owns_client = self._http is None
        client = await self._client()
        try:
            response = await client.get(
                f"{_API_BASE}/user/installations",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            if response.status_code in {401, 403}:
                return None
            response.raise_for_status()
            data = response.json()
            installations = data.get("installations") if isinstance(data, dict) else None
            if not installations or not isinstance(installations, list):
                return None
            first = installations[0]
            return first if isinstance(first, dict) else None
        except httpx.HTTPError:
            return None
        finally:
            if owns_client:
                await client.aclose()

    async def _has_installation(self) -> bool:
        """True if the authenticated user has at least one installation of this app."""
        return await self._get_installation() is not None

    async def list_accessible_repos(self) -> list[GitHubRepoRef]:
        """List repos granted to this app's installations for the logged-in user.

        ponytail: first page only (100 repos per installation) — upgrade: follow Link pages.
        """
        token = await self.get_valid_token()
        owns_client = self._http is None
        client = await self._client()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "navbe",
        }
        try:
            inst_resp = await client.get(
                f"{_API_BASE}/user/installations",
                headers=headers,
                params={"per_page": 100},
            )
            if inst_resp.status_code in {401, 403}:
                raise ConfigurationError(
                    "GitHub App is not installed or token cannot list installations",
                    details={
                        "status": inst_resp.status_code,
                        "hint": f"Install the app and grant repo access: {self.install_url}",
                        "install_url": self.install_url,
                    },
                )
            inst_resp.raise_for_status()
            installations = inst_resp.json().get("installations") or []
            if not isinstance(installations, list) or not installations:
                return []

            seen: set[str] = set()
            repos: list[GitHubRepoRef] = []
            for installation in installations:
                if not isinstance(installation, dict):
                    continue
                inst_id = installation.get("id")
                if inst_id is None:
                    continue
                repo_resp = await client.get(
                    f"{_API_BASE}/user/installations/{inst_id}/repositories",
                    headers=headers,
                    params={"per_page": 100},
                )
                if repo_resp.status_code in {401, 403}:
                    continue
                repo_resp.raise_for_status()
                items = repo_resp.json().get("repositories") or []
                if not isinstance(items, list):
                    continue
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    full_name = str(item.get("full_name") or "")
                    if not full_name or full_name in seen:
                        continue
                    owner_obj = item.get("owner") if isinstance(item.get("owner"), dict) else {}
                    owner = str(owner_obj.get("login") or full_name.split("/")[0])
                    name = str(item.get("name") or full_name.split("/")[-1])
                    seen.add(full_name)
                    repos.append(
                        GitHubRepoRef(
                            full_name=full_name,
                            owner=owner,
                            name=name,
                            private=bool(item.get("private")),
                            html_url=str(item.get("html_url") or ""),
                            clone_url=str(
                                item.get("clone_url")
                                or f"https://github.com/{full_name}.git"
                            ),
                        )
                    )
            repos.sort(key=lambda r: r.full_name.lower())
            return repos
        except httpx.HTTPError as exc:
            raise ExecutionError(
                "GitHub list accessible repos failed",
                details={"error": str(exc)},
            ) from exc
        finally:
            if owns_client:
                await client.aclose()

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

        Uses a valid GitHub App user token. Never returns the token.
        """
        token = await self.get_valid_token()
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
                    "default_branch": str(data.get("default_branch") or "main"),
                    "empty": data.get("size") == 0,
                }
            if get_resp.status_code not in {403, 404}:
                raise ExecutionError(
                    "GitHub get repo failed",
                    details={"status": get_resp.status_code, "body": get_resp.text[:500]},
                )

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
            if create_resp.status_code in {401, 403}:
                raise ConfigurationError(
                    "GitHub App cannot create repository (install or permissions missing)",
                    details={
                        "status": create_resp.status_code,
                        "body": create_resp.text[:500],
                        "hint": f"Install the app and grant repo access: {self.install_url}",
                        "install_url": self.install_url,
                    },
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
                "default_branch": str(data.get("default_branch") or "main"),
                "empty": False,
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
