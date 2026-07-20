"""Shared DI providers for FastAPI and mcp_app.

This module is the only production place that constructs concrete services.
"""

from functools import lru_cache
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

import navbe.domains.connectors.implementations  # noqa: F401
import navbe.domains.steps.implementations  # noqa: F401
from navbe.core.config import get_settings
from navbe.core.database import create_engine
from navbe.domains.catalog.service import CatalogService
from navbe.domains.connectors.registry import ConnectorRegistry
from navbe.domains.connectors.service import ConnectorService
from navbe.domains.execution.engine import LangGraphEngine
from navbe.domains.execution.repository import FileSystemRunRepository
from navbe.domains.execution.service import RunService, resolve_connector_configs
from navbe.domains.flows.repository import FileSystemFlowRepository
from navbe.domains.flows.service import FlowService
from navbe.domains.secrets.json_file import ChainedSecretsProvider, JsonFileSecretsProvider
from navbe.domains.secrets.service import EnvSecretsProvider, SecretsService
from navbe.domains.steps.registry import StepRegistry
from navbe.domains.sync.service import SyncService


@lru_cache
def get_db_engine() -> AsyncEngine:
    """Return the process-wide async SQLAlchemy engine."""
    settings = get_settings()
    return create_engine(str(settings.db_path))


@lru_cache
def get_session_factory() -> async_sessionmaker:
    """Return the shared async session factory."""
    return async_sessionmaker(get_db_engine(), expire_on_commit=False)


@lru_cache
def get_secrets_service() -> SecretsService:
    """Return secrets service: JSON credentials file, then env fallback."""
    settings = get_settings()
    json_store = JsonFileSecretsProvider(settings.credentials_path)
    env_provider = EnvSecretsProvider()
    chain = ChainedSecretsProvider([json_store, env_provider])
    return SecretsService(
        chain,
        store=json_store,
        presence_checks=[json_store, env_provider],
    )


@lru_cache
def get_connector_service() -> ConnectorService:
    """Return the connector service singleton."""
    return ConnectorService(
        ConnectorRegistry,
        secrets_service=get_secrets_service(),
    )


@lru_cache
def get_flow_repository() -> FileSystemFlowRepository:
    """Return the shared filesystem flow repository."""
    settings = get_settings()
    return FileSystemFlowRepository(
        flows_dir=settings.flows_dir,
        session_factory=get_session_factory(),
    )


@lru_cache
def get_flow_service() -> FlowService:
    """Return the flow service singleton."""
    return FlowService(get_flow_repository())


@lru_cache
def get_sync_service() -> SyncService:
    """Return the flows-only GitHub sync service."""
    settings = get_settings()
    return SyncService(
        config_path=settings.sync_config_path,
        flows_dir=settings.flows_dir,
        flow_repository=get_flow_repository(),
        secrets_service=get_secrets_service(),
    )


@lru_cache
def get_run_service() -> RunService:
    """Return the run service singleton with a LangGraph engine."""
    settings = get_settings()
    flow_service = get_flow_service()
    connector_service = get_connector_service()
    run_repo = FileSystemRunRepository(
        runs_dir_for=lambda flow_id: settings.flows_dir / flow_id / "runs",
    )

    async def resolve_connectors(flow_spec: Any) -> dict[str, Any]:
        return await resolve_connector_configs(flow_spec, connector_service)

    # Separate checkpoint DB from the control-plane SQLAlchemy file.
    checkpoint_path = settings.db_path.with_name(
        f"{settings.db_path.stem}_checkpoints{settings.db_path.suffix}"
    )
    engine = LangGraphEngine(
        run_repository=run_repo,
        checkpoint_db_path=str(checkpoint_path),
        resolve_connectors=resolve_connectors,
        get_flow_spec=flow_service.get,
    )
    return RunService(
        engine=engine,
        flow_service=flow_service,
        connector_service=connector_service,
    )


@lru_cache
def get_catalog_service() -> CatalogService:
    """Return the catalog service singleton."""
    return CatalogService(StepRegistry, ConnectorRegistry)


def clear_dependency_caches() -> None:
    """Clear all provider caches (for test isolation)."""
    get_catalog_service.cache_clear()
    get_sync_service.cache_clear()
    get_run_service.cache_clear()
    get_flow_service.cache_clear()
    get_flow_repository.cache_clear()
    get_connector_service.cache_clear()
    get_secrets_service.cache_clear()
    get_session_factory.cache_clear()
    get_db_engine.cache_clear()
    get_settings.cache_clear()
