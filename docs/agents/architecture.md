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
- `connectors` — standalone connector contracts, registry, service, HTTP + Resend.
- `secrets` — credentials-JSON secret refs consumed by connector resolution.
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

- `http` — generic HTTP; API keys via `headers` + `{"$secret": "KEY"}`
- `resend` — api.resend.com; `api_key: {"$secret": "RESEND_API_KEY"}`

## Secrets domain

`SecretsService` resolves `{"$secret": "KEY"}` leaves in connector configs from
the local JSON credentials file only (`NAVBE_CREDENTIALS_PATH`, default
`./navbe_credentials.json`). Env / `.env` are never consulted for `$secret`
resolution. Agents manage the store via MCP `secret_set` / `secret_list` /
`secret_hint` / `secret_delete` / `secret_has` (or REST `/api/v1/secrets`) —
full values are never returned. Entries may carry an optional `app` slug;
list/hint return a masked suffix (`****` + last 4).
Missing keys raise `NotFoundError` with the key name and a hint — never a secret value.

## Sync domain

`SyncService` mirrors **versionable workspace metadata** to GitHub under a working
clone (`navbe_sync_repo/`). Registered assets: `FlowsAsset`
(`flows/<flow_id>/flow.json`) and `SchedulesAsset`
(`schedules/<schedule_id>/schedule.json`). Reserved layout for later assets:
`connectors/`, `destinations/`. Never syncs runs, credentials,
OAuth tokens, archives, or Python step/connector source.

Auth: GitHub App Device Flow via `GitHubAuthService` → managed
`navbe_github_oauth.json` (not `secret_set`). Access tokens refresh via
`refresh_token` (no client secret). Token is injected in-process for
`git` (`http.extraHeader`) and never written to disk git config.

MCP: `auth_github_*`, `sync_connect` / `sync_configure` / `sync_init` /
`sync_status` / `sync_branch_create` / `sync_checkout` / `sync_push` /
`sync_pull`. REST: `/api/v1/sync/*`.

Default Client ID is the public Navbe AI GitHub App
(`NAVBE_GITHUB_APP_CLIENT_ID`). Enable Device Flow on the app, grant
Contents + Administration, and install on the account that owns workspace repos.
Legacy `NAVBE_GITHUB_OAUTH_CLIENT_ID` is still read as a fallback.

## Flows domain

`FlowSpec` is the agent-authored JSON document (nodes, edges, connectors).
`FlowService.create` validates structure + graph, then persists via
`FileSystemFlowRepository` (`flow.json` + SQLite `flows_index`).
`update()` archives prior content as `flow.v{n}.json`. Cycles are allowed.

## Schedules domain

`ScheduleSpec` lives at `schedules/<schedule_id>/schedule.json` (not on
`FlowSpec`). `when` is relative (`+30s` / `+1h` / `+1d`) or a 5-field cron.
`ScheduleService` + `FileSystemScheduleRepository` (SQLite `schedules_index`)
own CRUD / enable / disable. Optional `notify` email via Resend
(`api_key` as `{"$secret": "..."}`, `failure_threshold` default 1, latched
until a successful run).

`SchedulerLoop` ticks every ~10s **only inside `navbe serve`** (FastAPI
lifespan). Due schedules call `RunService.start(trigger="schedule")`. If the
flow is busy, the fire is skipped and `next_run_at` advances.

## Execution domain

`RunService` loads a `FlowSpec`, compiles it via `compile_flow`, and runs it
through `LangGraphEngine` (`AsyncSqliteSaver` checkpoints). Per-run artifacts
live under `{runs_dir}/{flow_id}/{run_id}/` (`state.json`, `trace.jsonl`,
`transcript.md`). Node wrappers write `NodeTrace` lines; MCP `flow_run`
defaults to ``wait=true`` and returns `steps` + a Mermaid `diagram` when the
run settles (``wait=false`` for fire-and-forget). `flow_status` /
`flow_resume` expose the same shape. CLI `navbe runs status` prints a steps
table (`--diagram` for Mermaid). Reserved step type `approval`
pauses via LangGraph `interrupt`; `resume` continues with `Command(resume=decision)`.

