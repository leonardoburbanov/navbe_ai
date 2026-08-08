"""Agent-facing catalog of registered steps and connectors."""

from typing import Any, cast

from navbe.domains.connectors.registry import ConnectorRegistry
from navbe.domains.steps.registry import StepRegistry

# approval is handled by graph_compiler, not StepRegistry — agents still need
# to discover it when authoring FlowSpecs.
_SYNTHETIC_STEPS: dict[str, dict[str, Any]] = {
    "approval": {
        "step_type": "approval",
        "title": "Approval",
        "description": (
            "Pauses execution for human approval. Handled structurally "
            "by the execution engine, not a registered Step class."
        ),
        "config_schema": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "description": (
                "Pauses execution for human approval. Handled structurally "
                "by the execution engine, not a registered Step class."
            ),
        },
    }
}

_STEP_BLURBS: dict[str, str] = {
    "set_var": "Store a value into flow state for later steps.",
    "http_request": "Call an HTTP endpoint via a configured http connector.",
    "transform": "Run in-memory DuckDB SQL over prior step outputs.",
    "llm_call": "Call an LLM through a connector that supports chat/completions.",
    "router_step": "Branch to the next node based on an expression.",
    "approval": "Pause for a human approve/reject decision.",
}

_CONNECTOR_BLURBS: dict[str, str] = {
    "http": "Generic HTTP client with base URL, headers, and timeout.",
    "langfuse": "Read Langfuse traces and observations for export workflows.",
    "duckdb_file": "Write/query a local DuckDB file (exports live under ~/.navbe).",
    "postgresql": "PostgreSQL queries and writes.",
    "mongodb": "MongoDB find/insert/update operations.",
    "clickhouse": "ClickHouse analytics queries.",
    "supabase": "Supabase / PostgREST-style access.",
    "pinecone": "Vector upsert and query.",
    "resend": "Transactional email via Resend.",
    "google_calendar": "Google Calendar events.",
}

_CONNECTOR_SECRETS: dict[str, list[str]] = {
    "langfuse": ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"],
    "resend": ["RESEND_API_KEY"],
    "pinecone": ["PINECONE_API_KEY"],
}


def _humanize(key: str) -> str:
    """Turn snake_case ids into Title Case labels."""
    return " ".join(part.capitalize() for part in key.split("_") if part)


def _schema_description(schema: dict[str, Any]) -> str | None:
    """Pull a description string from a JSON Schema object if present."""
    desc = schema.get("description")
    return desc if isinstance(desc, str) and desc.strip() else None


def _schema_title(schema: dict[str, Any]) -> str | None:
    """Pull a title string from a JSON Schema object if present."""
    title = schema.get("title")
    return title if isinstance(title, str) and title.strip() else None


class CatalogService:
    """Read-only catalog over StepRegistry and ConnectorRegistry."""

    def __init__(
        self,
        step_registry: type[StepRegistry] = StepRegistry,
        connector_registry: type[ConnectorRegistry] = ConnectorRegistry,
    ) -> None:
        """Bind registry classes used for catalog lookups."""
        self._steps = step_registry
        self._connectors = connector_registry

    async def get_steps_catalog(self) -> dict[str, dict]:
        """Return JSON Schema catalog for all discoverable step types."""
        registered: dict[str, dict] = {}
        for key, step_cls in self._steps.list_all().items():
            schema = cast(Any, step_cls).config_schema.model_json_schema()
            registered[key] = {
                "step_type": key,
                "title": _schema_title(schema) or _humanize(key),
                "description": _schema_description(schema)
                or _STEP_BLURBS.get(key, f"Step type '{key}'."),
                "config_schema": schema,
            }
        return {**registered, **_SYNTHETIC_STEPS}

    async def get_connectors_catalog(self) -> dict[str, dict]:
        """Return JSON Schema catalog for all registered connector types."""
        out: dict[str, dict] = {}
        for key, connector_cls in self._connectors.list_all().items():
            schema = cast(Any, connector_cls).config_schema.model_json_schema()
            out[key] = {
                "connector_type": key,
                "title": _schema_title(schema) or _humanize(key),
                "description": _schema_description(schema)
                or _CONNECTOR_BLURBS.get(key, f"Connector type '{key}'."),
                "config_schema": schema,
                "actions": cast(Any, connector_cls).actions,
                "required_secrets": _CONNECTOR_SECRETS.get(key, []),
            }
        return out

    async def get_full_catalog(self) -> dict:
        """Return combined steps + connectors catalog."""
        return {
            "steps": await self.get_steps_catalog(),
            "connectors": await self.get_connectors_catalog(),
        }
