# Architecture (EPIC 0)

Code is the source of truth. This page matches what exists after EPIC 0 bootstrap.

## Layers

Enforced by [`.importlinter`](../../.importlinter):

```
navbe.mcp_app | navbe.api   # outer: thin handlers
        ↓
navbe.domains               # use-cases (empty until later EPICs)
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

Planned domain names: `flows`, `execution`, `catalog`. Do not document their APIs until implemented.

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

## Persistence split (target)

- **SQLite** (`aiosqlite` + SQLAlchemy async) — app/control-plane state
- **DuckDB / CSV** — analytics destinations (not in tree yet)

See DuckDB caveats in [AGENTS.md](../../AGENTS.md).
