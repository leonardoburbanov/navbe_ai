#!/usr/bin/env bash
# Install Navbe CLI + MCP via uv tool install (Cursor-style one-liner).
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/leonardoburbanov/navbe_ai_v0.1/main/scripts/install.sh | bash
#   # or after a release:
#   curl -fsSL https://github.com/leonardoburbanov/navbe_ai_v0.1/releases/latest/download/install.sh | bash
set -euo pipefail

REPO="${NAVBE_REPO:-https://github.com/leonardoburbanov/navbe_ai_v0.1.git}"
REF="${NAVBE_REF:-}"  # optional tag/branch, e.g. v0.1.0

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

bold "Navbe installer"
info "Installing CLI (navbe) and MCP server (navbe-mcp)"

if ! command -v uv >/dev/null 2>&1; then
  info "uv not found — installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # shellcheck disable=SC1090
  if [ -f "$HOME/.local/bin/env" ]; then
    # newer uv installer
    . "$HOME/.local/bin/env" || true
  fi
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

command -v uv >/dev/null 2>&1 || die "uv still not on PATH after install"

SPEC="git+${REPO}"
if [ -n "$REF" ]; then
  SPEC="${SPEC}@${REF}"
fi

info "uv tool install ${SPEC}"
uv tool install --force "$SPEC"

UV_TOOL_BIN="$(uv tool dir --bin 2>/dev/null || true)"
if [ -z "$UV_TOOL_BIN" ]; then
  UV_TOOL_BIN="$HOME/.local/bin"
fi

if ! command -v navbe >/dev/null 2>&1; then
  info "Add to PATH: export PATH=\"${UV_TOOL_BIN}:\$PATH\""
  export PATH="${UV_TOOL_BIN}:$PATH"
fi

command -v navbe >/dev/null 2>&1 || die "navbe not on PATH (bin dir: ${UV_TOOL_BIN})"
command -v navbe-mcp >/dev/null 2>&1 || die "navbe-mcp not on PATH"

bold "Installed"
info "$(navbe --version)"
info "Next:"
info "  navbe setup"
info "  navbe mcp configure"
info "  navbe-mcp --help"
