# Connect Navbe to Claude Desktop & Cursor AI

Navbe exposes the same MCP server (`uv run navbe-mcp`) over **stdio** for both
clients. There is no client-specific server code — only config file location
differs.

Config paths below were checked against current public docs
([MCP local servers](https://modelcontextprotocol.io/docs/develop/connect-local-servers),
[Cursor MCP](https://cursor.com/docs/mcp)) as of this write-up.

---

## Shared setup (both clients)

### 1. Install and verify Navbe locally

```bash
git clone <repo>
cd navbe_ai_v0.1   # or your local checkout path
uv sync
uv run navbe-mcp --help
```

`--help` should print usage and exit 0 (it must not start a hanging stdio server).

### 2. Set required secrets

```bash
cp .env.example .env
# edit .env — set CRM_API_KEY (and NAVBE_ANTHROPIC_API_KEY if you want live llm_call)
```

For the automated demo fixture, a dummy `CRM_API_KEY` is enough when the fake
sales bot is used as the CRM base URL.

### 3. Start the fake sales-bot fixture

Keep this running in a separate terminal for the whole demo:

```bash
uv run python scripts/fake_sales_bot.py
# → http://localhost:8420  (/health, /chat, /leads/{id}/notes)
```

---

## 4A. Connecting Claude Desktop

**Config file location**

| OS | Path |
| --- | --- |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows (classic installer) | `%APPDATA%\Claude\claude_desktop_config.json` |
| Windows (Store / MSIX / WinGet) | `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json` |

Fastest path: Claude menu → **Settings → Developer → Edit Config** (creates the
file if missing). On Windows Store builds, confirm the opened path is the
virtualized one above if edits do not stick.

**MCP server entry** (use your absolute repo path):

```json
{
  "mcpServers": {
    "navbe": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "C:/NavbeAI/navbe_ai_v0.1",
        "navbe-mcp"
      ]
    }
  }
}
```

On macOS/Linux, replace the directory with something like
`/Users/you/src/navbe_ai_v0.1`.

**Restart Claude Desktop completely** (quit the app, not only close the window)
so it re-spawns the subprocess.

**Verify:** Claude’s MCP / connector UI shows **navbe** as connected.

---

## 4B. Connecting Cursor AI

**Config file location** ([Cursor MCP docs](https://cursor.com/docs/mcp))

| Scope | Path |
| --- | --- |
| Project (recommended for this demo) | `.cursor/mcp.json` in the repo root |
| Global | `~/.cursor/mcp.json` (Windows: `%USERPROFILE%\.cursor\mcp.json`) |

Project and global configs are merged; project wins on name conflicts.

**MCP server entry** (same shape as Claude Desktop today):

```json
{
  "mcpServers": {
    "navbe": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "${workspaceFolder}",
        "navbe-mcp"
      ]
    }
  }
}
```

`${workspaceFolder}` is supported by Cursor’s config interpolation when the
file lives under the project. Absolute paths also work.

**Reload MCP:** Cursor usually picks up `.cursor/mcp.json` without a full
restart. Check **Settings → Tools & MCP** (or the MCP panel) and enable
**navbe** if it is not auto-enabled.

**Verify:** MCP/tools panel lists Navbe tools (`flow.create`, `flow.run`, …)
for the current Agent/Composer session.

---

## 5. Demo prompt (identical for both clients)

```
I have a sales chatbot running at http://localhost:8420 with a POST /chat
endpoint that accepts {message, session_id}. Check what Navbe can do,
then build me a flow that simulates a customer conversation with a
price objection, and ask me before running it.
```

---

## 6. Expected agent behavior

1. Reads `navbe://catalog/steps` and `navbe://catalog/connectors`
2. Builds a FlowSpec using registered types (`http_request`, `set_var`,
   `llm_call`, `router`, optionally `approval`)
3. Calls `flow.validate`, then `flow.create`
4. Asks: “I’ve created this flow as `<flow_id>`. Want me to run it?”
5. On confirmation: `flow.run`, then polls `flow.status`
6. Reports outcome and which branch was taken

### Client approval caveat (important)

Navbe’s `flow.run` / `flow.status` split is designed so agents *can* ask before
executing — but **Claude Desktop** and **Cursor** each have their own tool
approval UX:

| Client | Typical behavior |
| --- | --- |
| Claude Desktop | Often prompts per tool call by default |
| Cursor | Depends on **Ask vs Agent** mode and Auto-Run / approval settings |

If Cursor runs `flow.run` without asking, check the active mode / Auto-Run
setting before assuming a Navbe bug.

---

## 7. Inspect results on disk (client-agnostic)

Default paths come from `.env` / settings (`NAVBE_FLOWS_DIR`, usually
`./navbe_flows`):

```bash
# after a successful create + run
cat navbe_flows/<flow_id>/flow.json
cat navbe_flows/<flow_id>/runs/<run_id>/transcript.md
cat navbe_flows/<flow_id>/runs/<run_id>/state.json
```

---

## Manual validation checklist

| Check | Claude Desktop | Cursor AI |
| --- | --- | --- |
| Client shows Navbe connected | connector list | MCP / Tools panel |
| Agent uses only registered step types | inspect `flow.json` | inspect `flow.json` |
| Confirmation before execution | Desktop per-tool approval | Note Ask/Agent + Auto-Run mode used |
| `transcript.md` readable | subjective | subjective |

**Sign-off (fill in when you run the manual walkthroughs)**

| Client | Date | Operator | Approval mode / notes | Pass? |
| --- | --- | --- | --- | --- |
| Claude Desktop | | | | |
| Cursor AI | | | | |

---

## Automated CI coverage (no live agent)

These prove the **server** side both clients talk to:

```bash
uv run pytest tests/integration/test_mcp_stdio_entrypoint.py -v
uv run pytest tests/unit/scripts/test_fake_sales_bot.py -v
uv run pytest tests/integration/test_demo_end_to_end.py -v
```
