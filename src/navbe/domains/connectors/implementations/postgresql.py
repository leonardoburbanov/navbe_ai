"""PostgreSQL connector — parameterized table CRUD via psycopg async."""

from __future__ import annotations

from typing import Any, Self, cast

from psycopg import AsyncConnection, sql
from psycopg.rows import dict_row
from pydantic import model_validator

from navbe.core.exceptions import ExecutionError
from navbe.domains.connectors.implementations._payload import action_payload
from navbe.domains.connectors.interfaces import ConnectorConfig
from navbe.domains.connectors.registry import ConnectorRegistry


class PostgreSQLConfig(ConnectorConfig):
    """PostgreSQL config: ``dsn`` or discrete host fields (password via ``$secret``)."""

    dsn: str | None = None
    host: str | None = None
    port: int = 5432
    user: str | None = None
    password: str | None = None
    dbname: str | None = None
    timeout: int = 30

    @model_validator(mode="after")
    def require_dsn_or_host_fields(self) -> Self:
        """Require either a DSN or host+user+dbname."""
        if self.dsn or (self.host and self.user and self.dbname):
            return self
        raise ValueError("postgresql requires dsn or host+user+dbname")


@ConnectorRegistry.register("postgresql")
class PostgreSQLConnector:
    """CRUD helpers against PostgreSQL tables (no multi-statement scripts)."""

    config_schema = PostgreSQLConfig
    actions = {
        "create": "INSERT row(s)",
        "read": "SELECT rows (table helper or sql+params)",
        "update": "UPDATE rows",
        "delete": "DELETE rows",
    }

    def __init__(self, config: dict[str, Any]) -> None:
        """Validate PostgreSQL config."""
        self.config = PostgreSQLConfig.model_validate(config)

    def _conninfo(self) -> str:
        if self.config.dsn:
            return self.config.dsn
        parts = [
            f"host={self.config.host}",
            f"port={self.config.port}",
            f"user={self.config.user}",
            f"dbname={self.config.dbname}",
        ]
        if self.config.password is not None:
            parts.append(f"password={self.config.password}")
        return " ".join(parts)

    async def _connect(self) -> Any:
        return await AsyncConnection.connect(
            self._conninfo(),
            row_factory=cast(Any, dict_row),
            connect_timeout=self.config.timeout,
        )

    async def test_connection(self) -> bool:
        """Return True when ``SELECT 1`` succeeds."""
        try:
            async with await self._connect() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1")
                    await cur.fetchone()
            return True
        except Exception:
            return False

    async def execute(self, action: str, payload: dict[str, Any]) -> Any:
        """Run a CRUD action."""
        if action not in self.actions:
            raise ExecutionError(
                f"Unsupported action '{action}' for postgresql connector",
                details={"action": action, "available": list(self.actions)},
            )
        fields = action_payload(
            payload, "table", "values", "columns", "where", "set", "sql", "params"
        )

        try:
            async with await self._connect() as conn:
                async with conn.cursor() as cur:
                    if action == "create":
                        return await self._create(cur, fields)
                    if action == "read":
                        return await self._read(cur, fields)
                    if action == "update":
                        return await self._update(cur, fields)
                    return await self._delete(cur, fields)
        except ExecutionError:
            raise
        except Exception as exc:
            raise ExecutionError(
                "postgresql action failed",
                details={"action": action},
            ) from exc

    async def _create(self, cur: Any, fields: dict[str, Any]) -> dict[str, Any]:
        table = fields.get("table")
        values = fields.get("values")
        if not table or not isinstance(values, dict):
            raise ExecutionError(
                "create requires table and values object",
                details={"fields": ["table", "values"]},
            )
        cols = [str(c) for c in values.keys()]
        query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING *").format(
            sql.Identifier(str(table)),
            sql.SQL(", ").join([sql.Identifier(c) for c in cols]),
            sql.SQL(", ").join([sql.Placeholder()] * len(cols)),
        )
        await cur.execute(query, [values[c] for c in cols])
        row = await cur.fetchone()
        return {"row": dict(row) if row else None}

    async def _read(self, cur: Any, fields: dict[str, Any]) -> dict[str, Any]:
        if fields.get("sql"):
            await cur.execute(fields["sql"], fields.get("params") or [])
            rows = await cur.fetchall()
            return {"rows": [dict(r) for r in rows]}
        table = fields.get("table")
        if not table:
            raise ExecutionError(
                "read requires table or sql",
                details={"fields": ["table", "sql"]},
            )
        columns = fields.get("columns") or ["*"]
        if columns == ["*"]:
            select = sql.SQL("*")
        else:
            select = sql.SQL(", ").join([sql.Identifier(c) for c in columns])
        query = sql.SQL("SELECT {} FROM {}").format(select, sql.Identifier(table))
        params: list[Any] = []
        where = fields.get("where")
        if isinstance(where, dict) and where:
            clauses = []
            for key, value in where.items():
                clauses.append(sql.SQL("{} = {}").format(sql.Identifier(key), sql.Placeholder()))
                params.append(value)
            query = sql.SQL("{} WHERE {}").format(query, sql.SQL(" AND ").join(clauses))
        limit = fields.get("limit")
        if limit is not None:
            query = sql.SQL("{} LIMIT {}").format(query, sql.Literal(int(limit)))
        await cur.execute(query, params)
        rows = await cur.fetchall()
        return {"rows": [dict(r) for r in rows]}

    async def _update(self, cur: Any, fields: dict[str, Any]) -> dict[str, Any]:
        table = fields.get("table")
        sets = fields.get("set")
        where = fields.get("where")
        if not table or not isinstance(sets, dict) or not isinstance(where, dict) or not where:
            raise ExecutionError(
                "update requires table, set, and where",
                details={"fields": ["table", "set", "where"]},
            )
        set_parts = []
        params: list[Any] = []
        for key, value in sets.items():
            set_parts.append(sql.SQL("{} = {}").format(sql.Identifier(key), sql.Placeholder()))
            params.append(value)
        where_parts = []
        for key, value in where.items():
            where_parts.append(sql.SQL("{} = {}").format(sql.Identifier(key), sql.Placeholder()))
            params.append(value)
        query = sql.SQL("UPDATE {} SET {} WHERE {}").format(
            sql.Identifier(table),
            sql.SQL(", ").join(set_parts),
            sql.SQL(" AND ").join(where_parts),
        )
        await cur.execute(query, params)
        return {"rowcount": cur.rowcount}

    async def _delete(self, cur: Any, fields: dict[str, Any]) -> dict[str, Any]:
        table = fields.get("table")
        where = fields.get("where")
        if not table or not isinstance(where, dict) or not where:
            raise ExecutionError(
                "delete requires table and where",
                details={"fields": ["table", "where"]},
            )
        where_parts = []
        params: list[Any] = []
        for key, value in where.items():
            where_parts.append(sql.SQL("{} = {}").format(sql.Identifier(key), sql.Placeholder()))
            params.append(value)
        query = sql.SQL("DELETE FROM {} WHERE {}").format(
            sql.Identifier(table),
            sql.SQL(" AND ").join(where_parts),
        )
        await cur.execute(query, params)
        return {"rowcount": cur.rowcount}
