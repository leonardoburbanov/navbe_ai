"""Git remote and workspace asset ports for sync."""

from pathlib import Path
from typing import Protocol, runtime_checkable

from navbe.domains.sync.github_auth import AssetChangeSet


@runtime_checkable
class GitRemote(Protocol):
    """Minimal git operations over a working clone."""

    async def ensure_clone(self, remote_url: str, local_dir: str, branch: str) -> None:
        """Clone if missing, otherwise fetch. Uses token via adapter env only."""
        ...

    async def current_branch(self, local_dir: str) -> str:
        """Return the checked-out branch name."""
        ...

    async def is_dirty(self, local_dir: str) -> bool:
        """True if the working tree has uncommitted changes."""
        ...

    async def create_branch(self, local_dir: str, name: str, from_branch: str) -> None:
        """Create ``name`` from ``from_branch`` and check it out."""
        ...

    async def checkout(self, local_dir: str, branch: str) -> None:
        """Check out ``branch`` (fails if dirty — caller must check)."""
        ...

    async def pull_ff_only(self, local_dir: str, branch: str) -> str:
        """Fast-forward pull; return HEAD sha."""
        ...

    async def commit_all(
        self,
        local_dir: str,
        message: str,
        paths: list[str] | None = None,
    ) -> str | None:
        """Stage ``paths`` (default: whole tree) and commit if dirty; return sha or None."""
        ...

    async def push(self, local_dir: str, branch: str) -> None:
        """Push current branch to origin."""
        ...

    async def head_sha(self, local_dir: str) -> str:
        """Return HEAD commit sha."""
        ...


@runtime_checkable
class WorkspaceAsset(Protocol):
    """One versionable workspace kind mirrored under ``subdir/`` in the clone.

    EPIC 14 ships FlowsAsset only. Future domains register connectors,
    destinations, and schedules without rewriting SyncService.
    """

    subdir: str

    def list_local_ids(self) -> list[str]:
        """Ids present in the local Navbe store."""
        ...

    def list_remote_ids(self, clone_root: Path) -> list[str]:
        """Ids present under clone_root/subdir."""
        ...

    def export_to(self, clone_root: Path) -> AssetChangeSet:
        """Write local assets into the clone; return change set."""
        ...

    async def import_from(self, clone_root: Path) -> AssetChangeSet:
        """Import clone assets into Navbe; return change set."""
        ...
