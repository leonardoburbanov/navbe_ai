# EPIC 0 — Bootstrap

**Status:** done  
**Goal:** Installable project, loadable configuration, base exceptions, green CI.  
**Non-goal:** No domain logic; no files inside `domains/*/` except `__init__.py`.

## Delivered

| Area | Location |
| --- | --- |
| Package + deps (`uv`, FastAPI, FastMCP, DuckDB, SQLAlchemy async, LangGraph, …) | `pyproject.toml`, `uv.lock` |
| Settings + `get_settings()` | `src/navbe/core/config.py` |
| `NavbeError` hierarchy | `src/navbe/core/exceptions.py` |
| Async engine / session helpers (no tables) | `src/navbe/core/database.py` |
| Skeleton packages | `api/`, `mcp_app/`, `domains/`, `dependencies.py`, `main.py` |
| Architecture guard | `.importlinter` |
| CI | `.github/workflows/ci.yml` |
| Env template | `.env.example` |
| Tests | `tests/unit/core/test_*.py` |

## Definition of Done

- [x] `uv sync` without errors
- [x] `uv run pytest` all green
- [x] `uv run ruff check .` → 0 errors
- [x] `uv run ty check src/` → 0 errors
- [x] `uv run lint-imports` → 0 violations
- [x] CI steps pass locally in sequence
- [x] No logic under `domains/*/` (only `__init__.py`)
- [x] `.env.example` documents `NAVBE_*` vars (no secrets)

## Tasks (reference)

| Task | Summary |
| --- | --- |
| 0.1 | `uv` package init, runtime + dev deps, pytest/ruff/ty config |
| 0.2 | Folder skeleton (no domain subpackages) |
| 0.3 | `Settings` + cached `get_settings()` + unit tests |
| 0.4 | Exception hierarchy + unit tests |
| 0.5 | `create_engine` / `get_session` + unit tests |
| 0.6 | import-linter layers contract |
| 0.7 | GitHub Actions CI + `conftest` settings fixture |

## Next

Do not invent EPIC 1 here. Wait for an explicit epic brief. When it lands, add `epics/epic-1.md` and link it from [delivery.md](../delivery.md).
