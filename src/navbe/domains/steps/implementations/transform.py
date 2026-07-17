"""DuckDB transform step implementation."""

from typing import Any

import duckdb

from navbe.core.exceptions import ExecutionError
from navbe.domains.steps.interfaces import StepContext
from navbe.domains.steps.models import StepConfig
from navbe.domains.steps.registry import StepRegistry


def _quote_identifier(name: str) -> str:
    """Quote a DuckDB identifier."""
    return '"' + name.replace('"', '""') + '"'


def _duckdb_type(values: list[Any]) -> str:
    """Infer a boring DuckDB column type from Python values."""
    concrete = [value for value in values if value is not None]
    if not concrete:
        return "VARCHAR"
    if all(isinstance(value, bool) for value in concrete):
        return "BOOLEAN"
    if all(isinstance(value, int) and not isinstance(value, bool) for value in concrete):
        return "BIGINT"
    if all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in concrete):
        return "DOUBLE"
    return "VARCHAR"


def _register_input(con: duckdb.DuckDBPyConnection, input_data: Any) -> None:
    """Register ctx.input_data as a table named ``input``."""
    if isinstance(input_data, list) and all(isinstance(row, dict) for row in input_data):
        columns = sorted({key for row in input_data for key in row})
        column_defs = ", ".join(
            f"{_quote_identifier(column)} {_duckdb_type([row.get(column) for row in input_data])}"
            for column in columns
        )
        con.execute(f"CREATE TABLE input ({column_defs})")
        placeholders = ", ".join("?" for _ in columns)
        quoted_columns = ", ".join(_quote_identifier(column) for column in columns)
        for row in input_data:
            con.execute(
                f"INSERT INTO input ({quoted_columns}) VALUES ({placeholders})",
                [row.get(column) for column in columns],
            )
        return

    con.register("input", input_data)


class TransformConfig(StepConfig):
    """Configuration for SQL transforms over a view named ``input``."""

    query: str


@StepRegistry.register("transform")
class TransformStep:
    """Run SQL against ``ctx.input_data`` registered as ``input``."""

    config_schema = TransformConfig

    def __init__(self, config: dict[str, Any]) -> None:
        """Validate and store transform config."""
        self.config = TransformConfig.model_validate(config)

    async def run(self, ctx: StepContext) -> Any:
        """Execute SQL against input data and return rows as dictionaries."""
        if ctx.input_data == []:
            return []

        con = duckdb.connect(":memory:")
        try:
            _register_input(con, ctx.input_data)
            result = con.execute(self.config.query)
            columns = [description[0] for description in result.description]
            return [dict(zip(columns, row, strict=True)) for row in result.fetchall()]
        except duckdb.Error as exc:
            raise ExecutionError(
                "Transform step failed",
                details={"query": self.config.query},
            ) from exc
        finally:
            con.close()
