"""Application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from navbe.core.paths import default_data_home

# Public Client ID for the official Navbe AI GitHub App (Device Flow; no secret).
DEFAULT_GITHUB_APP_CLIENT_ID = "Iv23livr6YIrrz0WNGpN"
DEFAULT_GITHUB_APP_SLUG = "navbe-ai"


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
    """Managed GitHub App token JSON under the active data home."""
    return default_data_home() / "navbe_github_oauth.json"


class Settings(BaseSettings):
    """Navbe runtime settings (env prefix ``NAVBE_``)."""

    # extra=ignore: stray connector keys in .env are ignored; use credentials JSON
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
    # Official Navbe AI GitHub App Client ID (public). Override via NAVBE_GITHUB_APP_CLIENT_ID.
    github_app_client_id: str = DEFAULT_GITHUB_APP_CLIENT_ID
    github_app_slug: str = DEFAULT_GITHUB_APP_SLUG
    # ponytail: dual-read for one release — upgrade: drop after callers migrate.
    github_oauth_client_id: str = ""
    log_level: str = "INFO"
    mcp_server_name: str = "navbe"
    anthropic_api_key: str | None = None

    @model_validator(mode="after")
    def _apply_legacy_oauth_client_id(self) -> "Settings":
        """Prefer github_app_client_id; fall back to legacy OAuth env if app id is empty."""
        if not self.github_app_client_id.strip() and self.github_oauth_client_id.strip():
            self.github_app_client_id = self.github_oauth_client_id.strip()
        if not self.github_app_client_id.strip():
            self.github_app_client_id = DEFAULT_GITHUB_APP_CLIENT_ID
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide cached Settings instance."""
    return Settings()
