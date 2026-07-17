"""Application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Navbe runtime settings (env prefix ``NAVBE_``)."""

    model_config = SettingsConfigDict(env_prefix="NAVBE_", env_file=".env")

    db_path: Path = Path("./navbe.db")
    flows_dir: Path = Path("./navbe_flows")
    log_level: str = "INFO"
    mcp_server_name: str = "navbe"
    anthropic_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide cached Settings instance."""
    return Settings()
