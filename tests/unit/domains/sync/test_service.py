"""SyncService: workspace assets (flows/<id>/flow.json) — OAuth auth, never runs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from navbe.core.exceptions import ValidationError
from navbe.domains.flows.models import FlowMetadata, FlowSpec
from navbe.domains.sync.assets import FlowsAsset, list_flow_ids
from navbe.domains.sync.models import SyncConfig
from navbe.domains.sync.oauth_store import GitHubOAuthStore
from navbe.domains.sync.service import SyncService


def _minimal_spec(flow_id: str, name: str = "") -> dict[str, Any]:
    """Minimal valid FlowSpec dict."""
    return {
        "flow_id": flow_id,
        "name": name or flow_id,
        "entry_node": "n1",
        "connectors": {},
        "nodes": [
            {
                "id": "n1",
                "step_type": "set_var",
                "config": {"var_name": "x", "value_from": "y"},
            }
        ],
        "edges": [],
    }


def _write_flow(root: Path, flow_id: str, **extra_files: str) -> None:
    """Write flow.json (+ optional junk files) under root/flow_id/."""
    flow_dir = root / flow_id
    flow_dir.mkdir(parents=True, exist_ok=True)
    (flow_dir / "flow.json").write_text(
        json.dumps(_minimal_spec(flow_id)),
        encoding="utf-8",
    )
    for name, content in extra_files.items():
        target = flow_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


class FakeFlowRepo:
    """In-memory repo that also writes flow.json (mirrors FileSystem upsert)."""

    def __init__(self, flows_dir: Path) -> None:
        self.flows_dir = flows_dir
        self.flows: dict[str, FlowSpec] = {}
        self.deleted: list[str] = []

    async def upsert(self, flow_spec: FlowSpec) -> FlowMetadata:
        path = self.flows_dir / flow_spec.flow_id / "flow.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(flow_spec.model_dump_json(indent=2), encoding="utf-8")
        self.flows[flow_spec.flow_id] = flow_spec
        now = datetime.now(UTC)
        return FlowMetadata(
            flow_id=flow_spec.flow_id,
            name=flow_spec.name,
            created_at=now,
            updated_at=now,
            version=1,
            path=str(path),
        )

    async def delete_index(self, flow_id: str) -> None:
        self.deleted.append(flow_id)
        self.flows.pop(flow_id, None)

    async def delete(self, flow_id: str) -> None:
        await self.delete_index(flow_id)


class FakeGitRemote:
    """In-memory git remote: tracks branch, dirty, commits, push/pull calls."""

    def __init__(self) -> None:
        self.branch = "main"
        self.dirty = False
        self.head = "sha0"
        self.ensure_clone_calls: list[tuple[str, str, str]] = []
        self.commit_calls: list[tuple[str, str, list[str] | None]] = []
        self.push_calls: list[tuple[str, str]] = []
        self.pull_calls: list[tuple[str, str]] = []
        self.create_branch_calls: list[tuple[str, str, str]] = []
        self.checkout_calls: list[tuple[str, str]] = []
        self.next_commit_sha: str | None = "sha1"

    async def ensure_clone(self, remote_url: str, local_dir: str, branch: str) -> None:
        self.ensure_clone_calls.append((remote_url, local_dir, branch))
        Path(local_dir).mkdir(parents=True, exist_ok=True)
        (Path(local_dir) / ".git").mkdir(exist_ok=True)
        self.branch = branch

    async def current_branch(self, local_dir: str) -> str:
        return self.branch

    async def is_dirty(self, local_dir: str) -> bool:
        return self.dirty

    async def create_branch(self, local_dir: str, name: str, from_branch: str) -> None:
        self.create_branch_calls.append((local_dir, name, from_branch))
        self.branch = name

    async def checkout(self, local_dir: str, branch: str) -> None:
        self.checkout_calls.append((local_dir, branch))
        self.branch = branch

    async def pull_ff_only(self, local_dir: str, branch: str) -> str:
        self.pull_calls.append((local_dir, branch))
        self.branch = branch
        self.head = "sha-pulled"
        return self.head

    async def commit_all(
        self,
        local_dir: str,
        message: str,
        paths: list[str] | None = None,
    ) -> str | None:
        self.commit_calls.append((local_dir, message, paths))
        if self.next_commit_sha is None:
            return None
        self.head = self.next_commit_sha
        return self.head

    async def push(self, local_dir: str, branch: str) -> None:
        self.push_calls.append((local_dir, branch))

    async def head_sha(self, local_dir: str) -> str:
        return self.head


@pytest.fixture
def sync_env(tmp_path: Path) -> dict[str, Any]:
    """Temp flows dir, clone dir, config, OAuth store, FakeGit, SyncService."""
    flows_dir = tmp_path / "navbe_flows"
    flows_dir.mkdir()
    repo_dir = tmp_path / "navbe_sync_repo"
    config_path = tmp_path / "navbe_sync.json"
    oauth_path = tmp_path / "navbe_github_oauth.json"
    config = SyncConfig(
        remote_url="https://github.com/org/navbe-flows.git",
        local_repo_dir=str(repo_dir),
        flows_subdir="flows",
        default_branch="main",
    )
    config_path.write_text(config.model_dump_json(indent=2), encoding="utf-8")
    oauth = GitHubOAuthStore(oauth_path)
    git = FakeGitRemote()
    repo = FakeFlowRepo(flows_dir)
    asset = FlowsAsset(flows_dir=flows_dir, flow_repository=repo)  # type: ignore[arg-type]
    service = SyncService(
        config_path=config_path,
        flows_dir=flows_dir,
        flow_repository=repo,  # type: ignore[arg-type]
        oauth_store=oauth,
        assets=[asset],
        git=git,
    )
    return {
        "flows_dir": flows_dir,
        "repo_dir": repo_dir,
        "config_path": config_path,
        "oauth": oauth,
        "git": git,
        "repo": repo,
        "service": service,
    }


@pytest.fixture
async def sync_env_ready(sync_env: dict[str, Any]) -> dict[str, Any]:
    """Same as sync_env but with an OAuth token saved."""
    oauth: GitHubOAuthStore = sync_env["oauth"]
    await oauth.save_token(access_token="test-token", login="tester")
    return sync_env


def test_list_flow_ids_ignores_dirs_without_flow_json(tmp_path: Path) -> None:
    """Only directories containing flow.json count."""
    _write_flow(tmp_path, "a")
    (tmp_path / "b").mkdir()
    (tmp_path / "c" / "runs").mkdir(parents=True)
    assert list_flow_ids(tmp_path) == ["a"]


async def test_push_copies_only_flow_json_not_runs_or_archives(
    sync_env_ready: dict[str, Any],
) -> None:
    """Push mirrors flows/<id>/flow.json only — drops runs/ and archives."""
    flows_dir: Path = sync_env_ready["flows_dir"]
    repo_dir: Path = sync_env_ready["repo_dir"]
    git: FakeGitRemote = sync_env_ready["git"]
    service: SyncService = sync_env_ready["service"]

    await git.ensure_clone("url", str(repo_dir), "main")
    remote_flows = repo_dir / "flows"
    _write_flow(remote_flows, "alpha", **{"flow.v1.json": "{}", "runs/x.json": "{}"})
    _write_flow(
        flows_dir,
        "alpha",
        **{"flow.v2.json": "archive", "runs/state.json": "run"},
    )
    _write_flow(flows_dir, "beta")

    result = await service.push(message="sync test")

    assert result.message == "pushed"
    assert set(result.flows_added + result.flows_updated) >= {"alpha", "beta"}
    assert git.commit_calls[0][2] == ["flows"]
    assert git.commit_calls[0][1] == "sync test"
    assert git.push_calls == [(str(repo_dir), "main")]

    alpha = remote_flows / "alpha"
    assert (alpha / "flow.json").is_file()
    assert not (alpha / "flow.v2.json").exists()
    assert not (alpha / "runs").exists()
    assert not (alpha / "flow.v1.json").exists()
    assert (remote_flows / "beta" / "flow.json").is_file()


async def test_push_removes_remote_flows_missing_locally(
    sync_env_ready: dict[str, Any],
) -> None:
    """Remote flow dirs not present locally are deleted on push."""
    flows_dir: Path = sync_env_ready["flows_dir"]
    repo_dir: Path = sync_env_ready["repo_dir"]
    git: FakeGitRemote = sync_env_ready["git"]
    service: SyncService = sync_env_ready["service"]

    await git.ensure_clone("url", str(repo_dir), "main")
    remote_flows = repo_dir / "flows"
    _write_flow(remote_flows, "gone")
    _write_flow(flows_dir, "keep")

    result = await service.push()
    assert result.flows_removed == ["gone"]
    assert result.message == "pushed"
    assert git.commit_calls[0][1] == "navbe: sync workspace"
    assert not (remote_flows / "gone").exists()
    assert (remote_flows / "keep" / "flow.json").is_file()


async def test_pull_imports_only_flow_json_organization(
    sync_env_ready: dict[str, Any],
) -> None:
    """Pull imports flows/<id>/flow.json; ignores remote runs/archives; drops local extras."""
    flows_dir: Path = sync_env_ready["flows_dir"]
    repo_dir: Path = sync_env_ready["repo_dir"]
    git: FakeGitRemote = sync_env_ready["git"]
    repo: FakeFlowRepo = sync_env_ready["repo"]
    service: SyncService = sync_env_ready["service"]

    await git.ensure_clone("url", str(repo_dir), "main")
    remote_flows = repo_dir / "flows"
    _write_flow(
        remote_flows,
        "from_gh",
        **{"flow.v9.json": "ignore", "runs/old.json": "ignore"},
    )
    _write_flow(flows_dir, "local_only")

    result = await service.pull()

    assert result.message == "pulled"
    assert result.flows_added == ["from_gh"]
    assert result.flows_removed == ["local_only"]
    assert "from_gh" in repo.flows
    assert (flows_dir / "from_gh" / "flow.json").is_file()
    assert not (flows_dir / "from_gh" / "flow.v9.json").exists()
    assert not (flows_dir / "from_gh" / "runs").exists()
    assert not (flows_dir / "local_only").exists()
    assert repo.deleted == ["local_only"]
    assert git.pull_calls


async def test_checkout_fails_when_dirty(sync_env_ready: dict[str, Any]) -> None:
    """Dirty clone blocks checkout."""
    repo_dir: Path = sync_env_ready["repo_dir"]
    git: FakeGitRemote = sync_env_ready["git"]
    service: SyncService = sync_env_ready["service"]
    await git.ensure_clone("url", str(repo_dir), "main")
    git.dirty = True
    with pytest.raises(ValidationError, match="dirty"):
        await service.checkout("feature")


async def test_configure_and_init(sync_env_ready: dict[str, Any]) -> None:
    """configure persists settings; init clones via FakeGit."""
    service: SyncService = sync_env_ready["service"]
    git: FakeGitRemote = sync_env_ready["git"]
    config = await service.configure(remote_url="https://github.com/o/r.git")
    assert config.remote_url.endswith("/r.git")
    status = await service.init()
    assert status.initialized is True
    assert status.github_logged_in is True
    assert git.ensure_clone_calls
