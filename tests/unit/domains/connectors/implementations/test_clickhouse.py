"""Tests for ClickHouse connector (mocked client)."""

from unittest.mock import MagicMock, patch

import pytest

from navbe.core.exceptions import ExecutionError
from navbe.domains.connectors.implementations.clickhouse import ClickHouseConnector


async def test_create_inserts_rows() -> None:
    """create calls client.insert."""
    mock_client = MagicMock()
    with patch(
        "navbe.domains.connectors.implementations.clickhouse.clickhouse_connect.get_client",
        return_value=mock_client,
    ):
        connector = ClickHouseConnector({"host": "localhost"})
        result = await connector.execute(
            "create",
            {"table": "events", "rows": [{"id": 1, "name": "x"}]},
        )

    assert result == {"inserted": 1}
    mock_client.insert.assert_called_once()
    mock_client.close.assert_called_once()


async def test_unsupported_action() -> None:
    """Unknown actions raise ExecutionError."""
    connector = ClickHouseConnector({"host": "localhost"})
    with pytest.raises(ExecutionError):
        await connector.execute("optimize", {})
