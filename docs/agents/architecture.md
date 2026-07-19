# Architecture (EPIC 0)

Code is the source of truth. This page matches what exists after EPIC 0 bootstrap.

## Layers

Enforced by [`.importlinter`](../../.importlinter):

```
navbe.mcp_app | navbe.api   # outer: thin handlers
        ↓
navbe.domains               # use-cases (steps…catalog)
        ↓
navbe.core                  # config, DB helpers, exceptions
```

Domains must not import `mcp_app` or `api`. Outer layers may depend on domains and core.

## Core

| Module | Responsibility |
| --- | --- |
| `navbe.core.config` | `Settings` + cached `get_settings()` (`NAVBE_` prefix) |
| `navbe.core.database` | `create_engine` / `get_session` — no tables yet |
| `navbe.core.exceptions` | `NavbeError` and subclasses; domains must not raise bare `Exception`/`ValueError` |

## Domain pattern

Each `src/navbe/domains/<name>/`:

- `models.py` — Pydantic shapes
- `interfaces.py` — `Protocol` ports
- `service.py` — use-cases depending on Protocols only

Implemented domain:

- `steps` — standalone step contracts, registry, service, and built-in implementations.
- `connectors` — standalone connector contracts, registry, service, and HTTP implementation.
- `secrets` — env-backed secret refs consumed by connector resolution.
- `flows` — FlowSpec models, graph validation, filesystem + SQLite index.
- `execution` — FlowSpec → LangGraph compile/run, checkpoints, HITL, run transcripts.
- `catalog` — read-only JSON Schema aggregation of steps + connectors for agents.

Outer surface (not a domain):

- `mcp_app` — FastMCP tools (`flow.*`) and catalog resources; thin adapters only.

## Steps domain

`steps` is intentionally independent from Flow / execution / MCP. Tests construct `StepContext` directly and call `await step.run(ctx)`.

Built-ins registered in `StepRegistry`:

- `http_request`
- `set_var`
- `transform`
- `llm_call`
- `router`

## Connectors domain

`connectors` wraps external systems and is consumed later by steps through
`ctx.flow_vars["connectors"][name]`. Tests instantiate connectors directly.

Built-ins registered in `ConnectorRegistry`:

- `http`

## Secrets domain

v0.1 resolves `{"$secret": "KEY"}` leaves from process env / `.env`.
`ConnectorService` injects `SecretsService(EnvSecretsProvider())` when wired.
Missing keys raise `NotFoundError` with the key name and a hint — never a secret value.

## Flows domain

`FlowSpec` is the agent-authored JSON document (nodes, edges, connectors).
`FlowService.create` validates structure + graph, then persists via
`FileSystemFlowRepository` (`flow.json` + SQLite `flows_index`).
`update()` archives prior content as `flow.v{n}.json`. Cycles are allowed.

## Execution domain

`RunService` loads a `FlowSpec`, compiles it via `compile_flow`, and runs it
through `LangGraphEngine` (`AsyncSqliteSaver` checkpoints). Per-run artifacts
live under `{runs_dir}/{flow_id}/{run_id}/` (`state.json`, `trace.jsonl`,
`transcript.md`). Reserved step type `approval` pauses via LangGraph
`interrupt`; `resume` continues with `Command(resume=decision)`.

Conditional edges match `node_outputs[source]["route"]` to `edge.condition`
(same convention as `RouterStep`).

## Catalog domain

`CatalogService` exposes `get_steps_catalog` / `get_connectors_catalog` /
`get_full_catalog` for agents before they author a FlowSpec. Schemas come from
registry `config_schema.model_json_schema()`. Reserved step type `approval`
is synthesized into the steps catalog (and accepted by `validate_graph`) even
though it is not registered in `StepRegistry`.

## MCP app

`create_mcp_server(flow_service, run_service, catalog_service)` registers tools
and resources. Domain errors become FastMCP `ToolError` with a JSON payload
(`error` / `code` / `message` / `details`). `flow_run` returns immediately;
`RunService.start` schedules execution with `asyncio.create_task`.

Discovery (EPIC 10): tools `catalog_*`, `flow_list`, `flow_get`, `flow_update`
plus resources `navbe://catalog/*`, `navbe://flows`, `navbe://flows/{flow_id}`.
Tool names are underscored (`flow_create`, not `flow.create`) for Claude-safe
`^[a-zA-Z0-9_-]{1,64}$` names.

## Wiring

`dependencies.py` is the only production constructor for concrete services
(lru_cache singletons; `clear_dependency_caches()` for tests). `main.create_app()`
mounts REST under `/api/v1/*` and FastMCP at `/mcp` via `http_app(path="/")`
with the MCP lifespan (and SQLite `flows_index` create_all on startup).

Stdio clients (Claude Desktop, Cursor) use `uv run navbe-mcp`
(`navbe.mcp_stdio:main`) — same services, `transport="stdio"`. See
[../connect_agents.md](../connect_agents.md).

## Persistence split (target)

- **SQLite** (`aiosqlite` + SQLAlchemy async) — app/control-plane state
- **DuckDB / CSV** — analytics destinations (not in tree yet)

See DuckDB caveats in [AGENTS.md](../../AGENTS.md).
