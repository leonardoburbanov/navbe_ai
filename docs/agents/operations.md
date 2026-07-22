# Operations

## Install (operators)

End-user and contributor install, CLI surface, and release assets:
**[../install.md](../install.md)**.

```bash
# end-user
curl -fsSL https://raw.githubusercontent.com/leonardoburbanov/navbe_ai_v0.1/main/scripts/install.sh | bash
# Windows: irm …/scripts/install.ps1 | iex

navbe setup
navbe mcp configure
```

## Local commands (contributors)

```bash
uv sync
uv run ruff check .
uv run ty check src/
uv run lint-imports
uv run pytest
uv run pytest tests/unit/core/test_config.py -v
uv run navbe --help
uv run navbe-mcp --help
```

Prefer the commands documented in [AGENTS.md](../../AGENTS.md) and
[../install.md](../install.md).

## Environment

| Variable | Purpose | Default |
| --- | --- | --- |
| `NAVBE_DB_PATH` | SQLite control-plane path | `<data-home>/navbe.db` |
| `NAVBE_FLOWS_DIR` | Flow definitions directory | `<data-home>/navbe_flows` |
| `NAVBE_CREDENTIALS_PATH` | Local credentials JSON | `<data-home>/navbe_credentials.json` |
| `NAVBE_SYNC_CONFIG_PATH` | GitHub sync config JSON | `<data-home>/navbe_sync.json` |
| `NAVBE_GITHUB_OAUTH_PATH` | Managed GitHub OAuth token JSON | `<data-home>/navbe_github_oauth.json` |
| `NAVBE_GITHUB_OAUTH_CLIENT_ID` | OAuth App client id (Device Flow) | unset (required for login) |
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

## Releases

[`.github/workflows/release.yml`](../../.github/workflows/release.yml) on tag `v*`:

1. `uv build`
2. Upload wheel, sdist, `install.sh`, `install.ps1` to the GitHub Release

No automated wiki generation job — agent docs under `docs/agents/` are hand-maintained.
