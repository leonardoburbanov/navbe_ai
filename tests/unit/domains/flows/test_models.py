"""Tests for flow models."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError as PydanticValidationError

from navbe.domains.flows.models import EdgeSpec, FlowSpec, NodeSpec

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


def _demo_flow() -> dict:
    """Load the sales-bot demo FlowSpec dict."""
    return json.loads((FIXTURES / "sales_bot_objection_test.json").read_text(encoding="utf-8"))


def test_flowspec_parses_demo_json() -> None:
    """Full sales-bot demo flow_spec parses without error."""
    flow = FlowSpec.model_validate(_demo_flow())
    assert flow.flow_id == "sales_bot_objection_test"
    assert flow.entry_node == "turn_1"
    assert len(flow.nodes) == 7
    assert flow.edges[0].from_ == "turn_1"


def test_edge_from_alias_round_trip() -> None:
    """EdgeSpec accepts and emits the JSON key ``from``."""
    edge = EdgeSpec.model_validate({"from": "a", "to": "b"})
    assert edge.from_ == "a"
    dumped = edge.model_dump(by_alias=True)
    assert dumped == {"from": "a", "to": "b", "condition": None}
    assert "from_" not in dumped


def test_flowspec_rejects_empty_nodes() -> None:
    """Empty nodes list is rejected."""
    payload = {
        "flow_id": "empty",
        "entry_node": "n1",
        "nodes": [],
        "edges": [],
    }
    with pytest.raises(PydanticValidationError):
        FlowSpec.model_validate(payload)


def test_flowspec_rejects_extra_top_level_field() -> None:
    """Unknown top-level keys are rejected."""
    payload = _demo_flow()
    payload["typo_field"] = True
    with pytest.raises(PydanticValidationError):
        FlowSpec.model_validate(payload)


def test_nodespec_rejects_extra_field() -> None:
    """Unknown fields on NodeSpec outer shape are rejected."""
    with pytest.raises(PydanticValidationError):
        NodeSpec.model_validate(
            {"id": "n1", "step_type": "set_var", "config": {}, "typo": 1}
        )


def test_edge_condition_optional_for_direct_edges() -> None:
    """Direct edges parse with condition=None."""
    edge = EdgeSpec.model_validate({"from": "a", "to": "b"})
    assert edge.condition is None
