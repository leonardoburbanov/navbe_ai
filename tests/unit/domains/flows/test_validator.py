"""Tests for flow graph validator."""

import copy
import json
from pathlib import Path

import navbe.domains.steps.implementations  # noqa: F401
from navbe.domains.flows.models import FlowSpec
from navbe.domains.flows.validator import validate_graph

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


def _demo() -> dict:
    """Load and return a mutable copy of the demo flow dict."""
    return copy.deepcopy(
        json.loads((FIXTURES / "sales_bot_objection_test.json").read_text(encoding="utf-8"))
    )


def test_valid_demo_flow_passes() -> None:
    """Full sales-bot demo flow validates cleanly."""
    result = validate_graph(FlowSpec.model_validate(_demo()))
    assert result.valid is True
    assert result.issues == []


def test_missing_entry_node_detected() -> None:
    """Unknown entry_node produces missing_entry_node."""
    payload = _demo()
    payload["entry_node"] = "nonexistent"
    result = validate_graph(FlowSpec.model_validate(payload))
    assert result.valid is False
    assert any(issue.code == "missing_entry_node" for issue in result.issues)


def test_unknown_step_type_detected() -> None:
    """Unregistered step_type is reported with node_id."""
    payload = _demo()
    payload["nodes"][0]["step_type"] = "not_a_real_step"
    result = validate_graph(FlowSpec.model_validate(payload))
    assert any(
        issue.code == "unknown_step_type" and issue.node_id == "turn_1"
        for issue in result.issues
    )


def test_edge_referencing_nonexistent_node_detected() -> None:
    """Edges pointing at missing nodes are reported."""
    payload = _demo()
    payload["edges"].append({"from": "ghost_from", "to": "ghost_to"})
    result = validate_graph(FlowSpec.model_validate(payload))
    codes = {issue.code for issue in result.issues}
    assert "edge_from_not_found" in codes
    assert "edge_to_not_found" in codes


def test_orphan_node_detected() -> None:
    """Nodes unreachable from entry_node are reported."""
    payload = _demo()
    payload["nodes"].append(
        {"id": "orphan", "step_type": "set_var", "config": {"var_name": "x", "value_from": "x"}}
    )
    result = validate_graph(FlowSpec.model_validate(payload))
    assert any(
        issue.code == "orphan_node" and issue.node_id == "orphan" for issue in result.issues
    )


def test_unknown_connector_reference_detected() -> None:
    """http_request connector names must exist in flow_spec.connectors."""
    payload = _demo()
    for node in payload["nodes"]:
        if node["id"] == "persist_outcome":
            node["config"]["connector"] = "ghost"
            break
    result = validate_graph(FlowSpec.model_validate(payload))
    assert any(
        issue.code == "unknown_connector_reference" and issue.node_id == "persist_outcome"
        for issue in result.issues
    )


def test_multiple_issues_all_reported_together() -> None:
    """Validator returns every issue in one pass."""
    payload = _demo()
    payload["entry_node"] = "missing_entry"
    payload["nodes"][0]["step_type"] = "not_a_real_step"
    payload["nodes"].append(
        {"id": "orphan", "step_type": "set_var", "config": {"var_name": "x", "value_from": "x"}}
    )
    result = validate_graph(FlowSpec.model_validate(payload))
    codes = {issue.code for issue in result.issues}
    assert "missing_entry_node" in codes
    assert "unknown_step_type" in codes
    assert "orphan_node" in codes
    assert len(result.issues) >= 3


def test_cyclic_flow_is_not_flagged_as_invalid() -> None:
    """Legitimate router back-edges do not produce validation issues."""
    result = validate_graph(FlowSpec.model_validate(_demo()))
    assert result.valid is True
    assert not any("cycle" in issue.code for issue in result.issues)
    assert any(
        edge.from_ == "router" and edge.to == "capture_objection"
        for edge in FlowSpec.model_validate(_demo()).edges
    )
