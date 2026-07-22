"""CLI sync commands."""

from __future__ import annotations

from typer.testing import CliRunner

from navbe.cli.main import cli
from tests.unit.cli.conftest import FakeSyncService


def test_sync_status_and_push_pull(monkeypatch) -> None:
    """Sync subcommands call SyncService and print human output."""
    fake = FakeSyncService()
    monkeypatch.setattr("navbe.cli.sync.get_sync_service", lambda: fake)
    monkeypatch.setattr("navbe.cli.actions.get_sync_service", lambda: fake)
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["sync", "configure", "--remote-url", "https://github.com/o/r.git"],
    )
    assert result.exit_code == 0
    assert "Saved sync config" in result.output

    result = runner.invoke(cli, ["sync", "status"])
    assert result.exit_code == 0
    assert "Sync status" in result.output

    result = runner.invoke(cli, ["sync", "branch", "create", "feature-x"])
    assert result.exit_code == 0
    assert fake.branch == "feature-x"

    result = runner.invoke(cli, ["sync", "push", "-m", "test"])
    assert result.exit_code == 0
    assert "message test" in result.output

    result = runner.invoke(cli, ["sync", "pull"])
    assert result.exit_code == 0
    assert "pulled" in result.output
