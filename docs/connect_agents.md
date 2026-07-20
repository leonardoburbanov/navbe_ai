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

Prefer the human CLI (stores keys in `navbe_credentials.json`, never echoes values):

```bash
uv run navbe secret set CRM_API_KEY
uv run navbe secret list
```

Or use `.env` (legacy):

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

Navbe ships a Claude **plugin** (MCP + skill) under [`claude-plugin/`](../claude-plugin/).
Prefer installing that package. Manual MCP-only config is the fallback below.

### Option A — Install the Claude plugin (recommended)

Package layout:

```text
claude-plugin/
├── .claude-plugin/plugin.json
├── .mcp.json                 # local navbe-mcp (edit path if needed)
└── skills/navbe-flows/SKILL.md
```

1. Edit `claude-plugin/.mcp.json` so `--directory` is your absolute Navbe checkout
   (default in-repo is `C:/NavbeAI/navbe_ai_v0.1`).
2. Rebuild upload zips if needed (Unix paths required — do **not** use
   PowerShell `Compress-Archive`):

   ```bash
   uv run python claude-plugin/build_zips.py
   ```

3. In Claude Desktop: **Customize → Plugins → +** → upload
   `claude-plugin/navbe-plugin.zip`.
4. Enable the plugin. Confirm the **navbe** connector/tools appear
   (`navbe_howto`, `catalog_steps`, `flow_list`, …).
5. Confirm skill **navbe-flows** is listed under **Customize → Skills** (or via `/`).

**Skill-only (if you already have MCP configured):** upload
`claude-plugin/navbe-flows-skill.zip` under **Customize → Skills → +**.
That zip must contain `navbe-flows/SKILL.md` (folder wrapper matching the
skill name), with forward-slash paths only.

If Claude says *Zip file contains path with invalid characters*, the archive
was built with Windows backslashes — regenerate with `build_zips.py`.

Fully quit and restart Claude Desktop after install so local MCP respawns.

### Option B — MCP only (manual config)

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

**Verify:** Claude’s MCP / connector UI shows **navbe** as connected, with tools
including `navbe_howto`, `catalog_steps`, `flow_list`, `secret_set`, `sync_pull`
(flows/`<id>`/flow.json only — never runs or credentials).

Still upload the **navbe-flows** skill (Option A skill-only) so Claude follows the
discover → validate → create → ask → run loop automatically.

### Claude Desktop tip (important)

Claude Desktop often exposes **tools** but not `navbe://` resources. With the
skill installed, Claude should call `catalog_steps` / `flow_list` on its own.
If not, say:

```
Use the navbe-flows skill. Call navbe_howto first, then catalog_steps and
flow_list. Prefer tools over navbe:// resources. Ask me before flow_run.
```

Or open the MCP prompt named `navbe_howto` if your Claude build lists prompts.

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

**Verify:** MCP/tools panel lists Navbe tools (`catalog_steps`, `flow_list`,
`flow_create`, `flow_run`, …)
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

1. Calls `navbe_howto`, then `catalog_steps` / `catalog_connectors` and
   `flow_list` (prefer tools over `navbe://` resources on Claude Desktop)
2. Builds a FlowSpec using registered types (`http_request`, `set_var`,
   `llm_call`, `router`, optionally `approval`)
3. Calls `flow_validate`, then `flow_create` (or `flow_update` if editing)
4. Asks: “I’ve created this flow as `<flow_id>`. Want me to run it?”
5. On confirmation: `flow_run`, then polls `flow_status`
6. Reports outcome and which branch was taken

### Client approval caveat (important)

Navbe’s `flow_run` / `flow_status` split is designed so agents *can* ask before
executing — but **Claude Desktop** and **Cursor** each have their own tool
approval UX:

| Client | Typical behavior |
| --- | --- |
| Claude Desktop | Often prompts per tool call by default |
| Cursor | Depends on **Ask vs Agent** mode and Auto-Run / approval settings |

If Cursor runs `flow_run` without asking, check the active mode / Auto-Run
setting before assuming a Navbe bug.

---

## 6B. Human CLI (not for agents)

Humans operate Navbe from the terminal without MCP:

```bash
uv run navbe --help
uv run navbe secret set GITHUB_TOKEN    # credentials
uv run navbe sync status                # GitHub flows mirror
uv run navbe runs watch <RUN_ID>        # live run status
uv run navbe steps                      # available step types
uv run navbe serve                      # HTTP API + MCP mount
```

Agents should keep using `navbe-mcp`.

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
