"""Git remote port for sync (flows mirror)."""

from typing import Protocol, runtime_checkable


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
