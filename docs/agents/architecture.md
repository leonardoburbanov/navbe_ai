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

## Domain pattern (when packages appear)

Each `src/navbe/domains/<name>/`:

- `models.py` — Pydantic shapes
- `interfaces.py` — `Protocol` ports
- `service.py` — use-cases depending on Protocols only

Planned domain names: `steps`, `connectors`, `flows`, `execution`, `secrets`, `catalog`. Do not document their APIs until implemented.

## Persistence split (target)

- **SQLite** (`aiosqlite` + SQLAlchemy async) — app/control-plane state
- **DuckDB / CSV** — analytics destinations (not in tree yet)

See DuckDB caveats in [AGENTS.md](../../AGENTS.md).
