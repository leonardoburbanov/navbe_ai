# EPIC 19 — Built-in Connectors (CRUD)

**Status:** planned  
**Goal:** Register first-class ConnectorRegistry types for Resend (`send_email`), MongoDB, PostgreSQL, Langfuse, external DuckDB, ClickHouse, Supabase, Google Calendar, and Pinecone — each with basic configurable CRUD (or domain-equivalent) actions — so agents discover them via `catalog_connectors` and invoke them from FlowSpecs.  
**Non-goal:** Destinations domain; Langfuse export MCP tools; typed per-connector steps; embedded Navbe-owned DuckDB analytics; changing MCP tool names; schedule-notifier refactor; Google OAuth begin/complete MCP; Supabase Auth/Storage/Realtime; Pinecone control-plane index admin.

## Depends on

- EPIC 2 — connectors domain + `ConnectorRegistry`
- EPIC 3 / 11 / 16 — `$secret` + credentials JSON
- EPIC 6 — catalog over connector schemas/actions
- EPIC 5 — execution resolves FlowSpec connectors into `flow_vars`

## Locked decisions

| Decision | Choice |
| --- | --- |
| Product surface | ConnectorRegistry only — auto-appears in `catalog_connectors`; no destinations domain; no new MCP tools |
| DuckDB | External user-owned file path (`db_path`); Navbe does not own a default analytics DB |
| Resend | Exclusive connector with first-class `send_email` — not generic HTTP verbs. Keep `http` for REST |
| CRUD | Each data connector exposes create/read/update/delete (or clear domain equivalents) via `execute(action, payload)` |
| Invocation | Existing `http_request` step: `method` = action name, `body_template` = action payload (`path` unused for non-HTTP). No new per-type steps |
| Google Calendar auth | Stored OAuth refresh token + client_id + client_secret (no browser OAuth / Device Flow in this epic) |

## In scope

| Type | Config (secrets via `$secret`) | Actions |
| --- | --- | --- |
| `resend` | `api_key` | `send_email` only (`from`, `to`, `subject`, `html` and/or `text`; optional `cc` / `bcc` / `reply_to`) — **breaking** vs today’s get/post/put/delete |
| `mongodb` | `uri` (+ optional `database`) | `create`, `read`, `update`, `delete` on `collection` + document / filter / update payload |
| `postgresql` | `dsn` **or** host/port/user/password/dbname | `create` (INSERT), `read` (SELECT), `update`, `delete` — parameterized; no multi-statement scripts |
| `langfuse` | `host`, `public_key`, `secret_key` | CRUD-shaped REST wrappers via `httpx` (no Langfuse SDK): pin to concrete Public API endpoints for create/read/update/delete where supported (traces / observations / scores as documented in T4) |
| `duckdb` | `db_path` (file) | `create` / `read` / `update` / `delete` with payload fields `sql` / `table` / `rows` / `where` as needed; sync DuckDB API via `asyncio.to_thread`; never invent a default path under Navbe data dirs |
| `clickhouse` | host/port/user/password/database (+ TLS flag) | `create` / `read` / `update` / `delete` — parameterized queries |
| `supabase` | `url`, `service_role_key` | `create` / `read` / `update` / `delete` on PostgREST `table` + `filters` / `row` / `rows` / `prefer` — **`httpx` only** |
| `google_calendar` | `client_id`, `client_secret`, `refresh_token` | `create` / `read` / `update` / `delete` on Calendar events (`calendar_id` default `primary`; event body / `event_id` / list query) — **`httpx` only**; refresh access token at Google OAuth token endpoint, then Calendar API v3 |
| `pinecone` | `api_key`, `host` (index host) | Domain CRUD: `create` = upsert, `read` = fetch and/or query (payload discriminates), `update` = upsert, `delete` = delete by ids / filter — **`httpx` only** (data-plane REST) |

Also in scope:

- Register imports in `domains/connectors/implementations/__init__.py`
- Wrap client/network failures as `ExecutionError` (no bare `ValueError` / `Exception`)
- Unit tests with fakes/mocks — no live production APIs
- `uv add` only for Mongo / Postgres / ClickHouse clients (prefer one small async-friendly client each). Reuse installed `httpx` + `duckdb` for Resend, Langfuse, DuckDB, Supabase, Google Calendar, and Pinecone (no `supabase-py` / Google / Pinecone SDKs)
- Implementation-PR docs: `architecture.md` built-ins list; `mcp_app/guide.py` connector blurb

## Out of scope

