"""Shared fakes for CLI unit tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from navbe.domains.execution.models import RunDetail, RunState, RunStatus
from navbe.domains.sync.models import SyncConfig, SyncResult, SyncStatus


class FakeSecretsService:
    """In-memory secrets fake."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self._apps: dict[str, str | None] = {}

    async def set(self, key: str, value: str, *, app: str | None = None):
        from navbe.domains.secrets.models import CredentialHint, mask_secret

        resolved_app = app if app is not None else self._apps.get(key)
        self._data[key] = value
        self._apps[key] = resolved_app
        return CredentialHint(
            key=key,
            hint=mask_secret(value),
            app=resolved_app,
            source="store",
        )

    async def delete(self, key: str) -> bool:
        if key not in self._data:
            return False
        del self._data[key]
        self._apps.pop(key, None)
        return True

    async def list_keys(self) -> list[str]:
        return sorted(self._data.keys())

    async def list_credentials(self):
        from navbe.domains.secrets.models import CredentialHint, mask_secret

        return [
            CredentialHint(
                key=key,
                hint=mask_secret(self._data[key]),
                app=self._apps.get(key),
                source="store",
            )
            for key in sorted(self._data.keys())
        ]

    async def get_hint(self, key: str):
        from navbe.core.exceptions import NotFoundError
        from navbe.domains.secrets.models import CredentialHint, mask_secret

        if key not in self._data:
            raise NotFoundError(f"Secret '{key}' not found", details={"key": key})
        return CredentialHint(
            key=key,
            hint=mask_secret(self._data[key]),
            app=self._apps.get(key),
            source="store",
        )

    async def has(self, key: str) -> bool:
        return key in self._data


class FakeSyncService:
    """Minimal sync fake."""

    def __init__(self) -> None:
        self.config = SyncConfig(remote_url="https://github.com/org/r.git")
        self.branch = "main"

    async def configure(self, **kwargs: Any) -> SyncConfig:
        data = self.config.model_dump()
        for key, value in kwargs.items():
            if value is not None:
                data[key] = value
        self.config = SyncConfig.model_validate(data)
        return self.config

    async def init(self) -> SyncStatus:
        return await self.status()

    async def status(self) -> SyncStatus:
        return SyncStatus(
            configured=bool(self.config.remote_url),
            initialized=True,
            remote_url=self.config.remote_url,
            branch=self.branch,
            dirty=False,
            local_flow_count=1,
            remote_flow_count=1,
        )

    async def branch_create(self, name: str) -> SyncStatus:
        self.branch = name
        return await self.status()

    async def checkout(self, branch: str) -> SyncStatus:
        self.branch = branch
        return await self.status()

    async def push(self, message: str | None = None) -> SyncResult:
        return SyncResult(
            branch=self.branch,
            commit_sha="abc",
            flows_added=["a"],
            message=message or "pushed",
        )

    async def pull(self) -> SyncResult:
        return SyncResult(branch=self.branch, commit_sha="def", message="pulled")

    async def connect(
        self,
        *,
        owner: str,
        name: str,
        private: bool = True,
        local_repo_dir: str | None = None,
        default_branch: str | None = None,
    ) -> SyncStatus:
        self.config = SyncConfig(
            remote_url=f"https://github.com/{owner}/{name}.git",
            local_repo_dir=local_repo_dir or self.config.local_repo_dir,
            default_branch=default_branch or self.config.default_branch,
        )
        return await self.status()


class FakeGitHubAuthService:
    """GitHub auth fake for CLI login tests."""

    def __init__(self) -> None:
        self.logged_in = False
        self.login: str | None = None
        self.pending = False

    async def status(self):
        from navbe.domains.sync.github_auth import GitHubAuthStatus

        return GitHubAuthStatus(
            logged_in=self.logged_in,
            login=self.login,
            pending=self.pending,
            app_installed=True if self.logged_in else None,
            install_url=None,
        )

    async def begin(self):
        from navbe.domains.sync.github_auth import DeviceBeginResult

        self.pending = True
        return DeviceBeginResult(
            user_code="ABCD-1234",
            verification_uri="https://github.com/login/device",
            expires_in=900,
            interval=5,
        )

    async def complete(self, *, timeout: float = 300.0):
        from navbe.domains.sync.github_auth import GitHubAuthStatus

        self.logged_in = True
        self.login = "octocat"
        self.pending = False
        return GitHubAuthStatus(
            logged_in=True,
            login="octocat",
            pending=False,
            app_installed=True,
            install_url=None,
        )

    async def logout(self):
        from navbe.domains.sync.github_auth import GitHubAuthStatus

        self.logged_in = False
        self.login = None
        self.pending = False
        return GitHubAuthStatus(
            logged_in=False,
            login=None,
            pending=False,
            app_installed=None,
            install_url=None,
        )

    async def list_accessible_repos(self):
        return []


class FakeRunService:
    """Run service fake with mutable status for watch tests."""

    def __init__(self) -> None:
        now = datetime.now(UTC)
        self._runs: dict[str, RunState] = {
            "r1": RunState(
                run_id="r1",
                flow_id="demo",
                status=RunStatus.RUNNING,
                current_node="n1",
                created_at=now,
                updated_at=now,
            )
        }
        self._polls = 0
        self._list_polls = 0

    async def status(self, run_id: str) -> RunState:
        self._polls += 1
        self._complete_running_if(self._polls >= 2)
        return self._runs[run_id]

    async def detail(self, run_id: str) -> RunDetail:
        """Return RunDetail wrapping status (empty steps for unit fakes)."""
        state = await self.status(run_id)
        return RunDetail(state=state, steps=[], diagram="flowchart TD\n")

    async def list_runs(self, flow_id: str | None = None) -> list[RunState]:
        self._list_polls += 1
        self._complete_running_if(self._list_polls >= 2)
        runs = list(self._runs.values())
        if flow_id is not None:
            runs = [r for r in runs if r.flow_id == flow_id]
        return runs

    def _complete_running_if(self, ready: bool) -> None:
        """Flip running → completed once enough polls have happened."""
        if not ready:
            return
        for run_id, state in list(self._runs.items()):
            if state.status == RunStatus.RUNNING:
                self._runs[run_id] = state.model_copy(
                    update={"status": RunStatus.COMPLETED, "current_node": None}
                )


class FakeCatalogService:
    """Catalog fake with one known step."""

    async def get_steps_catalog(self) -> dict[str, dict]:
        return {
            "set_var": {
                "step_type": "set_var",
                "config_schema": {
                    "title": "Set variable",
                    "description": "Extract a value",
                    "type": "object",
                },
            }
        }
