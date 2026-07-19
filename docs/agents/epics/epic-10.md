# EPIC 10 — MCP Discovery Parity

**Status:** done  
**Goal:** Expose everything agents need to *discover and inspect* Navbe state over MCP — catalogs, saved flows, and (where already in the domain) flow updates — using Claude-safe underscored tool names.  
**Non-goal:** Destinations / Langfuse export tools; secrets enumeration; delete flows; new domain packages; changing existing tool argument shapes beyond additive discovery tools.

## Why

EPIC 7 shipped authoring + run control (`flow_create` / `flow_run` / …) and catalog **resources**. Agents (and Claude Desktop) still cannot:

- List or recall already-created flows without knowing `flow_id`
- Reliably read catalogs when the client surfaces tools more than resources
- Update a persisted flow (repo already supports `update`; service/MCP/REST do not)

This epic closes that discovery gap so the MCP surface matches what the domains + REST already allow (and wires the missing `FlowService.update`).

## In scope

| Surface | What |
| --- | --- |
| Resources (keep) | `navbe://catalog/steps`, `navbe://catalog/connectors`, `navbe://catalog/full` |
| Resources (add) | `navbe://flows` (metadata index), `navbe://flows/{flow_id}` (full FlowSpec) |
| Tools (keep) | `flow_create`, `flow_validate`, `flow_run`, `flow_status`, `flow_resume`, `flow_list_runs` |
| Tools (add) | `flow_list`, `flow_get`, `flow_update` |
| Tools (add, catalog mirrors) | `catalog_steps`, `catalog_connectors`, `catalog_full` |
| Domain | `FlowService.update` → repository `update` (validate then archive+overwrite) |
| REST parity | `PUT /api/v1/flows/{flow_id}` (or `PUT ""` with id in body — prefer path id matching `GET`) |

## Out of scope

- `flow_delete` / hard delete of run history
- Listing secret keys or resolved secret values
- Destinations, DuckDB query tools, Langfuse connectors
- Renaming existing tools again (names stay underscored: `^[a-zA-Z0-9_-]{1,64}$`)
- Changing catalog JSON shape from EPIC 6/7

## Target MCP surface (after)

### Resources

| URI | Body |
| --- | --- |
| `navbe://catalog/steps` | step_type → config_schema (incl. synthetic `approval`) |
| `navbe://catalog/connectors` | connector_type → config_schema + actions |
| `navbe://catalog/full` | `{ "steps": …, "connectors": … }` |
| `navbe://flows` | list of `FlowMetadata` (`flow_id`, `name`, `version`, `path`, timestamps) |
| `navbe://flows/{flow_id}` | full FlowSpec JSON (`by_alias`) |

### Tools

| Tool | Role |
| --- | --- |
| `catalog_steps` | Same payload as `navbe://catalog/steps` |
| `catalog_connectors` | Same payload as `navbe://catalog/connectors` |
| `catalog_full` | Same payload as `navbe://catalog/full` |
| `flow_list` | `{ "flows": [FlowMetadata, …] }` |
| `flow_get` | FlowSpec for `flow_id` |
| `flow_create` | create (existing) |
| `flow_validate` | validate only (existing) |
| `flow_update` | validate + archive previous version + overwrite |
| `flow_run` / `flow_status` / `flow_resume` / `flow_list_runs` | execution (existing) |

Catalog tools are thin mirrors of resources so clients that only advertise tools (or fail resource reads) still discover step/connector types.

## Tasks

### T1 — `FlowService.update`

- Add `async def update(self, flow_spec_dict: dict) -> FlowMetadata` mirroring `create` (Pydantic validate → graph validate → `repository.update`).
- Reject unknown `flow_id` via existing `NotFoundError` from repository.
- Unit tests in `tests/unit/domains/flows/` (happy path + missing id + invalid graph).

**Verify:** `uv run pytest tests/unit/domains/flows -q`

### T2 — MCP tools: discovery + update

