"""Tests for DuckDB file connector (temp file)."""

from pathlib import Path

import pytest

from navbe.core.exceptions import ExecutionError
from navbe.domains.connectors.implementations.duckdb_file import DuckDBFileConnector


async def test_crud_roundtrip(tmp_path: Path) -> None:
    """create/read/update/delete against a temp .duckdb file."""
    db_path = str(tmp_path / "demo.duckdb")
    connector = DuckDBFileConnector({"db_path": db_path})

    # Bootstrap table via sql
    await connector.execute(
        "create",
        {"sql": "CREATE TABLE items (id INTEGER, name VARCHAR)"},
    )
    await connector.execute(
        "create",
        {"table": "items", "rows": [{"id": 1, "name": "a"}]},
    )
    read = await connector.execute("read", {"table": "items"})
    assert read["rows"] == [{"id": 1, "name": "a"}]

    await connector.execute(
        "update",
        {"table": "items", "set": {"name": "b"}, "where": {"id": 1}},
    )
    read2 = await connector.execute("read", {"table": "items", "where": {"id": 1}})
    assert read2["rows"][0]["name"] == "b"

    await connector.execute("delete", {"table": "items", "where": {"id": 1}})
    read3 = await connector.execute("read", {"table": "items"})
    assert read3["rows"] == []


async def test_connection_opens_file(tmp_path: Path) -> None:
    """test_connection succeeds on a writable path."""
    db_path = str(tmp_path / "ok.duckdb")
    connector = DuckDBFileConnector({"db_path": db_path})
    assert await connector.test_connection() is True


async def test_unsupported_action(tmp_path: Path) -> None:
    """Unknown actions raise ExecutionError."""
    connector = DuckDBFileConnector({"db_path": str(tmp_path / "x.duckdb")})
    with pytest.raises(ExecutionError):
        await connector.execute("drop", {})
