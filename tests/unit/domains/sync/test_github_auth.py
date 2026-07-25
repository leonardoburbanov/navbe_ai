"""GitHub App Device Flow auth + refresh."""

from __future__ import annotations

import time
from pathlib import Path

import httpx
import pytest
import respx

from navbe.core.exceptions import ConfigurationError, ExecutionError
from navbe.domains.sync.github_auth import GitHubAuthService
from navbe.domains.sync.oauth_store import GitHubOAuthStore


@pytest.fixture
def store(tmp_path: Path) -> GitHubOAuthStore:
    """Empty token store under tmp."""
    return GitHubOAuthStore(tmp_path / "navbe_github_oauth.json")


@pytest.fixture
def auth(store: GitHubOAuthStore) -> GitHubAuthService:
    """Auth service with a test client id."""
    return GitHubAuthService(store=store, client_id="Iv23liTEST", app_slug="navbe-ai")


@respx.mock
async def test_begin_device_flow_disabled_has_hint(auth: GitHubAuthService) -> None:
    """400 device_flow_disabled surfaces an enable-Device-Flow hint."""
    respx.post("https://github.com/login/device/code").mock(
        return_value=httpx.Response(
            400,
            json={
                "error": "device_flow_disabled",
                "error_description": "Device Flow must be explicitly enabled for this App",
            },
        )
    )
    with pytest.raises(ExecutionError, match="Device Flow is disabled") as exc_info:
        await auth.begin()
    assert "Optional features" in str(exc_info.value.details.get("hint", ""))


@respx.mock
async def test_begin_omits_scope(auth: GitHubAuthService) -> None:
    """Device-code request sends client_id only (no OAuth scope)."""
    route = respx.post("https://github.com/login/device/code").mock(
        return_value=httpx.Response(
            200,
            json={
                "device_code": "dc",
                "user_code": "ABCD-1234",
                "verification_uri": "https://github.com/login/device",
                "expires_in": 900,
                "interval": 5,
            },
        )
    )
    result = await auth.begin()
    assert result.user_code == "ABCD-1234"
    assert route.called
    body = route.calls.last.request.content.decode()
    assert "client_id=Iv23liTEST" in body
    assert "scope=" not in body


@respx.mock
async def test_complete_stores_refresh_and_expiry(
    auth: GitHubAuthService,
    store: GitHubOAuthStore,
) -> None:
    """Successful poll persists access + refresh + expires_at."""
    await store.save_pending(device_code="dc", interval=1, expires_at=time.time() + 60)
    respx.post("https://github.com/login/oauth/access_token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "ghu_access",
                "refresh_token": "ghr_refresh",
                "expires_in": 28800,
                "refresh_token_expires_in": 15897600,
                "token_type": "bearer",
                "scope": "",
            },
        )
    )
    respx.get("https://api.github.com/user").mock(
        return_value=httpx.Response(200, json={"login": "octocat"})
    )
    respx.get("https://api.github.com/user/installations").mock(
        return_value=httpx.Response(200, json={"installations": [{"id": 1}]})
    )
    status = await auth.complete(timeout=5)
    assert status.logged_in is True
    assert status.login == "octocat"
    assert await store.get_token() == "ghu_access"
    assert await store.get_refresh_token() == "ghr_refresh"
    assert await store.get_expires_at() is not None


@respx.mock
async def test_get_valid_token_refreshes_when_expired(
    auth: GitHubAuthService,
    store: GitHubOAuthStore,
) -> None:
    """Near-expiry access token is refreshed without client_secret."""
    await store.save_token(
        access_token="ghu_old",
        refresh_token="ghr_refresh",
        expires_in=-10,
        refresh_token_expires_in=10000,
        login="octocat",
    )
    route = respx.post("https://github.com/login/oauth/access_token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "ghu_new",
                "refresh_token": "ghr_new",
                "expires_in": 28800,
                "refresh_token_expires_in": 15897600,
                "token_type": "bearer",
                "scope": "",
            },
        )
    )
    token = await auth.get_valid_token()
    assert token == "ghu_new"
    assert await store.get_token() == "ghu_new"
    assert route.called
    body = route.calls.last.request.content.decode()
    assert "grant_type=refresh_token" in body
    assert "client_secret" not in body


@respx.mock
async def test_get_valid_token_refresh_failure_clears_store(
    auth: GitHubAuthService,
    store: GitHubOAuthStore,
) -> None:
    """Failed refresh clears credentials and asks for re-login."""
    await store.save_token(
        access_token="ghu_old",
        refresh_token="ghr_bad",
        expires_in=-10,
        login="octocat",
    )
    respx.post("https://github.com/login/oauth/access_token").mock(
        return_value=httpx.Response(
            200,
            json={"error": "bad_refresh_token", "error_description": "bad"},
        )
    )
    with pytest.raises(ConfigurationError, match="refresh"):
        await auth.get_valid_token()
    assert await store.has_token() is False


@respx.mock
async def test_status_includes_install_url_when_not_installed(
    auth: GitHubAuthService,
    store: GitHubOAuthStore,
) -> None:
    """Logged-in but no installations → install_url set."""
    await store.save_token(access_token="ghu_x", login="octocat")
    respx.get("https://api.github.com/user/installations").mock(
        return_value=httpx.Response(200, json={"installations": []})
    )
    status = await auth.status()
    assert status.logged_in is True
    assert status.app_installed is False
    assert status.install_url == "https://github.com/apps/navbe-ai/installations/new"
    assert status.uninstall_url == "https://github.com/settings/installations"
    assert status.configure_url is None


@respx.mock
async def test_status_includes_configure_url_when_installed(
    auth: GitHubAuthService,
    store: GitHubOAuthStore,
) -> None:
    """Logged-in with an installation → configure/uninstall URLs point at it."""
    await store.save_token(access_token="ghu_x", login="octocat")
    respx.get("https://api.github.com/user/installations").mock(
        return_value=httpx.Response(
            200,
            json={"installations": [{"id": 4242, "app_slug": "navbe-ai"}]},
        )
    )
    status = await auth.status()
    assert status.app_installed is True
    assert status.install_url is None
    assert status.configure_url == "https://github.com/settings/installations/4242"
    assert status.uninstall_url == status.configure_url


@respx.mock
async def test_list_accessible_repos(
    auth: GitHubAuthService,
    store: GitHubOAuthStore,
) -> None:
    """Installation repos are listed as owner/name refs."""
    await store.save_token(access_token="ghu_x", login="octocat")
    respx.get("https://api.github.com/user/installations").mock(
        return_value=httpx.Response(
            200,
            json={"installations": [{"id": 7}]},
        )
    )
    respx.get("https://api.github.com/user/installations/7/repositories").mock(
        return_value=httpx.Response(
            200,
            json={
                "repositories": [
                    {
                        "full_name": "octocat/flows",
                        "name": "flows",
                        "private": True,
                        "html_url": "https://github.com/octocat/flows",
                        "clone_url": "https://github.com/octocat/flows.git",
                        "owner": {"login": "octocat"},
                    }
                ]
            },
        )
    )
    repos = await auth.list_accessible_repos()
    assert len(repos) == 1
    assert repos[0].full_name == "octocat/flows"
    assert repos[0].owner == "octocat"
    assert repos[0].name == "flows"
