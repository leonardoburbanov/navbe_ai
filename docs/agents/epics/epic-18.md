# EPIC 18 — Schedule Flows

**Status:** done  
**Goal:** Time-based flow schedules with single-flight execution, run cancel, and email alerts on repeated failures.  
**Host:** scheduler tick loop runs only inside `navbe serve` / FastAPI lifespan.  
**Overlap:** reject/skip a new start while the flow has an active run (`pending` / `running` / `paused`); cancel the active run first to start another.

## Depends on

- EPIC 5 — execution / runs
- EPIC 7 / 10 — MCP tools
- EPIC 13 — human CLI
- EPIC 14 — reserved `schedules/<id>/schedule.json` sync layout

## In scope

- `domains/schedules/` — ScheduleSpec, when parser (`+30s` / cron via croniter), FS+SQLite store
- Single-flight + `flow_cancel` / `RunService.cancel` + `CANCELLED` status
- SchedulerLoop in `navbe serve` lifespan (~10s tick)
- Failure email via Resend (`notify`, default `failure_threshold=1`, latch until success)
- MCP `schedule_*` + `flow_cancel`; CLI `navbe schedules` / `navbe runs cancel`; REST parity
- `SchedulesAsset` registered for sync

## Non-goals

- Destinations / Langfuse product rename
- Scheduler in `navbe-mcp` stdio
- Auto-cancel-then-restart on overlap
- Slack/webhooks
- Queueing missed fires while serve was down (on wake: fire once if due, then next)

## Acceptance

```bash
uv run ruff check .
uv run ty check src/
uv run lint-imports
uv run pytest tests/unit/domains/schedules -q
uv run pytest tests/unit/domains/execution/test_single_flight.py -q
uv run pytest -q
```

## Definition of Done

- [x] Schedules persist as `schedules/<id>/schedule.json` and sync via SchedulesAsset
- [x] Tick loop only in `navbe serve`; due schedules start runs with `trigger=schedule`
- [x] Busy flow: manual start raises; scheduled fire skips and advances next_run_at
- [x] Cancel active run via MCP/CLI/REST
- [x] Failure notify via Resend after threshold (default 1), latched until success
- [x] Guards green
