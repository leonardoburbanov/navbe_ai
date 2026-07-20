"""Sync use-cases: GitHub mirror of flow organization only.

Only ``flows/<flow_id>/flow.json`` is copied. Never runs/, archives,
credentials, or Python step source.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import aiofiles

from navbe.core.exceptions import ConfigurationError, NotFoundError, ValidationError
from navbe.domains.flows.interfaces import FlowRepository
from navbe.domains.flows.models import FlowSpec
from navbe.domains.secrets.service import SecretsService
from navbe.domains.sync.git_remote import GitSubprocessRemote
from navbe.domains.sync.interfaces import GitRemote
from navbe.domains.sync.models import SyncConfig, SyncResult, SyncStatus


def list_flow_ids(flows_root: Path) -> list[str]:
    """Return flow_ids that have a ``flow.json`` under ``flows_root``."""
    if not flows_root.exists():
        return []
    ids: list[str] = []
    for child in sorted(flows_root.iterdir()):
        if child.is_dir() and (child / "flow.json").is_file():
            ids.append(child.name)
    return ids


def copy_flow_json(src_dir: Path, dest_dir: Path, flow_id: str) -> None:
    """Copy only ``flow_id/flow.json`` (creates dest dirs)."""
    src = src_dir / flow_id / "flow.json"
    dest = dest_dir / flow_id / "flow.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


class SyncService:
    """Configure and run flows-only GitHub sync."""

    def __init__(
        self,
        *,
        config_path: Path,
        flows_dir: Path,
        flow_repository: FlowRepository,
        secrets_service: SecretsService,
        git: GitRemote | None = None,
    ) -> None:
        """Create a sync service bound to local flows and a config file."""
        self._config_path = config_path
        self._flows_dir = flows_dir
        self._flows = flow_repository
        self._secrets = secrets_service
        self._git = git or GitSubprocessRemote()

    async def _load_config(self) -> SyncConfig:
        """Load sync config from disk (empty defaults if missing)."""
        if not self._config_path.exists():
            return SyncConfig()
        async with aiofiles.open(self._config_path, encoding="utf-8") as handle:
            raw = await handle.read()
        data = json.loads(raw) if raw.strip() else {}
        return SyncConfig.model_validate(data)

    async def _save_config(self, config: SyncConfig) -> None:
        """Persist sync config (never includes tokens)."""
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(self._config_path, "w", encoding="utf-8") as handle:
            await handle.write(config.model_dump_json(indent=2) + "\n")

    async def _resolve_token(self, config: SyncConfig) -> str:
        """Resolve GitHub token from credentials / env."""
        for key in (config.token_secret_key, "GH_TOKEN", "GITHUB_TOKEN"):
            try:
                return await self._secrets.resolve_ref(key)
            except NotFoundError:
                continue
        raise ConfigurationError(
            "GitHub token not found",
            details={
                "hint": "secret_set key=GITHUB_TOKEN (or GH_TOKEN) before sync_init",
                "key": config.token_secret_key,
            },
        )

    def _git_with_auth(self, token: str) -> GitRemote:
        """Return a git adapter carrying the bearer token in-process only."""
        base = self._git
        if isinstance(base, GitSubprocessRemote):
            return base.with_token(token)
        return base

    def _require_remote(self, config: SyncConfig) -> None:
        """Raise if remote_url is not configured."""
        if not config.remote_url.strip():
            raise ValidationError(
                "sync remote_url is not configured",
                details={"hint": "call sync_configure with remote_url first"},
            )

    async def configure(
        self,
        *,
        remote_url: str | None = None,
        local_repo_dir: str | None = None,
        flows_subdir: str | None = None,
        default_branch: str | None = None,
        token_secret_key: str | None = None,
    ) -> SyncConfig:
        """Update and persist sync settings (no token values)."""
        config = await self._load_config()
        data = config.model_dump()
        if remote_url is not None:
            data["remote_url"] = remote_url
        if local_repo_dir is not None:
            data["local_repo_dir"] = local_repo_dir
        if flows_subdir is not None:
            data["flows_subdir"] = flows_subdir.strip("/").replace("\\", "/") or "flows"
        if default_branch is not None:
            data["default_branch"] = default_branch
        if token_secret_key is not None:
            data["token_secret_key"] = token_secret_key
        updated = SyncConfig.model_validate(data)
        await self._save_config(updated)
        return updated

    async def init(self) -> SyncStatus:
        """Clone or bind the remote repository."""
        config = await self._load_config()
        self._require_remote(config)
        token = await self._resolve_token(config)
        git = self._git_with_auth(token)
        await git.ensure_clone(
            config.remote_url,
            config.local_repo_dir,
            config.default_branch,
        )
        flows_root = Path(config.local_repo_dir) / config.flows_subdir
        flows_root.mkdir(parents=True, exist_ok=True)
        return await self.status()

    async def status(self) -> SyncStatus:
        """Return sync / branch status and flow counts (local vs clone)."""
        config = await self._load_config()
        local_ids = list_flow_ids(self._flows_dir)
        repo = Path(config.local_repo_dir)
        initialized = repo.exists() and (repo / ".git").exists()
        remote_ids = list_flow_ids(repo / config.flows_subdir) if initialized else []
        if not config.remote_url:
            return SyncStatus(
                configured=False,
                initialized=False,
                local_flow_count=len(local_ids),
                remote_flow_count=0,
            )
        if not initialized:
            return SyncStatus(
                configured=True,
                initialized=False,
                remote_url=config.remote_url,
                flows_subdir=config.flows_subdir,
                default_branch=config.default_branch,
                local_flow_count=len(local_ids),
                remote_flow_count=0,
            )
        branch = await self._git.current_branch(config.local_repo_dir)
        dirty = await self._git.is_dirty(config.local_repo_dir)
        return SyncStatus(
            configured=True,
            initialized=True,
            remote_url=config.remote_url,
            branch=branch,
            dirty=dirty,
            flows_subdir=config.flows_subdir,
            default_branch=config.default_branch,
            local_flow_count=len(local_ids),
            remote_flow_count=len(remote_ids),
        )

    async def branch_create(self, name: str) -> SyncStatus:
        """Create and checkout a new branch from default_branch."""
        config = await self._load_config()
        self._require_remote(config)
        if await self._git.is_dirty(config.local_repo_dir):
            raise ValidationError(
                "working tree is dirty; commit or discard before branching",
                details={"local_repo_dir": config.local_repo_dir},
            )
        token = await self._resolve_token(config)
        git = self._git_with_auth(token)
        await git.create_branch(config.local_repo_dir, name, config.default_branch)
        return await self.status()

    async def checkout(self, branch: str) -> SyncStatus:
        """Checkout an existing branch (fails if dirty)."""
        config = await self._load_config()
        if await self._git.is_dirty(config.local_repo_dir):
            raise ValidationError(
                "working tree is dirty; commit or discard before checkout",
                details={"local_repo_dir": config.local_repo_dir},
            )
        token = await self._resolve_token(config)
        git = self._git_with_auth(token)
        await git.checkout(config.local_repo_dir, branch)
        return await self.status()

    async def push(self, message: str | None = None) -> SyncResult:
        """Copy local flows into clone ``flows/`` and push current branch.

        Only ``flows/<flow_id>/flow.json`` — not runs or archives.
        """
        config = await self._load_config()
        self._require_remote(config)
        token = await self._resolve_token(config)
        git = self._git_with_auth(token)
        branch = await git.current_branch(config.local_repo_dir)

        remote_flows = Path(config.local_repo_dir) / config.flows_subdir
        remote_flows.mkdir(parents=True, exist_ok=True)

        local_ids = set(list_flow_ids(self._flows_dir))
        remote_ids = set(list_flow_ids(remote_flows))

        removed = sorted(remote_ids - local_ids)
        for flow_id in removed:
            shutil.rmtree(remote_flows / flow_id, ignore_errors=True)

        added: list[str] = []
        updated: list[str] = []
        for flow_id in sorted(local_ids):
            if flow_id in remote_ids:
                updated.append(flow_id)
            else:
                added.append(flow_id)
            dest_dir = remote_flows / flow_id
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            copy_flow_json(self._flows_dir, remote_flows, flow_id)

        commit_msg = message or "navbe: sync flows"
        # Only stage flows_subdir — never runs/, credentials, or other clone junk.
        sha = await git.commit_all(
            config.local_repo_dir,
            commit_msg,
            paths=[config.flows_subdir],
        )
        if sha is not None:
            await git.push(config.local_repo_dir, branch)
            result_message = "pushed"
        else:
            sha = await git.head_sha(config.local_repo_dir)
            result_message = "up to date"

        return SyncResult(
            branch=branch,
            commit_sha=sha,
            flows_added=added,
            flows_updated=updated,
            flows_removed=removed,
            message=result_message,
        )

    async def pull(self) -> SyncResult:
        """Fast-forward pull and import only ``flows/<id>/flow.json`` into Navbe."""
        config = await self._load_config()
        self._require_remote(config)
        if await self._git.is_dirty(config.local_repo_dir):
            raise ValidationError(
                "working tree is dirty; cannot pull",
                details={"local_repo_dir": config.local_repo_dir},
            )
        token = await self._resolve_token(config)
        git = self._git_with_auth(token)
        branch = await git.current_branch(config.local_repo_dir)
        sha = await git.pull_ff_only(config.local_repo_dir, branch)

        remote_flows = Path(config.local_repo_dir) / config.flows_subdir
        remote_ids = set(list_flow_ids(remote_flows))
        local_ids = set(list_flow_ids(self._flows_dir))

        added: list[str] = []
        updated: list[str] = []
        for flow_id in sorted(remote_ids):
            spec_path = remote_flows / flow_id / "flow.json"
            async with aiofiles.open(spec_path, encoding="utf-8") as handle:
                raw = await handle.read()
            flow_spec = FlowSpec.model_validate_json(raw)
            if flow_id in local_ids:
                updated.append(flow_id)
            else:
                added.append(flow_id)
            await self._flows.upsert(flow_spec)

        removed = sorted(local_ids - remote_ids)
        for flow_id in removed:
            shutil.rmtree(self._flows_dir / flow_id, ignore_errors=True)
            await self._flows.delete_index(flow_id)

        return SyncResult(
            branch=branch,
            commit_sha=sha,
            flows_added=added,
            flows_updated=updated,
            flows_removed=removed,
            message="pulled",
        )
