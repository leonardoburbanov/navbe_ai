"""Tests for PostgreSQL connector (mocked AsyncConnection)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from navbe.core.exceptions import ExecutionError
from navbe.domains.connectors.implementations.postgresql import PostgreSQLConnector


async def test_create_inserts_and_returns_row() -> None:
    """create runs INSERT RETURNING and returns the row."""
    mock_cur = AsyncMock()
    mock_cur.fetchone.return_value = {"id": 1, "name": "ada"}
    mock_cur.__aenter__.return_value = mock_cur
    mock_cur.__aexit__.return_value = None

    mock_conn = AsyncMock()
    mock_conn.cursor = MagicMock(return_value=mock_cur)
    mock_conn.__aenter__.return_value = mock_conn
    mock_conn.__aexit__.return_value = None

    with patch(
        "navbe.domains.connectors.implementations.postgresql.AsyncConnection.connect",
        new=AsyncMock(return_value=mock_conn),
    ):
        connector = PostgreSQLConnector({"dsn": "postgresql://localhost/app"})
        result = await connector.execute(
            "create",
            {"table": "users", "values": {"name": "ada"}},
        )

    assert result == {"row": {"id": 1, "name": "ada"}}
    mock_cur.execute.assert_awaited()


async def test_missing_dsn_raises() -> None:
    """Config without dsn or host fields fails validation."""
    with pytest.raises(ValidationError):
        PostgreSQLConnector({"port": 5432})


async def test_unsupported_action() -> None:
    """Unknown actions raise ExecutionError."""
    connector = PostgreSQLConnector({"dsn": "postgresql://localhost/app"})
    with patch(
        "navbe.domains.connectors.implementations.postgresql.AsyncConnection.connect",
        new=AsyncMock(),
    ):
        with pytest.raises(ExecutionError):
            await connector.execute("truncate", {})