"""Tests for transform step.

Join tests are intentionally absent in EPIC 1.6 because this step exposes one
registered source named ``input``; multi-source joins belong to a later
merge-via-SQL step if reintroduced.
"""

import pytest

from navbe.core.exceptions import ExecutionError
from navbe.domains.steps.implementations.transform import TransformStep
from navbe.domains.steps.interfaces import StepContext


async def test_simple_select() -> None:
    """Filter input rows with SQL."""
    step = TransformStep({"query": "SELECT * FROM input WHERE x > 1 ORDER BY x"})
    ctx = StepContext(node_id="n1", input_data=[{"x": 1}, {"x": 2}, {"x": 3}])
    assert await step.run(ctx) == [{"x": 2}, {"x": 3}]


async def test_group_by_aggregation() -> None:
    """Aggregate rows grouped by a category."""
    step = TransformStep(
        {
            "query": (
                "SELECT category, SUM(amount) AS total "
                "FROM input GROUP BY category ORDER BY category"
            )
        }
    )
    ctx = StepContext(
        node_id="n1",
        input_data=[
            {"category": "a", "amount": 2},
            {"category": "a", "amount": 3},
            {"category": "b", "amount": 4},
        ],
    )
    assert await step.run(ctx) == [
        {"category": "a", "total": 5},
        {"category": "b", "total": 4},
    ]


async def test_invalid_sql_raises_execution_error() -> None:
    """Malformed SQL raises Navbe ExecutionError."""
    step = TransformStep({"query": "SELECT FROM"})

    with pytest.raises(ExecutionError):
        await step.run(StepContext(node_id="n1", input_data=[{"x": 1}]))


async def test_empty_input_returns_empty_list() -> None:
    """Empty list input returns an empty list without crashing."""
    step = TransformStep({"query": "SELECT * FROM input"})
    assert await step.run(StepContext(node_id="n1", input_data=[])) == []
