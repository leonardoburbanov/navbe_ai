"""Sync domain models (flows-only GitHub mirror)."""

from pydantic import BaseModel, Field


class SyncConfig(BaseModel):
    """Persisted sync settings (no tokens — token via secrets store)."""

    remote_url: str = ""
    local_repo_dir: str = "./navbe_sync_repo"
    flows_subdir: str = "flows"
    default_branch: str = "main"
    token_secret_key: str = "GITHUB_TOKEN"


class SyncStatus(BaseModel):
    """Current clone / branch state."""

    configured: bool
    initialized: bool
    remote_url: str = ""
    branch: str | None = None
    dirty: bool = False
    flows_subdir: str = "flows"
    default_branch: str = "main"
    local_flow_count: int = 0
    remote_flow_count: int = 0


class SyncResult(BaseModel):
    """Outcome of push or pull (flows only)."""

    branch: str
    commit_sha: str | None = None
    flows_added: list[str] = Field(default_factory=list)
    flows_updated: list[str] = Field(default_factory=list)
    flows_removed: list[str] = Field(default_factory=list)
    message: str = ""
