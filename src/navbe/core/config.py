"""Application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from navbe.core.paths import default_data_home


def _default_db_path() -> Path:
    """SQLite control-plane DB under the active data home."""
    return default_data_home() / "navbe.db"


def _default_flows_dir() -> Path:
    """Flows directory under the active data home."""
    return default_data_home() / "navbe_flows"


def _default_credentials_path() -> Path:
    """Credentials JSON under the active data home."""
    return default_data_home() / "navbe_credentials.json"


def _default_sync_config_path() -> Path:
    """Sync config JSON under the active data home."""
    return default_data_home() / "navbe_sync.json"


def _default_github_oauth_path() -> Path:
    """Managed GitHub OAuth token JSON under the active data home."""
    return default_data_home() / "navbe_github_oauth.json"


class Settings(BaseSettings):
    """Navbe runtime settings (env prefix ``NAVBE_``)."""

    # extra=ignore: connector secrets (RESEND_API_KEY, etc.) live in the same .env
    model_config = SettingsConfigDict(
        env_prefix="NAVBE_",
        env_file=".env",
        extra="ignore",
    )

    db_path: Path = Field(default_factory=_default_db_path)
    flows_dir: Path = Field(default_factory=_default_flows_dir)
    credentials_path: Path = Field(default_factory=_default_credentials_path)
    sync_config_path: Path = Field(default_factory=_default_sync_config_path)
    github_oauth_path: Path = Field(default_factory=_default_github_oauth_path)
    # Public OAuth App client id (Device Flow). Override via NAVBE_GITHUB_OAUTH_CLIENT_ID.
    github_oauth_client_id: str = ""
    log_level: str = "INFO"
    mcp_server_name: str = "navbe"
    anthropic_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide cached Settings instance."""
    return Settings()
