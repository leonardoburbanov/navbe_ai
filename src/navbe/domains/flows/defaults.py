"""Default flows seeded on first ``navbe serve`` (connectors + starter workflow).

Connectors are not a separate store — instances live on FlowSpecs. Seeding flows
is how a fresh install shows connectors in the UI and gives agents a runnable
base workflow.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from navbe.core.exceptions import NotFoundError, ValidationError
from navbe.core.paths import default_data_home
from navbe.domains.flows.service import FlowService

logger = logging.getLogger(__name__)

STARTER_FLOW_ID = "starter"
LANGFUSE_FLOW_ID = "langfuse_traces"


def _exports_dir() -> Path:
    """User-owned DuckDB export directory under the active data home."""
    path = default_data_home() / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_flow_specs() -> list[dict[str, Any]]:
    """Return built-in FlowSpec dicts (idempotent seed targets)."""
    duckdb_path = str(_exports_dir() / "langfuse.duckdb")
    return [
        {
            "flow_id": STARTER_FLOW_ID,
            "name": "Starter — HTTP ping",
            "entry_node": "ping",
            "connectors": {
                "http": {
                    "type": "http",
                    "config": {
                        "base_url": "https://httpbin.org",
                        "headers": {},
                        "timeout": 30,
                    },
                },
            },
            "nodes": [
                {
                    "id": "ping",
                    "step_type": "http_request",
                    "config": {
                        "connector": "http",
                        "method": "get",
                        "path": "/get",
                        "params": {"source": "navbe-starter"},
                    },
                }
            ],
            "edges": [],
        },
        {
            "flow_id": LANGFUSE_FLOW_ID,
            "name": "Langfuse traces → DuckDB",
            "entry_node": "read_traces",
            "connectors": {
                "langfuse": {
                    "type": "langfuse",
                    "config": {
                        "host": "https://cloud.langfuse.com",
                        "public_key": {"$secret": "LANGFUSE_PUBLIC_KEY"},
                        "secret_key": {"$secret": "LANGFUSE_SECRET_KEY"},
                        "timeout": 30,
                    },
                },
                "traces_db": {
                    "type": "duckdb",
                    "config": {"db_path": duckdb_path},
                },
            },
            "nodes": [
                {
                    "id": "read_traces",
                    "step_type": "http_request",
                    "config": {
                        "connector": "langfuse",
                        "method": "read",
                        "path": "",
                        "body_template": {},
                        "params": {"limit": 50},
                    },
                },
                {
                    "id": "store_probe",
                    "step_type": "http_request",
                    "config": {
                        "connector": "traces_db",
                        "method": "read",
                        "path": "",
                        "body_template": {
                            "sql": "SELECT 1 AS ok",
                        },
                    },
                },
            ],
            "edges": [{"from": "read_traces", "to": "store_probe"}],
        },
    ]


async def ensure_default_flows(flow_service: FlowService) -> list[str]:
    """Create missing built-in flows; skip ids that already exist.

    Returns the list of ``flow_id`` values that were created.
    """
    created: list[str] = []
    for spec in default_flow_specs():
        flow_id = str(spec["flow_id"])
        try:
            await flow_service.get(flow_id)
            continue
        except NotFoundError:
            pass
        try:
            await flow_service.create(spec)
            created.append(flow_id)
            logger.info("seeded default flow %s", flow_id)
        except ValidationError as exc:
            # Race: another process created it between get and create.
            if "already exists" in str(exc).lower():
                continue
            logger.warning("skip default flow %s: %s", flow_id, exc)
    return created
