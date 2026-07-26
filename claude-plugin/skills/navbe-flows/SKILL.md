---
name: navbe-flows
description: >-
  Use Navbe MCP to discover step/connector catalogs, list existing flows,
  validate/create/update FlowSpecs, run/cancel flows, and schedule them
  (`schedule_*`, `when` +30s/+1h/cron). Trigger when the user mentions Navbe,
  flows, workflows, schedules, flow_create, schedule_create, catalog_steps,
  MCP orchestration, or building/running a local Navbe flow.
---

# Navbe flows (Claude Desktop)

Navbe is a **local** workflow engine. You operate it only through Navbe MCP tools.
Prefer **tools** over `navbe://` resources — Claude Desktop often hides resources.

## Before anything else

1. Call `navbe_howto` if unsure of the loop.
2. Call `catalog_steps` and `catalog_connectors` (or `catalog_full`).
3. Call `flow_list`. Use `flow_get` before editing an existing `flow_id`.
4. Store API keys with `secret_set` (local `navbe_credentials.json` only — not
   env). Use `secret_list` / `secret_hint` / `secret_has` — never expect full
   values back. Example: `secret_set` key `RESEND_API_KEY` with `app=resend`.
5. GitHub workspace sync: `auth_github_begin` → show user the code →
   `auth_github_complete` (GitHub App; install if prompted), then
   `sync_connect` (or `sync_configure` + `sync_init`)
   → `sync_pull` / `sync_push`. Syncs **flows + schedules**; never credentials
   or runs.

Never invent `step_type` or connector `type` strings — only catalog keys.

## Author / edit loop

1. Draft a FlowSpec (shape below).
2. `flow_validate` until `valid` is true.
3. `flow_create` (new) or `flow_update` (existing).
4. **Ask the user before** `flow_run`.
5. Prefer default `flow_run` (`wait=true`): blocks until settled and returns
   `steps` + Mermaid `diagram`. **Always** show the user the `diagram` fence
   plus a short steps summary.
6. If `paused`: ask user, then `flow_resume` with `{"approved": true|false}` —
   show `diagram` again.
7. Optional: `flow_list_runs` for history; `flow_cancel` to stop an active run.
8. Optional: schedule with `schedule_*` (see below).

## Schedules

Schedules are separate documents (`schedules/<id>/schedule.json`), not fields on
`FlowSpec`.

1. Create after the flow exists: `schedule_create` with `schedule_id`, `flow_id`,
   `when` (`+30s` / `+1h` / `+1d` or a 5-field cron), optional `name` / `notify`.
2. **Fires only while `navbe serve` is running.** Stdio MCP can CRUD schedules,
   but the tick loop lives in serve — tell the user to run `navbe serve` if
   nothing fires.
3. Single-flight: if the flow already has an active run (`pending` / `running` /
   `paused`), a new start is rejected; scheduled fires skip. Cancel first with
   `flow_cancel` if they need to start another.
4. Toggle with `schedule_enable` / `schedule_disable`; inspect with
   `schedule_list` / `schedule_get` / `schedule_list_runs`.
5. Optional failure email (`notify`): channel `email`, `to`, `from`,
   `api_key: {"$secret": "RESEND_API_KEY"}`, `failure_threshold` (default **1**).

## Minimal FlowSpec

```json
{
  "flow_id": "my_flow",
  "name": "optional name",
  "entry_node": "n1",
  "connectors": {
    "mail": {
      "type": "resend",
      "config": {
        "api_key": {"$secret": "RESEND_API_KEY"}
      }
    }
  },
  "nodes": [
    {
      "id": "n1",
      "step_type": "http_request",
      "config": {
        "connector": "mail",
        "method": "post",
        "path": "/emails",
        "body_template": {
          "from": "onboarding@resend.dev",
          "to": ["user@example.com"],
          "subject": "Hello",
          "html": "<p>Hi</p>"
        }
      }
    }
  ],
  "edges": []
}
```

Secrets: always `{"$secret": "KEY"}` in connector config — never paste live secrets.
Store with `secret_set`; resolves from `navbe_credentials.json` only (not env).
HTTP connectors: put `$secret` in `headers`. Resend: put `$secret` in `api_key`.

## Common step types

Confirm with `catalog_steps` before use:

- `http_request`, `llm_call`, `router`, `set_var`, `transform`, `approval`

## Tool map

| Tool | Use |
| --- | --- |
| `navbe_howto` | Playbook / stuck |
| `secret_set` / `secret_list` / `secret_delete` / `secret_has` | Local credentials (no values returned) |
| `catalog_*` | Valid types before authoring |
| `flow_list` / `flow_get` | Discover / inspect |
| `flow_validate` | Cheap check |
| `flow_create` / `flow_update` | Persist |
| `flow_run` | Start (ask first; default wait=true → steps + diagram) |
| `flow_status` / `flow_resume` | Poll / continue HITL |
| `flow_list_runs` | History |
| `flow_cancel` | Cancel an active run |
| `schedule_create` / `schedule_get` / `schedule_list` / `schedule_update` | Schedule CRUD |
| `schedule_enable` / `schedule_disable` | Toggle schedule |
| `schedule_list_runs` | Runs triggered by schedules |
| `auth_github_*` | GitHub App Device Flow login for sync |
| `sync_*` | GitHub workspace mirror (flows + schedules; not runs/credentials) |

## GitHub sync (workspace)

1. `auth_github_begin` → show `user_code` + `verification_uri` → `auth_github_complete`
   (install the Navbe AI GitHub App if `install_url` is returned)
2. `sync_connect` with `owner` + `name` (creates repo if missing), or `sync_configure` + `sync_init`
3. `sync_pull` to import remote `flows/<flow_id>/flow.json` and
   `schedules/<schedule_id>/schedule.json` into local Navbe
4. Edit locally → `sync_branch_create` → `sync_push`

Never sync runs, credentials, OAuth tokens, archived `flow.vN.json`, or step Python source.

## Rules

- Do not run flows unless the user confirms.
- If MCP tools are missing (`navbe_howto`, `catalog_steps`), tell the user to restart Claude Desktop so `navbe-mcp` reloads.
- Do not claim Langfuse/DuckDB export tools exist unless those tools are listed in the live MCP tool list.
- Schedules do nothing without `navbe serve`; say so when creating or debugging schedules.
