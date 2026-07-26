# Install Navbe CLI + start local daemon (MCP + schedules) in one shot.
# Usage:
#   irm https://raw.githubusercontent.com/leonardoburbanov/navbe_ai_v0.1/main/scripts/install.ps1 | iex
#   # or after a release:
#   irm https://github.com/leonardoburbanov/navbe_ai_v0.1/releases/latest/download/install.ps1 | iex
#
# Env:
#   NAVBE_FROM_GIT=1          install from git instead of PyPI
#   NAVBE_REPO / NAVBE_REF    git remote + tag/branch when using git
$ErrorActionPreference = "Stop"

$Repo = if ($env:NAVBE_REPO) { $env:NAVBE_REPO } else { "https://github.com/leonardoburbanov/navbe_ai_v0.1.git" }
$Ref = $env:NAVBE_REF
$FromGit = $env:NAVBE_FROM_GIT

function Write-Info([string]$Message) {
    Write-Host "  $Message"
}

Write-Host "Navbe installer" -ForegroundColor Cyan
Write-Info "Installing CLI (navbe) and bootstrapping the local daemon"

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

$useGit = [bool]$FromGit -or [bool]$Ref
if ($useGit) {
    $spec = "git+$Repo"
    if ($Ref) { $spec = "${spec}@$Ref" }
    Write-Info "uv tool install $spec"
    & uv tool install --force $spec
} else {
    Write-Info "uv tool install navbe"
    try {
        & uv tool install --force navbe
        if ($LASTEXITCODE -ne 0) { throw "PyPI install failed" }
    } catch {
        Write-Info "PyPI package not available yet — falling back to git"
        $spec = "git+$Repo"
        if ($Ref) { $spec = "${spec}@$Ref" }
        & uv tool install --force $spec
    }
}

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
if (-not $navbe) { throw "navbe not on PATH (bin dir: $toolBin)" }

Write-Host "Bootstrap" -ForegroundColor Cyan
& navbe bootstrap

Write-Host "Installed" -ForegroundColor Green
Write-Info (& navbe --version)
Write-Info "Next: restart Cursor / Claude Desktop, then: navbe status"