- Extend `src/navbe/mcp_app/tools.py`:
  - `flow_list`, `flow_get`, `flow_update`
  - `catalog_steps`, `catalog_connectors`, `catalog_full` (inject `CatalogService` into `register_tools`)
- Keep thin adapters + `@mcp_tool_error_handler`.
- Update `create_mcp_server` / `register_tools` signatures to pass `catalog_service`.
- Unit tests under `tests/unit/mcp_app/` for each new tool; extend `test_server.py` expected name set.

**Verify:** `uv run pytest tests/unit/mcp_app -q`

### T3 — MCP resources: saved flows

- Extend `src/navbe/mcp_app/resources.py`:
  - `navbe://flows` → `flow_service.list()`
  - `navbe://flows/{flow_id}` → `flow_service.get(flow_id)` (template resource)
- Inject `FlowService` into `register_resources` (catalog registration stays).
- Unit tests for list + get + missing id error behavior.

**Verify:** `uv run pytest tests/unit/mcp_app -q`

### T4 — REST parity for update

- Add `PUT /api/v1/flows/{flow_id}` thin route calling `FlowService.update` (body = FlowSpec dict; path `flow_id` must match body `flow_id` or body omits id and path wins — pick one rule and document it).
- Unit/API tests alongside existing `tests/unit/api/test_flows_routes.py`.

**Verify:** `uv run pytest tests/unit/api/test_flows_routes.py -q`

### T5 — Integration + docs

- Extend `tests/integration/test_mcp_server_standalone.py` and/or stdio entrypoint test: list tools includes new names; `flow_list` sees a created flow; read `navbe://flows`.
- Update [architecture.md](../architecture.md) MCP section, [connect_agents.md](../../connect_agents.md) expected agent behavior (discover catalogs + `flow_list` before authoring), [quickstart.md](../quickstart.md) epic index, this file’s DoD checkboxes.
- Note in [AGENTS.md](../../../AGENTS.md) MCP product surface only if the “target tool order” bullet list needs a discovery step (prefer minimal AGENTS.md churn).

**Verify:**

```bash
uv run pytest tests/integration/test_mcp_server_standalone.py tests/integration/test_mcp_stdio_entrypoint.py -q
uv run ruff check .
uv run ty check src/navbe/mcp_app src/navbe/domains/flows src/navbe/api
uv run lint-imports
```

## Definition of Done

- [x] `flow_list` / `flow_get` / `flow_update` registered and unit-tested
- [x] `catalog_steps` / `catalog_connectors` / `catalog_full` registered and unit-tested
- [x] Resources `navbe://flows` and `navbe://flows/{flow_id}` registered and unit-tested
- [x] Existing catalog resources unchanged in shape
- [x] `FlowService.update` + REST `PUT` green
- [x] Integration/stdio tests list new tool names and can list a created flow
- [x] All tool names match `^[a-zA-Z0-9_-]{1,64}$` (no dots)
- [x] `uv run pytest tests/unit/mcp_app tests/unit/domains/flows tests/unit/api/test_flows_routes.py -q` green
- [x] `uv run pytest tests/integration/test_mcp_server_standalone.py tests/integration/test_mcp_stdio_entrypoint.py -q` green
- [x] `uv run ruff check .` / `uv run ty check src/` / `uv run lint-imports` green
- [x] Agent docs updated (`architecture`, `connect_agents`, epic status)

## Suggested agent loop (after)

1. `catalog_steps` + `catalog_connectors` (or read `navbe://catalog/*`)
2. `flow_list` — see what already exists
3. `flow_get` — inspect a flow before edit/run
4. `flow_validate` → `flow_create` or `flow_update`
5. `flow_run` → poll `flow_status` → `flow_resume` if paused
6. `flow_list_runs` for history

## Notes

- Catalog tool responses must equal resource payloads (single source: `CatalogService`).
- `flow_update` must not leak secrets; FlowSpec may contain `{"$secret": "KEY"}` refs — return specs as stored, never resolved values.
- Template resource 404s should surface as MCP resource errors consistent with FastMCP, not raw tracebacks.
- Ponytail: no new abstractions — thin MCP/REST adapters over existing services only.
