"""Sync domain models (workspace GitHub mirror)."""

from pydantic import BaseModel, Field


class SyncConfig(BaseModel):
    """Persisted sync settings (no tokens — auth via GitHub OAuth store)."""

    remote_url: str = ""
    local_repo_dir: str = "./navbe_sync_repo"
    flows_subdir: str = "flows"
    default_branch: str = "main"


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
    asset_counts: dict[str, dict[str, int]] = Field(default_factory=dict)
    github_logged_in: bool = False
    github_login: str | None = None


class SyncResult(BaseModel):
    """Outcome of push or pull across registered workspace assets."""

    branch: str
    commit_sha: str | None = None
    flows_added: list[str] = Field(default_factory=list)
    flows_updated: list[str] = Field(default_factory=list)
    flows_removed: list[str] = Field(default_factory=list)
    assets: dict[str, dict[str, list[str]]] = Field(default_factory=dict)
    message: str = ""
