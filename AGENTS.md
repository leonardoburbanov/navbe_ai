# Navbe

Local-first workflow orchestration engine operated by AI agents over MCP.

Agents sync data (e.g. Langfuse traces → DuckDB/CSV), schedule recurring flows, and query results — without a cloud control plane in the critical path.

This file is always-on guidance for coding agents working in this repo.

For deeper project context (architecture, operations, wiki scope), start at
[docs/agents/quickstart.md](docs/agents/quickstart.md). Keep this file for
must-follow rules only; put narrative docs in `docs/agents/`.

---

## Stack

| Layer | Choice |
| --- | --- |
| Runtime | Python 3.12+ |
| Packages | `uv` only (never pip/poetry) |
| HTTP API | FastAPI |
| Agent surface | FastMCP |
| Orchestration | LangGraph |
| App state | SQLite via `aiosqlite` |
| Analytics destinations | DuckDB (and CSV) |
| Tests | `pytest` + `pytest-asyncio` |

---

## Layout

```
src/navbe/
  core/             # config, database engine/session, base exceptions
  domains/          # subpackages added per EPIC (no logic in EPIC 0)
    steps/          # atomic units of work
    connectors/     # external sources (e.g. Langfuse)
    flows/          # scheduled/composed workflows
    execution/      # run lifecycle, modes, history
    secrets/        # credential storage/resolution
    catalog/        # discovery of connectors, destinations, flows
  api/              # FastAPI routes (thin; call services)
  mcp_app/          # FastMCP tools (thin; call services)
  dependencies.py
  main.py
pyproject.toml
tests/
```

Keep MCP tools and HTTP routes thin. Business logic lives in domain `service.py` files.
Layering is enforced by `.importlinter` (`uv run lint-imports`).

---

## Domain pattern

Every domain package under `src/navbe/domains/<name>/` follows this split:

| File | Role |
| --- | --- |
| `models.py` | Pydantic models (request/response/persistence shapes) |
| `interfaces.py` | `typing.Protocol` boundaries (ports) |
| `service.py` | Use-cases; depends on Protocols, not concrete infra |

Rules:

- Services take Protocols in `__init__` (or function args) — no hard imports of SQLite/DuckDB/HTTP clients inside domain services.
- Concrete adapters live outside the domain (e.g. `db/`, `destinations/`, connector clients).
- Prefer extending an existing domain over inventing a new top-level package.
- Do not cross-import another domain's `service.py` for convenience; call through a Protocol or move shared logic up.

---

## Commands

```bash
# sync / install
uv sync

# run API (when scaffolded)
uv run uvicorn navbe.api.app:app --reload

# run MCP server (when scaffolded)
uv run python -m navbe.mcp

# tests
uv run pytest
uv run pytest path/to/test_file.py -q

# lint / typecheck / architecture
uv run ruff check .
uv run ty check src/
uv run lint-imports
```

Add dependencies with `uv add <pkg>`; dev deps with `uv add --dev <pkg>`.

---

## Code style

- Type hints on all public functions and methods; module-level constants typed when non-obvious.
- Docstrings on public functions/classes (one-liner is fine; expand only when behavior is non-obvious).
- `async` at I/O boundaries (`aiosqlite`, HTTP, MCP handlers). Do not wrap sync CPU work in fake async.
- Prefer stdlib + already-installed deps. New dependency only when it clearly replaces non-trivial code.
- No speculative abstractions, extra config layers, or “flexibility” nobody asked for.
- Mark intentional shortcuts with `ponytail: <ceiling> — upgrade: <path>`.
- Do not create tests, examples, or README/markdown docs unless explicitly asked.

### Python shape

```python
# ✅ domain service depends on a Protocol
class ConnectorStore(Protocol):
    async def get(self, connector_id: str) -> Connector | None: ...

class ConnectorService:
    def __init__(self, store: ConnectorStore) -> None:
        self._store = store

    async def recall(self, connector_id: str) -> Connector:
        """Return a connector or raise if missing."""
        ...
```

```python
# ❌ service imports concrete SQLite repo / DuckDB path directly
from navbe.db.sqlite_connectors import SqliteConnectorRepo
```

---

## Architecture boundaries

**Always do**

- Put Pydantic shapes in `models.py`, ports in `interfaces.py`, use-cases in `service.py`.
- Persist app/control-plane state in SQLite; use DuckDB only as an analytics destination (or query surface over synced data).
- Keep secrets out of logs, MCP tool responses, traces, and git. Resolve via the `secrets` domain.
- Make MCP tool handlers validate inputs, call a domain service, return structured results.
- For workflow runs: default `mode="append"` (upsert by `id`). Use `mode="overwrite"` only when replacing all rows is intentional.

**Ask first**

- New domain packages beyond the six listed above.
- New destination types beyond DuckDB / CSV.
- Schema migrations that drop or rename persisted columns.
- Changing MCP tool names or argument shapes (agents depend on stability).

**Never do**

- Commit `.env`, credential files, or live secret values.
- Hit production external APIs from unit tests (mock at the Protocol boundary).
- Duplicate business logic in both FastAPI routes and MCP tools — share the service.
- Store Langfuse (or other) secret keys in flow definitions or destination configs in plaintext outside the secrets domain.
- Treat DuckDB destination columns as typed timestamps/numbers without casting (see below).

---

## DuckDB destination caveats

When writing or querying SQL against a Navbe traces/observations destination:

- Columns are stored as `VARCHAR` — `CAST(column AS TIMESTAMP)` (or other type) before date/numeric functions.
- `run_workflow` / scheduled runs default to `mode="append"`: upsert by `id`, no duplicates. `overwrite` replaces all rows.
- “Deleted” counts in run output are only meaningful for `overwrite`. In append mode, a missing id means it was not in the latest fetched page — not that the source deleted it.
- Through `query_destination` / `query_workflow_destination`, the table name is always `traces` or `observations`, regardless of file/table config on the destination.

---

## MCP product surface (target)

Agents operate Navbe through tools roughly in this order of use:

1. Connectors — register/query external sources.
2. Destinations — DuckDB or CSV sinks.
3. Flows/workflows — schedule syncs (`when`: `+30s` / `+1h` / cron).
4. Execution — `run_workflow`, recall status, list runs.
5. Query — `query_destination` / `query_workflow_destination` (paginated SELECT).

Prefer querying a synced DuckDB destination over calling the live source for analytics.

---

## Security

- Secrets domain owns storage and resolution; never echo secret values in API/MCP responses.
- Local data dirs (SQLite, DuckDB files, exports) stay on disk; do not assume network share semantics.
- Read-only SQL for destination query tools — no DDL/DML via query endpoints.

---

## Testing (when asked to add tests)

- `pytest` + `pytest-asyncio`; mark async tests with `@pytest.mark.asyncio`.
- Test domain services with fake Protocol implementations — not real DuckDB/network.
- One focused test file per behavior change is enough; no fixture megafw.

---

## Git

- Commit only when the user asks.
- Do not push unless asked.
- Keep commits small and focused on why, not a file laundry list.

---

## Documentation

- Agent wiki entry: [docs/agents/quickstart.md](docs/agents/quickstart.md)
- Wiki scope (do not rewrite unless asked): [docs/agents/INSTRUCTIONS.md](docs/agents/INSTRUCTIONS.md)
- When an EPIC merges behavior, update the matching `docs/agents/` page in the same change set when docs would otherwise be wrong.
- Do not add OpenWiki or other doc-generator tooling unless explicitly requested.
