"""Shared fakes for CLI unit tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from navbe.domains.execution.models import RunState, RunStatus
from navbe.domains.sync.models import SyncConfig, SyncResult, SyncStatus


class FakeSecretsService:
    """In-memory secrets fake."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    async def set(self, key: str, value: str) -> None:
        self._data[key] = value

    async def delete(self, key: str) -> bool:
        if key not in self._data:
            return False
        del self._data[key]
        return True

    async def list_keys(self) -> list[str]:
        return sorted(self._data.keys())

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

    async def status(self, run_id: str) -> RunState:
        self._polls += 1
        state = self._runs[run_id]
        if self._polls >= 2 and state.status == RunStatus.RUNNING:
            completed = state.model_copy(
                update={"status": RunStatus.COMPLETED, "current_node": None}
            )
            self._runs[run_id] = completed
            return completed
        return state

    async def list_runs(self, flow_id: str) -> list[RunState]:
        return [r for r in self._runs.values() if r.flow_id == flow_id]


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
