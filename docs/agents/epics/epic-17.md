# EPIC 17 — Run UX (CLI steps view + MCP execution diagram)

**Status:** done  
**Goal:** Humans and agents can see *how* a run executed — per-step timeline + a ready-to-render Mermaid graph — without inventing it from `node_outputs`.  
**Non-goal:** Mid-run `RUNNING` streaming; new MCP tool names; CLI flow authoring / start from CLI; web UI.

## Depends on

- EPIC 5 — execution / `NodeTrace` / transcripts
- EPIC 7 — MCP `flow_status` / `flow_resume`
- EPIC 13 — `navbe runs status`

## Why

`NodeTrace` + `save_trace` / `transcript.md` existed but nothing wrote traces during LangGraph execution. CLI status showed only coarse status; MCP returned `RunState` without a step timeline or diagram Claude/ChatGPT can render.

## Design

### Traces at node boundaries

`compile_flow` accepts an optional async `on_trace` callback. Step and approval nodes record `NodeTrace` (start/finish/error/latency) and await the callback. Engine passes `repository.save_trace` bound to `run_id`.

### Run detail

`RunRepository.list_traces(run_id)` + `render_run_mermaid(flow, traces, status)`.  
`RunService.detail(run_id) -> RunDetail` with `state`, `steps` (`StepExecution`), `diagram`.

### CLI

`navbe runs status <run_id> [--diagram]` — existing header + steps-style Rich table (`node_id`, `step_type`, `status`, `latency_ms`, `error`). Optional Mermaid fenced block.

### MCP

`flow_run` defaults to ``wait=true``: blocks until settled and returns `steps` +
Mermaid `diagram` in one response. Agents must show the diagram to the user.
`flow_status` / `flow_resume` return the same enriched shape. Use ``wait=false``
only for fire-and-forget + poll.

## In scope

- Wire `NodeTrace` writes; `list_traces`; Mermaid renderer
- `RunService.detail`; CLI steps table; MCP `steps` + `diagram`
- Howto + epic index

## Out of scope

- Changing `flow_run` to wait for completion
- Mid-run progress streaming
- New MCP tools; ASCII-only primary diagrams

## Definition of Done

- [x] `navbe runs status <run_id>` shows steps table with node_id / step_type / status / latency
- [x] `flow_status` / `flow_resume` return `steps[]` + `diagram` (`flowchart TD`)
- [x] `transcript.md` under runs/ has node sections after a real run (traces wired)
- [x] Howto mentions showing `diagram` to the user
- [x] `uv run ruff check .` / `ty check src/` / `lint-imports` green

## Notes

- Keep `flow_run` async (`run_id` immediately); poll `flow_status` for the diagram.
- Mermaid is the agent-facing viz format (no new dependency).
