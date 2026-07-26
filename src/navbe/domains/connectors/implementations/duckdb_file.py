"""DuckDB file connector — external user-owned ``.duckdb`` path (not Navbe analytics)."""

from __future__ import annotations

import asyncio
from typing import Any

import duckdb

from navbe.core.exceptions import ExecutionError
from navbe.domains.connectors.implementations._payload import action_payload
from navbe.domains.connectors.interfaces import ConnectorConfig
from navbe.domains.connectors.registry import ConnectorRegistry


class DuckDBFileConfig(ConnectorConfig):
    """Path to a user-owned DuckDB database file. No default under Navbe data dirs."""

    db_path: str


@ConnectorRegistry.register("duckdb")
class DuckDBFileConnector:
    """CRUD helpers against an external DuckDB file via ``asyncio.to_thread``."""

    config_schema = DuckDBFileConfig
    actions = {
        "create": "INSERT rows into a table (or run sql)",
        "read": "SELECT / query (table helper or sql)",
        "update": "UPDATE rows (or run sql)",
        "delete": "DELETE rows (or run sql)",
    }

    def __init__(self, config: dict[str, Any]) -> None:
        """Validate DuckDB file config."""
        self.config = DuckDBFileConfig.model_validate(config)
        if not self.config.db_path.strip():
            raise ExecutionError(
                "duckdb requires non-empty db_path",
                details={"field": "db_path"},
            )

    async def test_connection(self) -> bool:
        """Return True when the file opens and ``SELECT 1`` works."""

        def _probe() -> bool:
            try:
                con = duckdb.connect(self.config.db_path)
                try:
                    con.execute("SELECT 1").fetchone()
                    return True
                finally:
                    con.close()
            except duckdb.Error:
                return False

        return await asyncio.to_thread(_probe)

    async def execute(self, action: str, payload: dict[str, Any]) -> Any:
        """Run a CRUD action against ``db_path``."""
        if action not in self.actions:
            raise ExecutionError(
                f"Unsupported action '{action}' for duckdb connector",
                details={"action": action, "available": list(self.actions)},
            )
        fields = action_payload(payload, "sql", "table", "rows", "where", "set", "values")

        def _run() -> Any:
            try:
                con = duckdb.connect(self.config.db_path)
                try:
                    if fields.get("sql"):
                        result = con.execute(fields["sql"], fields.get("params") or [])
                        if action == "read" or result.description:
                            cols = [d[0] for d in result.description] if result.description else []
                            rows = result.fetchall()
                            return {
                                "columns": cols,
                                "rows": [dict(zip(cols, row, strict=False)) for row in rows],
                            }
                        return {"ok": True}
                    if action == "create":
                        return self._create(con, fields)
                    if action == "read":
                        return self._read(con, fields)
                    if action == "update":
                        return self._update(con, fields)
                    return self._delete(con, fields)
                finally:
                    con.close()
            except ExecutionError:
                raise
            except duckdb.Error as exc:
                raise ExecutionError(
                    "duckdb action failed",
                    details={"action": action},
                ) from exc

        return await asyncio.to_thread(_run)

    def _create(self, con: duckdb.DuckDBPyConnection, fields: dict[str, Any]) -> dict[str, Any]:
        table = fields.get("table")
        rows = fields.get("rows") or fields.get("values")
        if not table or rows is None:
            raise ExecutionError(
                "create requires table and rows/values",
                details={"fields": ["table", "rows"]},
            )
        if isinstance(rows, dict):
            rows = [rows]
        if not isinstance(rows, list) or not rows:
            raise ExecutionError(
                "create requires non-empty rows list",
                details={"field": "rows"},
            )
        cols = list(rows[0].keys())
        placeholders = ", ".join(["?"] * len(cols))
        col_sql = ", ".join(cols)
        sql_text = f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders})"
        for row in rows:
            con.execute(sql_text, [row[c] for c in cols])
        return {"inserted": len(rows)}

    def _read(self, con: duckdb.DuckDBPyConnection, fields: dict[str, Any]) -> dict[str, Any]:
        table = fields.get("table")
        if not table:
            raise ExecutionError(
                "read requires table or sql",
                details={"fields": ["table", "sql"]},
            )
        sql_text = f"SELECT * FROM {table}"
        params: list[Any] = []
        where = fields.get("where")
        if isinstance(where, dict) and where:
            clauses = [f"{k} = ?" for k in where]
            sql_text += " WHERE " + " AND ".join(clauses)
            params.extend(where.values())
        if fields.get("limit") is not None:
            sql_text += f" LIMIT {int(fields['limit'])}"
        result = con.execute(sql_text, params)
        cols = [d[0] for d in result.description] if result.description else []
        data = result.fetchall()
        return {"columns": cols, "rows": [dict(zip(cols, row, strict=False)) for row in data]}

    def _update(self, con: duckdb.DuckDBPyConnection, fields: dict[str, Any]) -> dict[str, Any]:
        table = fields.get("table")
        sets = fields.get("set")
        where = fields.get("where")
        if not table or not isinstance(sets, dict) or not isinstance(where, dict) or not where:
            raise ExecutionError(
                "update requires table, set, and where",
                details={"fields": ["table", "set", "where"]},
            )
        set_sql = ", ".join(f"{k} = ?" for k in sets)
        where_sql = " AND ".join(f"{k} = ?" for k in where)
        params = list(sets.values()) + list(where.values())
        con.execute(f"UPDATE {table} SET {set_sql} WHERE {where_sql}", params)
        return {"ok": True}

    def _delete(self, con: duckdb.DuckDBPyConnection, fields: dict[str, Any]) -> dict[str, Any]:
        table = fields.get("table")
        where = fields.get("where")
        if not table or not isinstance(where, dict) or not where:
            raise ExecutionError(
                "delete requires table and where",
                details={"fields": ["table", "where"]},
            )
        where_sql = " AND ".join(f"{k} = ?" for k in where)
        con.execute(f"DELETE FROM {table} WHERE {where_sql}", list(where.values()))
        return {"ok": True}
