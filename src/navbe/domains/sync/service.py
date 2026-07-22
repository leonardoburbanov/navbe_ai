"""Sync use-cases: GitHub mirror of versionable workspace metadata.

Push/pull iterates registered ``WorkspaceAsset`` instances. EPIC 14 registers
flows only (``flows/<flow_id>/flow.json``). Never runs/, archives, credentials,
OAuth tokens, or Python step source.

Auth: GitHub Device Flow token from ``GitHubOAuthStore`` only.
"""

from __future__ import annotations

import json
from pathlib import Path

import aiofiles

from navbe.core.exceptions import ConfigurationError, NotFoundError, ValidationError
from navbe.domains.flows.interfaces import FlowRepository
from navbe.domains.sync.assets import FlowsAsset, copy_flow_json, list_flow_ids
from navbe.domains.sync.git_remote import GitSubprocessRemote
from navbe.domains.sync.github_auth import GitHubAuthService
from navbe.domains.sync.interfaces import GitRemote, WorkspaceAsset
from navbe.domains.sync.models import SyncConfig, SyncResult, SyncStatus
from navbe.domains.sync.oauth_store import GitHubOAuthStore

__all__ = [
    "SyncService",
    "copy_flow_json",
    "list_flow_ids",
]

class SyncService:
    """Configure and run workspace GitHub sync (OAuth-backed)."""

    def __init__(
        self,
        *,
        config_path: Path,
        flows_dir: Path,
        flow_repository: FlowRepository,
        oauth_store: GitHubOAuthStore,
        auth_service: GitHubAuthService | None = None,
        assets: list[WorkspaceAsset] | None = None,
        git: GitRemote | None = None,
    ) -> None:
        """Create a sync service bound to local workspace assets and config."""
        self._config_path = config_path
        self._flows_dir = flows_dir
        self._flows = flow_repository
        self._oauth = oauth_store
        self._auth = auth_service
        self._git = git or GitSubprocessRemote()
        self._assets: list[WorkspaceAsset] = assets or [
            FlowsAsset(flows_dir=flows_dir, flow_repository=flow_repository),
        ]

    async def _load_config(self) -> SyncConfig:
        """Load sync config from disk (empty defaults if missing)."""
        if not self._config_path.exists():
            return SyncConfig()
        async with aiofiles.open(self._config_path, encoding="utf-8") as handle:
            raw = await handle.read()
        data = json.loads(raw) if raw.strip() else {}
        # Drop deprecated PAT key if present in older configs.
        data.pop("token_secret_key", None)
        return SyncConfig.model_validate(data)

    async def _save_config(self, config: SyncConfig) -> None:
        """Persist sync config (never includes tokens)."""
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(self._config_path, "w", encoding="utf-8") as handle:
            await handle.write(config.model_dump_json(indent=2) + "\n")

    async def _resolve_token(self) -> str:
        """Resolve GitHub token from the OAuth store only."""
        try:
            return await self._oauth.get_token()
        except NotFoundError as exc:
            raise ConfigurationError(
                "GitHub OAuth token not found",
                details={
                    "hint": "run navbe login github (or auth_github_begin / auth_github_complete)",
                },
            ) from exc

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
                details={"hint": "call sync_connect or sync_configure with remote_url first"},
            )

    def _asset_paths(self) -> list[str]:
        """Subdirs to stage on commit."""
        return [asset.subdir for asset in self._assets]

    async def configure(
        self,
        *,
        remote_url: str | None = None,
        local_repo_dir: str | None = None,
        flows_subdir: str | None = None,
        default_branch: str | None = None,
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
        updated = SyncConfig.model_validate(data)
        await self._save_config(updated)
        return updated

    async def connect(
        self,
        *,
        owner: str,
        name: str,
        private: bool = True,
        local_repo_dir: str | None = None,
        default_branch: str | None = None,
    ) -> SyncStatus:
        """Create-or-bind ``owner/name``, configure remote, and init the clone."""
        if self._auth is None:
            raise ConfigurationError(
                "GitHub auth service is not configured",
                details={"hint": "wire GitHubAuthService into SyncService"},
            )
        repo_info = await self._auth.ensure_repo(owner=owner, name=name, private=private)
        clone_url = str(repo_info["clone_url"])
        await self.configure(
            remote_url=clone_url,
            local_repo_dir=local_repo_dir,
            default_branch=default_branch,
        )
        return await self.init()

    async def init(self) -> SyncStatus:
        """Clone or bind the remote repository."""
        config = await self._load_config()
        self._require_remote(config)
        token = await self._resolve_token()
        git = self._git_with_auth(token)
        await git.ensure_clone(
            config.remote_url,
            config.local_repo_dir,
            config.default_branch,
        )
        clone = Path(config.local_repo_dir)
        for asset in self._assets:
            (clone / asset.subdir).mkdir(parents=True, exist_ok=True)
        return await self.status()

    async def status(self) -> SyncStatus:
        """Return sync / branch status and per-asset counts (local vs clone)."""
        config = await self._load_config()
        clone = Path(config.local_repo_dir)
        initialized = clone.exists() and (clone / ".git").exists()

        asset_counts: dict[str, dict[str, int]] = {}
        local_flow_count = 0
        remote_flow_count = 0
        for asset in self._assets:
            local_n = len(asset.list_local_ids())
            remote_n = len(asset.list_remote_ids(clone)) if initialized else 0
            asset_counts[asset.subdir] = {"local": local_n, "remote": remote_n}
            if asset.subdir == "flows" or getattr(asset, "subdir", "") == config.flows_subdir:
                local_flow_count = local_n
                remote_flow_count = remote_n

        logged_in = await self._oauth.has_token()
        login = await self._oauth.get_login()

        if not config.remote_url:
            return SyncStatus(
                configured=False,
                initialized=False,
                local_flow_count=local_flow_count,
                remote_flow_count=0,
                asset_counts=asset_counts,
                github_logged_in=logged_in,
                github_login=login,
            )
        if not initialized:
            return SyncStatus(
                configured=True,
                initialized=False,
                remote_url=config.remote_url,
                flows_subdir=config.flows_subdir,
                default_branch=config.default_branch,
                local_flow_count=local_flow_count,
                remote_flow_count=0,
                asset_counts=asset_counts,
                github_logged_in=logged_in,
                github_login=login,
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
            local_flow_count=local_flow_count,
            remote_flow_count=remote_flow_count,
            asset_counts=asset_counts,
            github_logged_in=logged_in,
            github_login=login,
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
        token = await self._resolve_token()
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
        token = await self._resolve_token()
        git = self._git_with_auth(token)
        await git.checkout(config.local_repo_dir, branch)
        return await self.status()

    async def push(self, message: str | None = None) -> SyncResult:
        """Export registered assets into the clone and push the current branch."""
        config = await self._load_config()
        self._require_remote(config)
        token = await self._resolve_token()
        git = self._git_with_auth(token)
        branch = await git.current_branch(config.local_repo_dir)
        clone = Path(config.local_repo_dir)

        assets_delta: dict[str, dict[str, list[str]]] = {}
        flows_added: list[str] = []
        flows_updated: list[str] = []
        flows_removed: list[str] = []
        for asset in self._assets:
            change = asset.export_to(clone)
            assets_delta[asset.subdir] = change.model_dump()
            if asset.subdir == "flows":
                flows_added = change.added
                flows_updated = change.updated
                flows_removed = change.removed

        commit_msg = message or "navbe: sync workspace"
        sha = await git.commit_all(
            config.local_repo_dir,
            commit_msg,
            paths=self._asset_paths(),
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
            flows_added=flows_added,
            flows_updated=flows_updated,
            flows_removed=flows_removed,
            assets=assets_delta,
            message=result_message,
        )

    async def pull(self) -> SyncResult:
        """Fast-forward pull and import registered assets into Navbe."""
        config = await self._load_config()
        self._require_remote(config)
        if await self._git.is_dirty(config.local_repo_dir):
            raise ValidationError(
                "working tree is dirty; cannot pull",
                details={"local_repo_dir": config.local_repo_dir},
            )
        token = await self._resolve_token()
        git = self._git_with_auth(token)
        branch = await git.current_branch(config.local_repo_dir)
        sha = await git.pull_ff_only(config.local_repo_dir, branch)
        clone = Path(config.local_repo_dir)

        assets_delta: dict[str, dict[str, list[str]]] = {}
        flows_added: list[str] = []
        flows_updated: list[str] = []
        flows_removed: list[str] = []
        for asset in self._assets:
            change = await asset.import_from(clone)
            assets_delta[asset.subdir] = change.model_dump()
            if asset.subdir == "flows":
                flows_added = change.added
                flows_updated = change.updated
                flows_removed = change.removed

        return SyncResult(
            branch=branch,
            commit_sha=sha,
            flows_added=flows_added,
            flows_updated=flows_updated,
            flows_removed=flows_removed,
            assets=assets_delta,
            message="pulled",
        )
