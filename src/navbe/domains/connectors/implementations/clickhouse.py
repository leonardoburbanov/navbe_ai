"""ClickHouse connector — parameterized CRUD via clickhouse-connect."""

from __future__ import annotations

import asyncio
from typing import Any

import clickhouse_connect

from navbe.core.exceptions import ExecutionError
from navbe.domains.connectors.implementations._payload import action_payload
from navbe.domains.connectors.interfaces import ConnectorConfig
from navbe.domains.connectors.registry import ConnectorRegistry


class ClickHouseConfig(ConnectorConfig):
    """ClickHouse HTTP client config (password via ``$secret``)."""

    host: str
    port: int = 8123
    username: str = "default"
    password: str = ""
    database: str = "default"
    secure: bool = False
    timeout: int = 30


@ConnectorRegistry.register("clickhouse")
class ClickHouseConnector:
    """CRUD helpers against ClickHouse (sync client via ``asyncio.to_thread``)."""

    config_schema = ClickHouseConfig
    actions = {
        "create": "INSERT rows",
        "read": "SELECT / query",
        "update": "ALTER UPDATE or sql",
        "delete": "ALTER DELETE or sql",
    }

    def __init__(self, config: dict[str, Any]) -> None:
        """Validate ClickHouse config."""
        self.config = ClickHouseConfig.model_validate(config)

    def _client(self) -> Any:
        return clickhouse_connect.get_client(
            host=self.config.host,
            port=self.config.port,
            username=self.config.username,
            password=self.config.password,
            database=self.config.database,
            secure=self.config.secure,
            connect_timeout=self.config.timeout,
        )

    async def test_connection(self) -> bool:
        """Return True when ``SELECT 1`` succeeds."""

        def _probe() -> bool:
            try:
                client = self._client()
                try:
                    client.query("SELECT 1")
                    return True
                finally:
                    client.close()
            except Exception:
                return False

        return await asyncio.to_thread(_probe)

    async def execute(self, action: str, payload: dict[str, Any]) -> Any:
        """Run a CRUD action."""
        if action not in self.actions:
            raise ExecutionError(
                f"Unsupported action '{action}' for clickhouse connector",
                details={"action": action, "available": list(self.actions)},
            )
        fields = action_payload(payload, "sql", "table", "rows", "where", "set", "columns")

        def _run() -> Any:
            try:
                client = self._client()
                try:
                    if fields.get("sql"):
                        result = client.query(fields["sql"], parameters=fields.get("params") or {})
                        return {
                            "columns": list(result.column_names),
                            "rows": [
                                dict(zip(result.column_names, row, strict=False))
                                for row in result.result_rows
                            ],
                        }
                    if action == "create":
                        return self._create(client, fields)
                    if action == "read":
                        return self._read(client, fields)
                    if action == "update":
                        return self._update(client, fields)
                    return self._delete(client, fields)
                finally:
                    client.close()
            except ExecutionError:
                raise
            except Exception as exc:
                raise ExecutionError(
                    "clickhouse action failed",
                    details={"action": action},
                ) from exc

        return await asyncio.to_thread(_run)

    def _create(self, client: Any, fields: dict[str, Any]) -> dict[str, Any]:
        table = fields.get("table")
        rows = fields.get("rows")
        if not table or not isinstance(rows, list) or not rows:
            raise ExecutionError(
                "create requires table and non-empty rows",
                details={"fields": ["table", "rows"]},
            )
        columns = fields.get("columns") or list(rows[0].keys())
        data = [[row.get(c) for c in columns] for row in rows]
        client.insert(table, data, column_names=columns)
        return {"inserted": len(rows)}

    def _read(self, client: Any, fields: dict[str, Any]) -> dict[str, Any]:
        table = fields.get("table")
        if not table:
            raise ExecutionError(
                "read requires table or sql",
                details={"fields": ["table", "sql"]},
            )
        query = f"SELECT * FROM {table}"
        parameters: dict[str, Any] = {}
        where = fields.get("where")
        if isinstance(where, dict) and where:
            clauses = []
            for i, (key, value) in enumerate(where.items()):
                pname = f"w{i}"
                clauses.append(f"{key} = {{{pname}:String}}")
                parameters[pname] = str(value)
            query += " WHERE " + " AND ".join(clauses)
        if fields.get("limit") is not None:
            query += f" LIMIT {int(fields['limit'])}"
        result = client.query(query, parameters=parameters)
        return {
            "columns": list(result.column_names),
            "rows": [
                dict(zip(result.column_names, row, strict=False))
                for row in result.result_rows
            ],
        }

    def _update(self, client: Any, fields: dict[str, Any]) -> dict[str, Any]:
        table = fields.get("table")
        sets = fields.get("set")
        where = fields.get("where")
        if not table or not isinstance(sets, dict) or not isinstance(where, dict) or not where:
            raise ExecutionError(
                "update requires table, set, and where",
                details={"fields": ["table", "set", "where"]},
            )
        set_sql = ", ".join(f"{k} = {{{k}:String}}" for k in sets)
        where_sql = " AND ".join(f"{k} = {{w_{k}:String}}" for k in where)
        parameters = {
            **{k: str(v) for k, v in sets.items()},
            **{f"w_{k}": str(v) for k, v in where.items()},
        }
        client.command(
            f"ALTER TABLE {table} UPDATE {set_sql} WHERE {where_sql}",
            parameters=parameters,
        )
        return {"ok": True}

    def _delete(self, client: Any, fields: dict[str, Any]) -> dict[str, Any]:
        table = fields.get("table")
        where = fields.get("where")
        if not table or not isinstance(where, dict) or not where:
            raise ExecutionError(
                "delete requires table and where",
                details={"fields": ["table", "where"]},
            )
        where_sql = " AND ".join(f"{k} = {{w_{k}:String}}" for k in where)
        parameters = {f"w_{k}": str(v) for k, v in where.items()}
        client.command(f"ALTER TABLE {table} DELETE WHERE {where_sql}", parameters=parameters)
        return {"ok": True}
