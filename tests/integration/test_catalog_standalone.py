"""Cross-domain catalog ↔ validator contract test."""

import navbe.domains.connectors.implementations  # noqa: F401
import navbe.domains.steps.implementations  # noqa: F401
from navbe.domains.catalog.service import CatalogService
from navbe.domains.connectors.registry import ConnectorRegistry
from navbe.domains.flows.models import FlowSpec
from navbe.domains.flows.validator import RESERVED_STEP_TYPES, validate_graph
from navbe.domains.steps.registry import StepRegistry


async def test_catalog_matches_what_flows_validator_accepts() -> None:
    """Every catalog type is accepted by the validator, and vice versa.

    Cross-domain contract: an agent building from the catalog must never hit
    a validation error for an unrecognized type. ``approval`` is structural
    (not registry-backed) and must stay in sync with RESERVED_STEP_TYPES.
    """
    catalog = CatalogService()
    steps_catalog = await catalog.get_steps_catalog()
    connectors_catalog = await catalog.get_connectors_catalog()

    for step_type in steps_catalog:
        if step_type == "approval":
            assert step_type in RESERVED_STEP_TYPES
            continue
        assert step_type in StepRegistry.list_all()

    for step_type in StepRegistry.list_all():
        assert step_type in steps_catalog

    for connector_type in connectors_catalog:
        assert connector_type in ConnectorRegistry.list_all()

    for connector_type in ConnectorRegistry.list_all():
        assert connector_type in connectors_catalog

    flow = FlowSpec.model_validate(
        {
            "flow_id": "approval_gate",
            "entry_node": "gate",
            "nodes": [
                {
                    "id": "gate",
                    "step_type": "approval",
                    "config": {"message": "OK?"},
                }
            ],
            "edges": [],
        }
    )
    assert validate_graph(flow).valid is True
