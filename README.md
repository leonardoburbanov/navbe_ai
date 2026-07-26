# Navbe

Local-first workflow orchestration for AI agents. One daemon serves **MCP**, **schedules**, and the **HTTP API**.

## Install (one command)

**macOS / Linux / WSL**

```bash
curl -fsSL https://raw.githubusercontent.com/leonardoburbanov/navbe_ai/main/scripts/install.sh | bash
```

**Windows (PowerShell)**

```powershell
irm https://raw.githubusercontent.com/leonardoburbanov/navbe_ai/main/scripts/install.ps1 | iex
```

That installs `navbe`, starts `navbe serve` in the background, and writes Cursor / Claude Desktop MCP config to:

`http://127.0.0.1:8000/mcp`

Then **restart Cursor or Claude Desktop**.

```bash
navbe status
navbe secret set YOUR_KEY --app your_app   # when a connector needs it
```

Or with [uv](https://docs.astral.sh/uv/) directly:

```bash
uv tool install navbe
navbe bootstrap
```

(If the PyPI package is not published yet, the install scripts fall back to git.)

## Contributor checkout

```bash
git clone https://github.com/leonardoburbanov/navbe_ai.git
cd navbe_ai
uv sync
uv run navbe bootstrap
```

## Docs

- [Install & distribution](docs/install.md)
- [Connect agents](docs/connect_agents.md)
- [Agent quickstart](docs/agents/quickstart.md)

## License

Open source — see the repository for terms.