Single-flight: only one active run (`pending` / `running` / `paused`) per
flow — further starts raise (or skip when scheduled). `flow_cancel` /
`RunService.cancel` cancels the asyncio task and persists `CANCELLED`.
Runs record `trigger` (`manual` | `schedule`) and optional `schedule_id`.

Conditional edges match `node_outputs[source]["route"]` to `edge.condition`
(same convention as `RouterStep`).

## Catalog domain

`CatalogService` exposes `get_steps_catalog` / `get_connectors_catalog` /
`get_full_catalog` for agents before they author a FlowSpec. Schemas come from
registry `config_schema.model_json_schema()`. Reserved step type `approval`
is synthesized into the steps catalog (and accepted by `validate_graph`) even
though it is not registered in `StepRegistry`.

## MCP app

`create_mcp_server(..., schedule_service=...)`
registers tools and resources. Domain errors become FastMCP `ToolError` with a JSON payload
(`error` / `code` / `message` / `details`). `flow_run` returns immediately when
``wait=false``; `RunService.start` schedules execution with `asyncio.create_task`.
Schedule tools (`schedule_*`) CRUD configs; the tick loop that fires them runs
only under `navbe serve`.

Discovery (EPIC 10): tools `catalog_*`, `flow_list`, `flow_get`, `flow_update`
plus resources `navbe://catalog/*`, `navbe://flows`, `navbe://flows/{flow_id}`.
Credentials (EPIC 11): `secret_*`. GitHub flows sync (EPIC 12): `sync_*`.
Tool names are underscored (`flow_create`, not `flow.create`) for Claude-safe
`^[a-zA-Z0-9_-]{1,64}$` names.

Claude Desktop playbook: tool `navbe_howto`, resource `navbe://guide`, and
prompt `navbe_howto` share one text (`mcp_app/guide.py`). Prefer the **tool**
on Claude Desktop (resources/prompts are often not surfaced to the model).

Claude packaging: [`claude-plugin/`](../../claude-plugin/) bundles local MCP
(`.mcp.json`) + skill `navbe-flows` for Customize → Plugins / Skills. See
[../connect_agents.md](../connect_agents.md).

## Wiring

`dependencies.py` is the only production constructor for concrete services
(lru_cache singletons; `clear_dependency_caches()` for tests). `main.create_app()`
mounts REST under `/api/v1/*` and FastMCP at `/mcp` via `http_app(path="/")`
with the MCP lifespan (and SQLite `flows_index` create_all on startup).

Clients (Claude Desktop, Cursor) connect to the same process over HTTP MCP at
`/mcp` (`http://127.0.0.1:8000/mcp` by default). Start with `navbe bootstrap`
or `navbe serve` / `navbe serve --detach`. See [../install.md](../install.md)
and [../connect_agents.md](../connect_agents.md).

## Human CLI

`navbe` is the ops console for humans (Typer + Rich). It calls the same
domain services as MCP/REST — no HTTP round-trip. Package: `src/navbe/cli/`.

| Command group | Role |
| --- | --- |
| `navbe bootstrap` | Data dirs + detach serve + write client MCP URL configs |
| `navbe secret` | Local credentials (masked hints; values never printed) |
| `navbe sync` | GitHub `flows/<id>/flow.json` mirror |
| `navbe flows` / `navbe runs` / `navbe steps` | Browse flows, runs, step catalog |
| `navbe serve` / `status` / `stop` | Daemon (API + MCP + schedules) |
| `navbe setup` | Interactive onboarding (data dirs, secrets, sync, MCP write) |
| `navbe mcp show` / `configure` | Pasteable URL snippet / write Cursor & Claude Desktop configs |
| `navbe info` | Paths, credential/sync readiness, version |
| `navbe login --status` | Recommended API keys present (never values) |

Distribution (install scripts, `uv tool install`, GitHub Releases / PyPI): [../install.md](../install.md).

## Persistence split (target)

- **SQLite** (`aiosqlite` + SQLAlchemy async) — app/control-plane state
- **Analytics** — external / out-of-process (not embedded in Navbe; independent DuckDB later)

See coding rules in [AGENTS.md](../../AGENTS.md).
