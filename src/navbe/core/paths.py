"""Filesystem helpers for repo checkout vs tool-installed layout."""

from __future__ import annotations

from pathlib import Path


def find_repo_root(start: Path | None = None) -> Path | None:
    """Return navbe repo root if ``start`` is inside a checkout."""
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "src" / "navbe").is_dir():
            try:
                text = (candidate / "pyproject.toml").read_text(encoding="utf-8")
            except OSError:
                continue
            if 'name = "navbe"' in text:
                return candidate
    return None


def default_data_home() -> Path:
    """Repo root when developing from a checkout; else ``~/.navbe``."""
    repo = find_repo_root()
    if repo is not None:
        return repo
    return Path.home() / ".navbe"