- Destinations domain / `query_destination` / Langfuse export workflow MCP (`create_connector`, `create_destination`, …)
- New domain packages
- Typed steps (`db_query`, `langfuse_fetch`, …)
- Changing `ResendFailureNotifier` to call `ResendConnector` (optional follow-up)
- MotherDuck / remote DuckDB-as-a-service (file path only)
- Slack / other email providers
- Encrypting credentials; changing `$secret` shape
- Changing MCP tool names or argument shapes
- Google OAuth begin/complete MCP tools; interactive consent UI; service-account JSON auth
- Supabase Auth / Storage / Realtime
- Google Meet / Drive
- Pinecone control-plane index create/delete
- `supabase-py`, `google-api-python-client`, or `pinecone` SDK dependencies

## Invocation pattern

Agents declare connectors on `FlowSpec.connectors`, then call them with the existing `http_request` step:

```json
{
  "step_type": "http_request",
  "connector": "my_resend",
  "method": "send_email",
  "body_template": {
    "from": "alerts@example.com",
    "to": "ops@example.com",
    "subject": "Hello",
    "text": "Body"
  }
}
```

For DB connectors, `method` is `create` | `read` | `update` | `delete` and `body_template` holds collection/table/filter/sql fields. `path` is unused for non-`http` connectors.

## Tasks

### T0 — Shared conventions

- Document (in this epic + code comments where useful) action naming, secret field conventions, and `ExecutionError` wrapping.
- Ensure new modules are imported from `implementations/__init__.py` so `@ConnectorRegistry.register` side-effects run.
- Keep `http` connector unchanged (generic REST).

**Non-goals:** New Protocol methods; shared base class beyond existing `ConnectorConfig`.

**Verify:** existing connector tests still green after later tasks import new modules.

### T1 — Resend exclusive `send_email`

- Rewrite [`src/navbe/domains/connectors/implementations/resend.py`](../../src/navbe/domains/connectors/implementations/resend.py): drop get/post/put/delete; expose only `send_email`.
- POST `https://api.resend.com/emails` with resolved Bearer `api_key`.
- Validate required payload fields; return Resend JSON on success.
- Update any unit tests that assumed HTTP verb actions.

**Verify:** `uv run pytest tests/unit/domains/connectors -q`

### T2 — MongoDB connector

- Add dependency via `uv add` (e.g. `pymongo` or async equivalent — pick one; prefer async if same size).
- New file `implementations/mongodb.py`: config `uri`, optional `database`; actions `create` / `read` / `update` / `delete`.
- Payload: `collection` required; `document` / `filter` / `update` / `limit` as appropriate per action.
- `test_connection`: ping / trivial command.

**Verify:** unit tests with mocked client; `uv run pytest tests/unit/domains/connectors -q`

### T3 — PostgreSQL connector

- `uv add` one client (e.g. `psycopg[binary]` / `asyncpg` — pick one).
- New file `implementations/postgresql.py`: DSN **or** discrete host fields; parameterized CRUD only (no multi-statement scripts).
- Payload: `table` + `values` / `columns` / `where` / `set` / `returning` as needed; or explicit `sql` + `params` for `read` when table helpers are insufficient — prefer table helpers for create/update/delete.
- `test_connection`: `SELECT 1`.

**Verify:** unit tests with mocked connection; `uv run pytest tests/unit/domains/connectors -q`

### T4 — Langfuse connector

- New file `implementations/langfuse.py` using **`httpx` only** (no Langfuse SDK).
- Config: `host`, `public_key`, `secret_key` (keys via `$secret`).
- Auth: HTTP Basic (`public_key`:`secret_key`).
- Pin concrete Public API paths for CRUD-shaped actions (document chosen endpoints in the implementation module docstring). Minimum: list/get + create where the API supports them; map unsupported delete/update to clear `ExecutionError` with details rather than silent no-ops.
- `test_connection`: authenticated lightweight GET (e.g. projects / health-equivalent).

**Verify:** unit tests with `respx` / httpx mock; `uv run pytest tests/unit/domains/connectors -q`

### T5 — DuckDB external file connector

- New file `implementations/duckdb_connector.py` (or `duckdb_file.py`) — avoid clashing with the in-memory `transform` step.
- Config: `db_path` only (absolute or relative file path owned by the user).
- Actions: `create` / `read` / `update` / `delete` with `sql` / `table` / `rows` / `where` payload fields as standardized in T0.
- Run sync DuckDB calls via `asyncio.to_thread`.
- **Never** default `db_path` under Navbe data dirs; do not embed an analytics sink owned by Navbe (AGENTS.md).

**Verify:** unit tests against a temp `.duckdb` file; `uv run pytest tests/unit/domains/connectors -q`

