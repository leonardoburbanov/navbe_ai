"""CLI onboarding commands (setup, info, login)."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from navbe.cli.main import cli
from tests.unit.cli.conftest import FakeSecretsService, FakeSyncService


def test_navbe_no_args_shows_welcome() -> None:
    """Running navbe with no subcommand prints quick start."""
    runner = CliRunner()
    result = runner.invoke(cli, [])
    assert result.exit_code == 0
    assert "Quick start" in result.output
    assert "navbe setup" in result.output


def test_navbe_help_includes_onboarding_commands() -> None:
    """Root help lists setup, info, login."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "setup" in result.output
    assert "info" in result.output
    assert "login" in result.output
    assert "Quick start" in result.output


def test_info_json(monkeypatch, tmp_path: Path) -> None:
    """info --json returns structured status."""
    fake_secrets = FakeSecretsService()
    fake_secrets._data["GITHUB_TOKEN"] = "x"  # noqa: SLF001
    fake_sync = FakeSyncService()
    monkeypatch.setattr("navbe.cli.info.get_secrets_service", lambda: fake_secrets)
    monkeypatch.setattr("navbe.cli.info.get_sync_service", lambda: fake_sync)
    monkeypatch.setattr(
        "navbe.cli.info.get_settings",
        lambda: type(
            "S",
            (),
            {
                "flows_dir": tmp_path / "flows",
                "db_path": tmp_path / "navbe.db",
                "credentials_path": tmp_path / "navbe_credentials.json",
                "sync_config_path": tmp_path / "navbe_sync.json",
            },
        )(),
    )
    monkeypatch.setattr("navbe.cli.info.find_repo_root", lambda: None)

    runner = CliRunner()
    result = runner.invoke(cli, ["info", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["version"]
    assert data["credentials"]["stored_key_count"] == 1
    assert data["sync"]["configured"] is True


def test_setup_dry_run(monkeypatch) -> None:
    """setup --dry-run previews steps without uv sync."""
    monkeypatch.setattr("navbe.cli.setup.find_repo_root", lambda: Path.cwd())
    monkeypatch.setattr("navbe.cli.setup.get_secrets_service", lambda: FakeSecretsService())
    runner = CliRunner()
    result = runner.invoke(cli, ["setup", "--dry-run", "--skip-sync"])
    assert result.exit_code == 0
    assert "Dry run" in result.output
    assert "navbe-mcp" in result.output


def test_login_status(monkeypatch) -> None:
    """login --status lists recommended keys without values."""
    fake = FakeSecretsService()
    fake._data["GITHUB_TOKEN"] = "secret"  # noqa: SLF001
    monkeypatch.setattr("navbe.cli.login.get_secrets_service", lambda: fake)
    runner = CliRunner()
    result = runner.invoke(cli, ["login", "--status"])
    assert result.exit_code == 0
    assert "GITHUB_TOKEN" in result.output
    assert "yes" in result.output
    assert "secret" not in result.output
