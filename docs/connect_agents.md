# Connect Navbe to Claude Desktop & Cursor AI

Navbe exposes MCP over **HTTP** from the local daemon (`navbe serve`) at
`http://127.0.0.1:8000/mcp`. The same process runs the schedule ticker and REST API.

**Install first:** [install.md](install.md) (one-liner runs `navbe bootstrap`).

---

## Shared setup (both clients)

### 1. Install + bootstrap

```bash
# end-user one-liner (preferred)
# curl …/install.sh | bash   or   irm …/install.ps1 | iex

navbe --version
navbe status
curl -s http://127.0.0.1:8000/health
```

```bash
# contributor checkout
uv sync
uv run navbe bootstrap
```

`navbe bootstrap` creates data dirs, starts `navbe serve --detach`, and writes
Cursor / Claude Desktop configs with the MCP URL.

### 2. Set required secrets

```bash
navbe secret set CRM_API_KEY --app crm
navbe secret set RESEND_API_KEY --app resend
navbe secret list
```

Connector and LLM keys are **not** read from `.env` — only from the credentials
file via `secret_set` / `{"$secret": "KEY"}`.

### 3. Reload the agent client

Fully quit and reopen **Claude Desktop**, or reload MCP in **Cursor**
(Settings → Tools & MCP). Confirm **navbe** is connected and tools appear
(`navbe_howto`, `catalog_steps`, `flow_list`, …).

---

## 4A. Connecting Claude Desktop

### Option A — Install the Claude plugin (recommended)

Package layout:

```text
claude-plugin/
├── .claude-plugin/plugin.json
├── .mcp.json                 # url → http://127.0.0.1:8000/mcp
└── skills/navbe-flows/SKILL.md
```

1. Ensure `navbe serve` is running (`navbe status`).
2. Rebuild upload zips if needed (Unix paths — do **not** use PowerShell
   `Compress-Archive`):

   ```bash
   uv run python claude-plugin/build_zips.py
   ```

3. In Claude Desktop: **Customize → Plugins → +** → upload
   `claude-plugin/navbe-plugin.zip`.
4. Enable the plugin. Confirm tools appear.

**Skill-only:** upload `claude-plugin/navbe-flows-skill.zip` under
**Customize → Skills → +**.

### Option B — MCP only (`navbe mcp configure`)

```bash
navbe mcp configure --client claude
```

Claude Desktop’s `claude_desktop_config.json` **only accepts stdio** (`command` /
`args`). A bare `"url"` entry is skipped with “not valid MCP server
configurations”. Navbe therefore writes an [`mcp-remote`](https://www.npmjs.com/package/mcp-remote)
bridge (requires Node.js / `npx`):

```json
{
  "mcpServers": {
    "navbe": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "http://127.0.0.1:8000/mcp",
        "--allow-http",
        "--transport",
        "http-only"
      ]
    }
  }
}
```

Keep `navbe serve` running. Fully quit and reopen Claude Desktop after editing.

Config locations:

| OS | Path |
| --- | --- |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows (classic) | `%APPDATA%\Claude\claude_desktop_config.json` |
| Windows (Store) | `%LOCALAPPDATA%\Packages\Claude_…\LocalCache\Roaming\Claude\claude_desktop_config.json` |

---

## 4B. Connecting Cursor AI

```bash
navbe mcp configure --client cursor
```

Or project/global `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "navbe": {
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

| Scope | Path |
| --- | --- |
| Project | `.cursor/mcp.json` |
| Global | `~/.cursor/mcp.json` |

---

## 5. Demo prompt (identical for both clients)

```
I have a sales chatbot running at http://localhost:8420 with a POST /chat
endpoint that accepts {message, session_id}. Check what Navbe can do,
then build me a flow that simulates a customer conversation with a
price objection, and ask me before running it.
```

(Checkout-only fixture: `uv run python scripts/fake_sales_bot.py`.)

---

## 6. Expected agent behavior

1. Calls `navbe_howto`, then `catalog_steps` / `catalog_connectors` and `flow_list`
2. Builds a FlowSpec using registered types
3. Calls `flow_validate`, then `flow_create` (or `flow_update`)
4. Asks before `flow_run`, then polls `flow_status`

### Client approval caveat

| Client | Typical behavior |
| --- | --- |
| Claude Desktop | Often prompts per tool call by default |
| Cursor | Depends on Ask vs Agent mode and Auto-Run settings |

---

## 6B. Human CLI

```bash
navbe bootstrap
navbe status
navbe stop
navbe info
navbe login github
navbe sync connect OWNER REPO
navbe serve          # foreground instead of --detach
```

From a checkout, prefix with `uv run`.

---

## Automated CI coverage

```bash
uv run pytest tests/integration/test_mcp_server_standalone.py -v
uv run pytest tests/integration/test_serve_health.py -v
uv run pytest tests/unit/scripts/test_fake_sales_bot.py -v
uv run pytest tests/integration/test_demo_end_to_end.py -v
```
