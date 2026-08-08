# Build the Navbe Python sidecar (PyInstaller onedir) for Tauri bundling.
#
# Usage (from repo root):
#   powershell -File scripts/build_sidecar.ps1
#
# Output:
#   desktop/src-tauri/resources/navbe/navbe.exe (+ _internal/)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $Uv) {
  $UvPath = "$env:LOCALAPPDATA\hermes\bin\uv.exe"
  if (Test-Path $UvPath) {
    Set-Alias -Name uv -Value $UvPath
  } else {
    throw "uv not found on PATH"
  }
}

Write-Host "Ensuring PyInstaller is installed…"
uv sync --all-groups
uv add --dev pyinstaller | Out-Null

$OutDir = Join-Path $Root "desktop\src-tauri\resources\navbe"
$WorkDir = Join-Path $Root "build\sidecar"
$SpecName = "navbe"

New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null
if (Test-Path $OutDir) {
  Remove-Item -Recurse -Force $OutDir
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Host "Running PyInstaller onedir…"
uv run pyinstaller `
  --noconfirm `
  --clean `
  --name $SpecName `
  --onedir `
  --console `
  --distpath $WorkDir `
  --workpath (Join-Path $WorkDir "work") `
  --specpath $WorkDir `
  --collect-all duckdb `
  --collect-all psycopg `
  --collect-all pymongo `
  --collect-all clickhouse_connect `
  --collect-all langgraph `
  --collect-all fastmcp `
  --collect-all uvicorn `
  --hidden-import navbe.main `
  --hidden-import uvicorn.logging `
  --hidden-import uvicorn.loops.auto `
  --hidden-import uvicorn.protocols.http.auto `
  --hidden-import uvicorn.protocols.websockets.auto `
  --hidden-import uvicorn.lifespan.on `
  (Join-Path $Root "src\navbe\cli\main.py")

$Built = Join-Path $WorkDir $SpecName
if (-not (Test-Path $Built)) {
  throw "PyInstaller output missing: $Built"
}

Copy-Item -Recurse -Force (Join-Path $Built "*") $OutDir

if (-not (Test-Path (Join-Path $OutDir "navbe.exe"))) {
  $found = Get-ChildItem $OutDir -Filter "*.exe" | Select-Object -First 1
  if ($null -eq $found) { throw "No .exe produced in $OutDir" }
  Rename-Item $found.FullName "navbe.exe"
}

$stampPath = Join-Path $OutDir ".sidecar-stamp"
$git = ""
try { $git = (git -C $Root rev-parse --short HEAD 2>$null).Trim() } catch { }
@(
  "built_at=$(Get-Date -Format o)"
  "git=$git"
  "features=catalog,defaults"
) | Set-Content -Path $stampPath -Encoding utf8

# Keep the empty-dir placeholder for git when resources are ignored.
$gitkeep = Join-Path $OutDir ".gitkeep"
if (-not (Test-Path $gitkeep)) {
  New-Item -ItemType File -Path $gitkeep -Force | Out-Null
}

Write-Host "Sidecar ready at $OutDir (stamp written)"
Get-ChildItem $OutDir | Select-Object Name, Length | Format-Table
