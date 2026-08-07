# EPIC 20 — Navbe Desktop (Tauri)

**Status:** in progress  
**Goal:** One downloadable Windows installer. User double-clicks, the app starts the Navbe daemon itself, and everything agents can do over MCP is doable by a human in a GUI.  
**Non-goal:** macOS/Linux installers (build config stays cross-platform; only Windows is released this epic), drag-and-drop graph canvas, auto-update, code signing.

## Depends on

- EPIC 8 — FastAPI REST surface
- EPIC 11 / 16 — credentials JSON + masked hints
- EPIC 13 — `navbe serve` daemon
- EPIC 14 / 15 — GitHub sync + Device Flow
- EPIC 17 — run detail (steps + Mermaid)
- EPIC 18 — schedules
- EPIC 19 — connector catalog richness

## Locked decisions

| Decision | Choice |
| --- | --- |
| Shell | Tauri 2 + React 18 + TypeScript + Vite (`pnpm`) |
| Daemon | Attach to `http://127.0.0.1:8000` if healthy; else spawn bundled sidecar; kill only if we spawned it |
| Sidecar | PyInstaller **onedir** of `navbe` CLI → `navbe.exe serve --host 127.0.0.1 --port 8000` |
| Authoring UI | Node/edge list editor + RJSF forms from catalog + Mermaid preview (no canvas) |
| Data home | Packaged app uses `~/.navbe` (same as CLI) |

## In scope

1. REST parity for the UI: catalog routes, `POST /flows/validate`, `GET /runs?flow_id=`, enriched run detail (`steps` + `diagram`), CORS for Tauri/Vite origins.
2. `desktop/` Tauri app with Home, Credentials, Connectors, Flows, Runs, Schedules, Sync pages.
3. Rust sidecar lifecycle + `daemon_status` command.
4. Windows packaging: `scripts/build_sidecar.ps1`, NSIS + MSI via Tauri, `.github/workflows/desktop-release.yml`.
5. Docs: this epic, delivery/quickstart index, install guide Desktop section.

## Out of scope

- macOS / Linux release artifacts
- Flow graph canvas / drag-and-drop
- Auto-update / code signing
- Talking to the daemon over MCP from the UI (REST only)

## Layout

```
desktop/
  package.json, vite.config.ts, tsconfig.json, index.html
  src/                 # React UI
  src-tauri/           # Rust + tauri.conf.json + resources/navbe/
scripts/build_sidecar.ps1
.github/workflows/desktop-release.yml
src/navbe/api/v1/routes/catalog.py
src/navbe/domains/execution/payloads.py
```

## Acceptance

```bash
# API guards
uv sync
uv run ruff check .
uv run ty check src/
uv run lint-imports
uv run pytest

# Desktop (after Rust + MSVC available)
cd desktop
pnpm install
pnpm build
# optional local full build:
#   powershell -File ../scripts/build_sidecar.ps1
#   pnpm tauri build
```

## Definition of Done

- [x] `catalog`, `flows/validate`, `runs` list + enriched detail live over REST
- [x] Tauri + React scaffold with seven pages wired to REST
- [x] Sidecar attach-or-spawn lifecycle in Rust (`daemon_status`)
- [x] PyInstaller build script + NSIS/MSI config + desktop release workflow
- [x] Docs updated (this page, delivery, quickstart, install)
- [ ] `pnpm tauri build` produces a working NSIS `.exe` on a clean Windows box (requires MSVC Build Tools + sidecar build; CI on `v*` tags)
