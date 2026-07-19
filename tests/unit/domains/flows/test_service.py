"""Tests for FlowService."""

import copy
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

import navbe.domains.steps.implementations  # noqa: F401
from navbe.core.exceptions import ValidationError
from navbe.domains.flows.models import FlowSpec
from navbe.domains.flows.service import FlowService
from tests.unit.domains.flows.test_interfaces import FakeFlowRepository

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


def _demo_dict() -> dict:
    """Load mutable demo flow dict."""
    return copy.deepcopy(
        json.loads((FIXTURES / "sales_bot_objection_test.json").read_text(encoding="utf-8"))
    )


async def test_create_valid_flow_saves_via_repository() -> None:
    """Valid demo dict is parsed and saved once."""
    repo = FakeFlowRepository()
    service = FlowService(repo)
    meta = await service.create(_demo_dict())
    assert meta.flow_id == "sales_bot_objection_test"
    assert len(repo.saved) == 1
    assert isinstance(repo.saved[0], FlowSpec)
    assert repo.saved[0].entry_node == "turn_1"


async def test_create_malformed_dict_raises_validation_error_before_saving() -> None:
    """Missing entry_node fails before repository.save."""
    repo = FakeFlowRepository()
    repo.save = AsyncMock(wraps=repo.save)
    payload = _demo_dict()
    del payload["entry_node"]
    with pytest.raises(ValidationError):
        await FlowService(repo).create(payload)
    repo.save.assert_not_called()


async def test_create_graph_invalid_raises_with_issues_in_details() -> None:
    """Graph issues land in ValidationError.details['issues']."""
    repo = FakeFlowRepository()
    repo.save = AsyncMock(wraps=repo.save)
    payload = _demo_dict()
    payload["nodes"].append(
        {"id": "orphan", "step_type": "set_var", "config": {"var_name": "x", "value_from": "x"}}
    )
    with pytest.raises(ValidationError) as exc_info:
        await FlowService(repo).create(payload)
    assert any(issue["code"] == "orphan_node" for issue in exc_info.value.details["issues"])
    repo.save.assert_not_called()


async def test_get_delegates_to_repository() -> None:
    """get() forwards to repository.get."""
    repo = FakeFlowRepository()
    spec = FlowSpec.model_validate(_demo_dict())
    await repo.save(spec)
    repo.get = AsyncMock(wraps=repo.get)
    retrieved = await FlowService(repo).get("sales_bot_objection_test")
    repo.get.assert_awaited_once_with("sales_bot_objection_test")
    assert retrieved.flow_id == "sales_bot_objection_test"


async def test_list_delegates_to_repository() -> None:
    """list() forwards to repository.list."""
    repo = FakeFlowRepository()
    await repo.save(FlowSpec.model_validate(_demo_dict()))
    repo.list = AsyncMock(wraps=repo.list)
    listed = await FlowService(repo).list()
    repo.list.assert_awaited_once()
    assert len(listed) == 1