### T6 — ClickHouse connector

- `uv add` one client (e.g. `clickhouse-connect`).
- New file `implementations/clickhouse.py`: host/port/user/password/database + TLS; CRUD action names; parameterized queries.
- `test_connection`: trivial `SELECT 1` (or client ping).

**Verify:** unit tests with mocked client; `uv run pytest tests/unit/domains/connectors -q`

### T8 — Supabase connector

- New file `implementations/supabase.py` using **`httpx` only** (no `supabase-py`).
- Config: `url`, `service_role_key` (key via `$secret`).
- Headers: `apikey` + `Authorization: Bearer <service_role_key>`.
- Actions: `create` / `read` / `update` / `delete` against PostgREST (`/rest/v1/{table}`); payload `table` + `filters` / `row` / `rows` / `prefer` as needed.
- `test_connection`: authenticated lightweight GET (e.g. root or a probe table if configured — prefer a status/health call that does not require a table name).

**Verify:** unit tests with `respx` / httpx mock; `uv run pytest tests/unit/domains/connectors -q`

### T9 — Google Calendar connector

- New file `implementations/google_calendar.py` using **`httpx` only** (no Google SDK).
- Config: `client_id`, `client_secret`, `refresh_token` (all `$secret`-able strings).
- On use: POST Google OAuth token endpoint to refresh access token, then Calendar API v3 for event CRUD.
- Actions: `create` / `read` / `update` / `delete`; `calendar_id` defaults to `primary`; payload carries event body / `event_id` / list query params.
- `test_connection`: refresh token + lightweight calendar list/get.

**Non-goals:** Device/OAuth MCP tools; service-account JSON; Meet/Drive.

**Verify:** unit tests with `respx` / httpx mock; `uv run pytest tests/unit/domains/connectors -q`

### T10 — Pinecone connector

- New file `implementations/pinecone.py` using **`httpx` only** (no Pinecone SDK).
- Config: `api_key` (`$secret`), `host` (index host).
- Domain CRUD: `create` = upsert, `read` = fetch and/or query (payload discriminates), `update` = upsert, `delete` = delete by ids / filter.
- Data-plane REST only — no control-plane index create/delete.
- `test_connection`: authenticated describe-index-stats or equivalent lightweight GET.

**Verify:** unit tests with `respx` / httpx mock; `uv run pytest tests/unit/domains/connectors -q`

### T7 — Docs + catalog surfacing

When implementation merges:

- Update [`architecture.md`](../architecture.md) built-in connector list (`http`, `resend`, plus the nine EPIC 19 types; describe Resend `send_email`).
- Update `mcp_app/guide.py` (and howto) connector blurb: Resend via `send_email`; note `http_request.method` = action name for non-HTTP connectors.
- Confirm `catalog_connectors` / `catalog_full` list all registered types (no new MCP tools).

**Non-goals:** New README; destinations docs; plugin skill rewrite unless asked.

**Verify:**

```bash
uv run ruff check .
uv run ty check src/
uv run lint-imports
uv run pytest tests/unit/domains/connectors -q
uv run pytest -q
```

## Acceptance (implementation)

```bash
uv run ruff check .
uv run ty check src/
uv run lint-imports
uv run pytest tests/unit/domains/connectors -q
uv run pytest -q
```

## Definition of Done

- [ ] `resend` exposes only `send_email` (breaking vs HTTP-verb actions)
- [ ] `mongodb`, `postgresql`, `langfuse`, `duckdb`, `clickhouse`, `supabase`, `google_calendar`, `pinecone` registered with CRUD-shaped actions and config schemas
- [ ] Secrets use `{"$secret": "…"}`; never echo secret values in errors/logs
- [ ] DuckDB uses user-supplied `db_path` only (no Navbe-owned default analytics DB)
- [ ] Langfuse, Supabase, Google Calendar, and Pinecone use `httpx` only (no vendor SDKs)
- [ ] Unit tests mock network/DB clients (except optional temp DuckDB file)
- [ ] Catalog lists all new types; `architecture.md` + howto updated in the implementation PR
- [ ] Guards green (`ruff`, `ty`, `lint-imports`, full pytest)
- [ ] Schedule `ResendFailureNotifier` left unchanged (follow-up only)

## Notes

- FlowSpec connectors that still use `resend` with `method: "post"` / path `/emails` must migrate to `method: "send_email"` + email fields in `body_template`.
- ponytail: invoke non-HTTP connectors through `http_request` — upgrade: generic `connector_action` step if the name confuses agents.
- ponytail: schedule notify still POSTs Resend directly — upgrade: call `ResendConnector.send_email`.
