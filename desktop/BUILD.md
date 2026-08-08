# Navbe Desktop — rebuild installers

How to regenerate the Windows installers (NSIS `.exe` + MSI), what you need on the machine, and how to remove an installed build.

Only Windows is packaged today (`nsis` + `msi`). See [docs/install.md](../docs/install.md) for the CLI one-liner installers (`install.ps1` / `install.sh`); those are scripts, not built artifacts.

---

## Prerequisites

| Tool | Notes |
| --- | --- |
| Windows 10/11 | Build host (MSVC + NSIS/WiX via Tauri) |
| [uv](https://docs.astral.sh/uv/) | Python 3.12+ env for the sidecar |
| [Node.js](https://nodejs.org/) 22+ + [pnpm](https://pnpm.io/) 10 | Frontend + `@tauri-apps/cli` |
| [Rust](https://rustup.rs/) stable | `rustup default stable` |
| **MSVC Build Tools** | “Desktop development with C++” (or VS Build Tools + Windows SDK) |
| WebView2 | Usually already on Win10/11; install the [Evergreen Runtime](https://developer.microsoft.com/microsoft-edge/webview2/) if needed |

Optional check:

```powershell
uv --version
node --version
pnpm --version
rustc --version
```

---

## Generate installers again

Run from the **repo root**. Order matters: sidecar first, then Tauri.

```powershell
# 1) Python deps + PyInstaller onedir → desktop/src-tauri/resources/navbe/
uv sync --all-groups
powershell -File scripts/build_sidecar.ps1

# 2) Desktop UI + Rust + NSIS/MSI
cd desktop
pnpm install
pnpm tauri build
```

### What each step does

1. **`scripts/build_sidecar.ps1`** — packs the `navbe` CLI with PyInstaller (`onedir`) into `desktop/src-tauri/resources/navbe/` (`navbe.exe` + `_internal/`). Tauri bundles that folder as app resources.
2. **`pnpm tauri build`** — builds the React UI, compiles the Rust shell, and produces Windows installers.

### Artifacts

| Kind | Path |
| --- | --- |
| NSIS installer | `desktop/src-tauri/target/release/bundle/nsis/*.exe` |
| MSI installer | `desktop/src-tauri/target/release/bundle/msi/*.msi` |
| Unpacked app (dev check) | `desktop/src-tauri/target/release/Navbe.exe` |

Double-click the `.exe` or `.msi` to install locally.

### CI (no local MSVC)

Push a `v*` tag; [`.github/workflows/desktop-release.yml`](../.github/workflows/desktop-release.yml) builds the same pipeline and attaches NSIS/MSI to the GitHub Release.

```powershell
git tag v0.1.0
git push origin v0.1.0
```

---

## Dev loop (no installer)

For UI/Rust work without packaging:

```powershell
# sidecar still required if you want the app to spawn the daemon itself
powershell -File scripts/build_sidecar.ps1
cd desktop
pnpm install
pnpm tauri dev
```

Or run `uv run navbe serve` separately; the app attaches to `http://127.0.0.1:8000` when healthy.

On launch the app starts the bundled sidecar (if nothing is already healthy on `:8000`) and proxies all REST calls through Rust — no separate CLI step.

---

## Uninstall

### Desktop app (NSIS / MSI)

1. **Settings → Apps → Installed apps** → uninstall **Navbe**  
   (or Control Panel → Programs and Features).

The installer **stops everything first**: `navbe stop`, then force-kills
`navbe-desktop.exe` / `navbe.exe` (desktop + sidecar/daemon) and clears
`%USERPROFILE%\.navbe\serve.pid`. You do not need to quit the app manually.

That removes the installed app under Program Files. It does **not** delete
local data under `%USERPROFILE%\.navbe`.

Hooks live in `src-tauri/windows/hooks.nsh` (NSIS) and
`src-tauri/windows/stop-on-uninstall.wxs` (MSI); both call
`resources/stop-all.cmd`.

### Local data (optional)

Desktop and CLI share `%USERPROFILE%\.navbe` (credentials, SQLite, flows, schedules).

```powershell
# remove data home (destructive — secrets + DB)
Remove-Item -Recurse -Force "$env:USERPROFILE\.navbe"
```

Also clear MCP client entries if you no longer want agents talking to Navbe (`~/.cursor/mcp.json`, Claude Desktop config) — see [docs/connect_agents.md](../docs/connect_agents.md).

### CLI tool install (separate from the desktop `.exe`)

If you installed via `install.ps1` / `uv tool install navbe`:

```powershell
navbe stop
uv tool uninstall navbe
```

Desktop uninstall already kills a running `navbe.exe` serve; it does not remove the `uv tool` install.
---

## Common failures

| Symptom | Fix |
| --- | --- |
| `Bundled navbe sidecar not found` | Re-run `scripts/build_sidecar.ps1` before `pnpm tauri build` |
| Linker / `link.exe` errors | Install MSVC Build Tools + Windows SDK; open a **Developer** / refreshed PowerShell |
| `uv not found` | Install uv and ensure it is on `PATH` |
| Empty `bundle/nsis` or `bundle/msi` | Confirm `tauri.conf.json` has `"targets": ["nsis", "msi"]` and the build finished without error |

Product name / version / bundle id: `desktop/src-tauri/tauri.conf.json` (`productName`, `version`, `identifier`).
