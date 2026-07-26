# Navbe

Local-first workflow orchestration engine operated by AI agents over MCP.

Agents sync data (e.g. Langfuse traces → external analytics), schedule recurring flows, and query results — without a cloud control plane in the critical path.

This file is always-on guidance for coding agents working in this repo.

For deeper project context (architecture, operations, wiki scope), start at
[docs/agents/quickstart.md](docs/agents/quickstart.md). End-user install and
CLI distribution: [docs/install.md](docs/install.md). Keep this file for
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
| In-step SQL | DuckDB in-memory (`transform` step only) |
| Analytics destinations | External / out-of-process (not embedded in Navbe) |
| Tests | `pytest` + `pytest-asyncio` |

---

## Layout

```
src/navbe/
  core/             # config, database engine/session, base exceptions
  domains/          # subpackages added per EPIC (no logic in EPIC 0)
    steps/          # atomic units of work
    connectors/     # external sources (e.g. Langfuse)
    flows/          # composed workflows
    schedules/      # time-based triggers + failure notify
    execution/      # run lifecycle, modes, history
    secrets/        # credential storage/resolution
    catalog/        # discovery of connectors, flows
    sync/           # GitHub workspace sync (flows + schedules; OAuth)
  api/              # FastAPI routes (thin; call services)
  mcp_app/          # FastMCP tools (thin; call services)
  cli/              # Human ops console (Click + Rich)
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

- Services take Protocols in `__init__` (or function args) — no hard imports of SQLite/HTTP clients inside domain services.
- Concrete adapters live outside the domain (e.g. `db/`, connector clients).
- Prefer extending an existing domain over inventing a new top-level package.
- Do not cross-import another domain's `service.py` for convenience; call through a Protocol or move shared logic up.

---

## Commands

```bash
# sync / install (contributors)
uv sync

# end-user install (no clone) — see docs/connect_agents.md
# curl -fsSL …/scripts/install.sh | bash
# irm …/scripts/install.ps1 | iex

# human CLI + one daemon (MCP + schedules + API)
uv run navbe bootstrap      # dirs + serve --detach + wire agents
uv run navbe status
uv run navbe --help
uv run navbe serve          # foreground; or --detach

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
# ❌ service imports concrete SQLite repo directly
from navbe.db.sqlite_connectors import SqliteConnectorRepo
```

---

## Architecture boundaries

**Always do**

- Put Pydantic shapes in `models.py`, ports in `interfaces.py`, use-cases in `service.py`.
- Persist app/control-plane state in SQLite. Do not embed an analytics DuckDB (file or server) inside Navbe — analytics lives in an independent instance later.
- Keep secrets out of logs, MCP tool responses, traces, and git. Resolve via the `secrets` domain.
- Make MCP tool handlers validate inputs, call a domain service, return structured results.
- For workflow runs: default `mode="append"` (upsert by `id`). Use `mode="overwrite"` only when replacing all rows is intentional.

**Ask first**

- New domain packages beyond those listed in Layout (including `sync`).
- Wiring Navbe to an external analytics store (independent DuckDB or otherwise).
- Schema migrations that drop or rename persisted columns.
- Changing MCP tool names or argument shapes (agents depend on stability).

**Never do**

- Commit `.env`, credential files, or live secret values.
- Hit production external APIs from unit tests (mock at the Protocol boundary).
- Duplicate business logic in both FastAPI routes and MCP tools — share the service.
- Store Langfuse (or other) secret keys in flow definitions or destination configs in plaintext outside the secrets domain.
- Add an embedded DuckDB analytics sink (local `.duckdb` file owned by Navbe as a destination).

---

## MCP product surface (target)

Agents operate Navbe through tools roughly in this order of use:

1. Connectors — register/query external sources.
2. Flows/workflows — compose graphs; schedule via `schedule_*` (`when`: `+30s` / `+1h` / cron).
3. Execution — `flow_run`, `flow_status`, `flow_cancel`, list runs.

Schedules fire only while `navbe serve` is up (same process as HTTP MCP at
`/mcp`). Analytics querying against an independent DuckDB (or other store) is
out of band from this daemon for now.

---

## Security

- Secrets domain owns storage and resolution; never echo secret values in API/MCP responses.
- Prefer `secret_set` / local `navbe_credentials.json` over committing keys; file is gitignored.
  `$secret` resolves from that file only — never from env / `.env`.
- Local data dirs (SQLite, credentials JSON) stay on disk; do not assume network share semantics.

---

## Testing (when asked to add tests)

- `pytest` + `pytest-asyncio`; mark async tests with `@pytest.mark.asyncio`.
- Test domain services with fake Protocol implementations — not real network.
- One focused test file per behavior change is enough; no fixture megafw.

---

## Git

- Commit only when the user asks.
- Do not push unless asked.
- Keep commits small and focused on why, not a file laundry list.

---

## Documentation

- Agent wiki entry: [docs/agents/quickstart.md](docs/agents/quickstart.md)
- Install & distribution (CLI/MCP): [docs/install.md](docs/install.md)
- Connect Cursor / Claude: [docs/connect_agents.md](docs/connect_agents.md)
- Delivery / EPICs: [docs/agents/delivery.md](docs/agents/delivery.md)
- Wiki scope (do not rewrite unless asked): [docs/agents/INSTRUCTIONS.md](docs/agents/INSTRUCTIONS.md)
- When an EPIC merges behavior, update the matching `docs/agents/` page in the same change set when docs would otherwise be wrong.
- Do not add OpenWiki or other doc-generator tooling unless explicitly requested.
