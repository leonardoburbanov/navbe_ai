"""Agent playbook for Claude Desktop and other MCP clients."""

from fastmcp import FastMCP

# Single source for tool / resource / prompt exposures.
NAVBE_HOWTO = """\
# Navbe MCP playbook (Claude Desktop)

Navbe runs local workflow graphs (flows). Prefer **tools** over `navbe://` resources —
Claude Desktop often does not surface resources to the model.

## Always start here

1. Call tool `navbe_howto` (this text) if you are unsure.
2. Call `catalog_steps` and `catalog_connectors` (or `catalog_full`) before authoring.
3. Call `flow_list` to see what already exists. Use `flow_get` before editing.
4. For connector API keys: prefer `secret_set` (local JSON credentials) over editing `.env`.
   Use `secret_list` / `secret_has` to check keys — values are never returned.
5. To share workspace metadata via GitHub:
   `auth_github_begin` → show the user the code → `auth_github_complete`, then
   `sync_connect` (or `sync_configure` + `sync_init`) → `sync_pull` / `sync_push`.

Do **not** invent step_type or connector type strings — only use catalog keys.

## Author / edit loop

1. Build a FlowSpec dict (see shape below).
2. `flow_validate` — fix until `valid` is true.
3. `flow_create` (new) or `flow_update` (existing `flow_id`).
4. **Ask the user before** `flow_run`.
5. Poll `flow_status` with the returned `run_id` until status is
   `completed`, `failed`, or `paused`.
6. If `paused` (approval node): ask the user, then `flow_resume` with
   `{"approved": true}` or `{"approved": false}`.
7. Optional: `flow_list_runs` for history.

## FlowSpec shape (minimal)

```json
{
  "flow_id": "my_flow",
  "name": "optional display name",
  "entry_node": "n1",
  "connectors": {
    "api": {
      "type": "http",
      "config": {
        "base_url": "https://example.com",
        "headers": {},
        "timeout": 30
      }
    }
  },
  "nodes": [
    {
      "id": "n1",
      "step_type": "http_request",
      "config": {
        "connector": "api",
        "method": "get",
        "path": "/health"
      }
    }
  ],
  "edges": []
}
```

Secrets in connector headers: `{"Authorization": {"$secret": "ENV_KEY_NAME"}}`
(never put live secret values in the spec). Store keys with `secret_set`
(writes `navbe_credentials.json`); resolution order is credentials file, then env.

## Step types (discover via catalog_steps)

- `http_request` — call a named http connector
- `llm_call` — prompt call
- `router` — branch on condition → routes
- `set_var` — extract one value
- `transform` — SQL over view `input`
- `approval` — pause for human decision

## Connector types (discover via catalog_connectors)

- `http` — base_url + optional headers/timeout; used by `http_request`

## Tool map

| Tool | When |
| --- | --- |
| `navbe_howto` | First call / stuck |
| `secret_*` | Local connector credentials (no values) |
| `auth_github_begin` / `auth_github_complete` | GitHub Device Flow (sync auth) |
| `auth_github_status` / `auth_github_logout` | OAuth presence / logout |
| `catalog_steps` / `catalog_connectors` / `catalog_full` | Before authoring |
| `flow_list` / `flow_get` | Discover existing flows |
| `flow_validate` | Cheap check before save |
| `flow_create` / `flow_update` | Persist |
| `flow_run` | Start (ask user first) |
| `flow_status` | Poll run |
| `flow_resume` | Continue after approval |
| `flow_list_runs` | Run history for one flow |
| `sync_connect` / `sync_configure` / `sync_init` / `sync_status` | Bind a GitHub workspace repo |
| `sync_branch_create` / `sync_checkout` | Branching |
| `sync_push` / `sync_pull` | Push/pull workspace assets (flows today) |

GitHub sync never touches runs, credentials, OAuth tokens, archives, or Python step source.
Repo layout: `flows/<flow_id>/flow.json` (connectors/destinations/schedules reserved).

## Optional resources (if your client supports them)

- `navbe://guide` — same playbook
- `navbe://catalog/steps` | `connectors` | `full`
- `navbe://flows` | `navbe://flows/{flow_id}`
"""


def register_prompts(mcp: FastMCP) -> None:
    """Register the Navbe howto prompt (underscored name for Claude)."""

    @mcp.prompt(name="navbe_howto")
    def navbe_howto_prompt() -> str:
        """How to use Navbe MCP tools (discover → validate → create → ask → run)."""
        return NAVBE_HOWTO
