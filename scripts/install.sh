#!/usr/bin/env bash
# Install Navbe CLI + start local daemon (MCP + schedules) in one shot.
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/leonardoburbanov/navbe_ai/main/scripts/install.sh | bash
#   # or after a release:
#   curl -fsSL https://github.com/leonardoburbanov/navbe_ai/releases/latest/download/install.sh | bash
#
# Env:
#   NAVBE_FROM_GIT=1          install from git instead of PyPI
#   NAVBE_REPO / NAVBE_REF    git remote + tag/branch when NAVBE_FROM_GIT=1
set -euo pipefail

REPO="${NAVBE_REPO:-https://github.com/leonardoburbanov/navbe_ai.git}"
REF="${NAVBE_REF:-}"
FROM_GIT="${NAVBE_FROM_GIT:-}"

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

bold "Navbe installer"
info "Installing CLI (navbe) and bootstrapping the local daemon"

if ! command -v uv >/dev/null 2>&1; then
  info "uv not found — installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # shellcheck disable=SC1090
  if [ -f "$HOME/.local/bin/env" ]; then
    . "$HOME/.local/bin/env" || true
  fi
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

command -v uv >/dev/null 2>&1 || die "uv still not on PATH after install"

if [ -n "$FROM_GIT" ] || [ -n "$REF" ]; then
  SPEC="git+${REPO}"
  if [ -n "$REF" ]; then
    SPEC="${SPEC}@${REF}"
  fi
  info "uv tool install ${SPEC}"
  uv tool install --force "$SPEC"
else
  info "uv tool install navbe"
  if ! uv tool install --force navbe; then
    info "PyPI package not available yet — falling back to git"
    SPEC="git+${REPO}"
    if [ -n "$REF" ]; then
      SPEC="${SPEC}@${REF}"
    fi
    uv tool install --force "$SPEC"
  fi
fi

UV_TOOL_BIN="$(uv tool dir --bin 2>/dev/null || true)"
if [ -z "$UV_TOOL_BIN" ]; then
  UV_TOOL_BIN="$HOME/.local/bin"
fi

if ! command -v navbe >/dev/null 2>&1; then
  info "Add to PATH: export PATH=\"${UV_TOOL_BIN}:\$PATH\""
  export PATH="${UV_TOOL_BIN}:$PATH"
fi

command -v navbe >/dev/null 2>&1 || die "navbe not on PATH (bin dir: ${UV_TOOL_BIN})"

bold "Bootstrap"
navbe bootstrap

bold "Installed"
info "$(navbe --version)"
info "Next: restart Cursor / Claude Desktop, then: navbe status"
