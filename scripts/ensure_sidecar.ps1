# Fail (or optionally rebuild) unless a stamped PyInstaller sidecar exists.
#
# Usage:
#   powershell -File scripts/ensure_sidecar.ps1
#   powershell -File scripts/ensure_sidecar.ps1 -Build

param(
  [switch]$Build
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$OutDir = Join-Path $Root "desktop\src-tauri\resources\navbe"
$Exe = Join-Path $OutDir "navbe.exe"
$Stamp = Join-Path $OutDir ".sidecar-stamp"

function Test-SidecarReady {
  return (Test-Path $Exe) -and (Test-Path $Stamp)
}

if (Test-SidecarReady) {
  Write-Host "Sidecar OK: $Exe"
  Get-Content $Stamp | ForEach-Object { Write-Host "  $_" }
  exit 0
}

if ($Build) {
  Write-Host "Sidecar missing - running build_sidecar.ps1..."
  & (Join-Path $PSScriptRoot "build_sidecar.ps1")
  if (-not (Test-SidecarReady)) {
    throw "build_sidecar.ps1 finished but stamp/exe still missing under $OutDir"
  }
  exit 0
}

Write-Error "Navbe desktop sidecar missing or unstamped. Expected $Exe and $Stamp. Run: powershell -File scripts/build_sidecar.ps1 (or: pnpm run tauri:build in desktop/)"
exit 1
