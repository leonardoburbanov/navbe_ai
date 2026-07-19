# EPIC 9 — End-to-End Demo + Claude Desktop & Cursor Connection

**Status:** done (automated DoD green; manual client walkthroughs are human sign-off)  
**Goal:** Shared stdio MCP entrypoint, fake sales-bot fixture, CI e2e demo, dual-client docs.  
**Non-goal:** New domain logic; client-specific server code.

## Delivered

| Area | Location |
| --- | --- |
| Stdio entrypoint | `src/navbe/mcp_stdio.py` → `uv run navbe-mcp` |
| Fake sales bot | `scripts/fake_sales_bot.py` (port via `FAKE_SALES_BOT_PORT`) |
| Stdio contract tests | `tests/integration/test_mcp_stdio_entrypoint.py` |
| Fake bot unit tests | `tests/unit/scripts/test_fake_sales_bot.py` |
| Automated demo | `tests/integration/test_demo_end_to_end.py` |
| Client walkthrough | `docs/connect_agents.md` |

## Definition of Done

- [x] `uv run pytest tests/integration/test_mcp_stdio_entrypoint.py -v` green
- [x] `uv run pytest tests/unit/scripts/test_fake_sales_bot.py -v` green
- [x] `uv run pytest tests/integration/test_demo_end_to_end.py -v` green
- [x] `uv run navbe-mcp --help` exits cleanly
- [x] `docs/connect_agents.md` with verified Claude Desktop + Cursor paths
- [ ] Manual Claude Desktop walkthrough signed off (human)
- [ ] Manual Cursor walkthrough signed off (human; note Ask/Agent mode)
- [x] ruff / ty / lint-imports green

## Notes

- FastMCP `run(transport="stdio", show_banner=False)` — banner off keeps stdout MCP-clean.
- Automated demo uses the existing `sales_bot_objection_test` fixture against the real fake-bot process (CRM notes endpoint on the same server).
