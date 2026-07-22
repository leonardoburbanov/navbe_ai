# Install Navbe CLI + MCP via uv tool install (Cursor-style one-liner).
# Usage:
#   irm https://raw.githubusercontent.com/leonardoburbanov/navbe_ai_v0.1/main/scripts/install.ps1 | iex
#   # or after a release:
#   irm https://github.com/leonardoburbanov/navbe_ai_v0.1/releases/latest/download/install.ps1 | iex
$ErrorActionPreference = "Stop"

$Repo = if ($env:NAVBE_REPO) { $env:NAVBE_REPO } else { "https://github.com/leonardoburbanov/navbe_ai_v0.1.git" }
$Ref = $env:NAVBE_REF  # optional tag/branch, e.g. v0.1.0

function Write-Info([string]$Message) {
    Write-Host "  $Message"
}

Write-Host "Navbe installer" -ForegroundColor Cyan
Write-Info "Installing CLI (navbe) and MCP server (navbe-mcp)"

$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    Write-Info "uv not found — installing uv..."
    irm https://astral.sh/uv/install.ps1 | iex
    $env:Path = "$env:USERPROFILE\.local\bin;$env:USERPROFILE\.cargo\bin;$env:Path"
    $uv = Get-Command uv -ErrorAction SilentlyContinue
}
if (-not $uv) {
    throw "uv still not on PATH after install"
}

$spec = "git+$Repo"
if ($Ref) {
    $spec = "${spec}@$Ref"
}

Write-Info "uv tool install $spec"
& uv tool install --force $spec

$toolBin = $null
try {
    $toolBin = (& uv tool dir --bin).Trim()
} catch {
    $toolBin = Join-Path $env:USERPROFILE ".local\bin"
}
if ($toolBin -and ($env:Path -notlike "*$toolBin*")) {
    $env:Path = "$toolBin;$env:Path"
    Write-Info "Add to PATH permanently: $toolBin"
}

$navbe = Get-Command navbe -ErrorAction SilentlyContinue
$mcp = Get-Command navbe-mcp -ErrorAction SilentlyContinue
if (-not $navbe) { throw "navbe not on PATH (bin dir: $toolBin)" }
if (-not $mcp) { throw "navbe-mcp not on PATH" }

Write-Host "Installed" -ForegroundColor Green
Write-Info (& navbe --version)
Write-Info "Next:"
Write-Info "  navbe setup"
Write-Info "  navbe mcp configure"
Write-Info "  navbe-mcp --help"
