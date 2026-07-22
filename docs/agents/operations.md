# Operations

## Local commands

```bash
uv sync
uv run ruff check .
uv run ty check src/
uv run lint-imports
uv run pytest
uv run pytest tests/unit/core/test_config.py -v
```

API and MCP entrypoints are not wired yet (stubs under `api/` and `mcp_app/`). When they exist, prefer the commands documented in [AGENTS.md](../../AGENTS.md).

## Environment

| Variable | Purpose | Default |
| --- | --- | --- |
| `NAVBE_DB_PATH` | SQLite control-plane path | `<data-home>/navbe.db` |
| `NAVBE_FLOWS_DIR` | Flow definitions directory | `<data-home>/navbe_flows` |
| `NAVBE_CREDENTIALS_PATH` | Local credentials JSON | `<data-home>/navbe_credentials.json` |
| `NAVBE_LOG_LEVEL` | Log level | `INFO` |
| `NAVBE_MCP_SERVER_NAME` | MCP server name | `navbe` |
| `NAVBE_ANTHROPIC_API_KEY` | Optional Anthropic key | unset |

`<data-home>` is the repo root when running from a checkout, otherwise `~/.navbe`.

See [`.env.example`](../../.env.example).

## CI

[`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) on push/PR:

1. `uv sync`
2. `uv run ruff check .`
3. `uv run ty check src/`
4. `uv run lint-imports`
5. `uv run pytest --cov-fail-under=0`

No automated wiki generation job — agent docs under `docs/agents/` are hand-maintained.
