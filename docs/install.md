# Install & distribution

How developers get Navbe on their machine without (or with) a git checkout.
Agent wiring after install is in [connect_agents.md](connect_agents.md).

## End-user install (recommended)

One-liner installers ensure [uv](https://docs.astral.sh/uv/) is present, run
`uv tool install navbe`, then **`navbe bootstrap`** so the local daemon is up
and Cursor / Claude point at `http://127.0.0.1:8000/mcp`.

### macOS / Linux / WSL

```bash
curl -fsSL https://raw.githubusercontent.com/leonardoburbanov/navbe_ai/main/scripts/install.sh | bash
```

### Windows (PowerShell)

```powershell
irm https://raw.githubusercontent.com/leonardoburbanov/navbe_ai/main/scripts/install.ps1 | iex
```

### Direct uv (no script)

```bash
uv tool install navbe
navbe bootstrap
```

### Pin a version / install from git

```bash
# bash / WSL — git install
NAVBE_FROM_GIT=1 NAVBE_REF=v0.1.0 curl -fsSL …/scripts/install.sh | bash

# PowerShell
$env:NAVBE_FROM_GIT = "1"
$env:NAVBE_REF = "v0.1.0"
irm …/scripts/install.ps1 | iex

# or
uv tool install git+https://github.com/leonardoburbanov/navbe_ai.git@v0.1.0
navbe bootstrap
```

Optional overrides for the scripts:

| Env var | Default | Purpose |
| --- | --- | --- |
| `NAVBE_FROM_GIT` | unset | Force git install instead of PyPI |
| `NAVBE_REPO` | `https://github.com/leonardoburbanov/navbe_ai.git` | Git remote |
| `NAVBE_REF` | (unset) | Tag or branch (implies git install) |

### Verify

```bash
navbe --version
navbe status              # serve healthy + MCP URL
curl -s http://127.0.0.1:8000/health
```

Then restart Cursor / Claude Desktop.

## Contributor install (checkout)

```bash
git clone https://github.com/leonardoburbanov/navbe_ai.git
cd navbe_ai
uv sync
uv run navbe bootstrap
```

Inside a checkout, prefer `uv run navbe …` so you use the working tree.

## Data home

| Mode | Default data root |
| --- | --- |
| Tool install (`uv tool install` / install scripts) | `~/.navbe/` |
| Git checkout | repo root |

Files under that root (unless overridden by `NAVBE_*`):

| Path | Role |
| --- | --- |
| `navbe.db` | SQLite control plane |
| `navbe_flows/` | Flow definitions + run artifacts |
| `navbe_credentials.json` | Local secrets (never commit) |
| `navbe_github_oauth.json` | Managed GitHub App token (never commit) |
| `navbe_sync.json` | GitHub sync config |
| `serve.pid` / `serve.log` | Detached daemon metadata |

See [agents/operations.md](agents/operations.md) for the full env table.

## Human CLI surface

One process: **`navbe serve`** (MCP at `/mcp` + schedules + REST). Humans use **`navbe`**.

| Command | Role |
| --- | --- |
| `navbe` / `navbe --help` | Interactive slash menu on a TTY; otherwise quick start |
| `navbe bootstrap` | First-run: data dirs, detach serve, write MCP client configs |
| `navbe serve [--detach]` | Foreground or background daemon |
| `navbe status` / `navbe stop` | Daemon health / stop |
| `navbe setup` | Interactive onboarding (secrets, sync, MCP write) |
| `navbe info [--json]` | Paths, credential/sync readiness, version |
| `navbe login` / `navbe login github` | Status / GitHub App Device Flow |
| `navbe logout github` | Clear managed GitHub OAuth token |
| `navbe github install` / `uninstall` / `reinstall` / `status` | Install / remove / fix Navbe AI on GitHub |
| `navbe mcp show` | Print pasteable `mcpServers` JSON (URL) |
| `navbe mcp configure` | Merge Navbe URL into Cursor / Claude Desktop configs |
| `navbe secret …` | Local credentials store (connectors) |
| `navbe sync connect|configure|…` | GitHub workspace mirror (flows + reserved layout) |
| `navbe flows` / `navbe runs` / `navbe steps` | Browse flows, runs, step catalog |

`navbe mcp configure` writes:

| Client | Path |
| --- | --- |
| Cursor (global) | `~/.cursor/mcp.json` |
| Claude Desktop (Windows) | `%APPDATA%\Claude\claude_desktop_config.json` |
| Claude Desktop (macOS) | `~/Library/Application Support/Claude/claude_desktop_config.json` |

Flags: `--client cursor|claude|all`, `--dry-run`, `--host`, `--port`.

## Distribution artifacts

| Artifact | Location | Notes |
| --- | --- | --- |
| `scripts/install.sh` | repo + GitHub Release | bash installer + bootstrap |
| `scripts/install.ps1` | repo + GitHub Release | PowerShell installer + bootstrap |
| Wheel / sdist | GitHub Release + PyPI on `v*` tags | from `uv build` / Trusted Publishing |
| Website install page | (your site) | Mirror the one-liners |

Release pipeline: [`.github/workflows/release.yml`](../.github/workflows/release.yml)
runs on tag `v*`, uploads wheel/sdist/install scripts, and publishes to PyPI.

### Cut a release

```bash
# bump version in pyproject.toml / src/navbe/__init__.py as needed
git tag v0.1.0
git push origin v0.1.0
```

GitHub Actions builds, attaches assets, and publishes to PyPI (Trusted Publisher).

### Out of scope (today)

- Windows desktop / tray app
- Standalone PyInstaller branded `.exe`
- OS service generators (pidfile daemon is enough)

## Website copy (paste into your install page)

**macOS / Linux / WSL**

```bash
curl -fsSL https://raw.githubusercontent.com/leonardoburbanov/navbe_ai/main/scripts/install.sh | bash
```

**Windows**

```powershell
irm https://raw.githubusercontent.com/leonardoburbanov/navbe_ai/main/scripts/install.ps1 | iex
```

**Then**

```bash
navbe status
# restart Cursor / Claude Desktop
```

Full agent connection steps: [connect_agents.md](connect_agents.md).
