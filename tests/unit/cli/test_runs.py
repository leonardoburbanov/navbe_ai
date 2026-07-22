"""CLI runs commands."""

from __future__ import annotations

from click.testing import CliRunner

from navbe.cli.main import cli
from tests.unit.cli.conftest import FakeRunService


def test_runs_list_and_status(monkeypatch) -> None:
    """Runs list/status print run metadata."""
    fake = FakeRunService()
    monkeypatch.setattr("navbe.cli.actions.get_run_service", lambda: fake)
    runner = CliRunner()

    result = runner.invoke(cli, ["runs", "list", "demo"])
    assert result.exit_code == 0
    assert "r1" in result.output

    result = runner.invoke(cli, ["runs", "status", "r1"])
    assert result.exit_code == 0
    assert "running" in result.output


def test_runs_watch_until_completed(monkeypatch) -> None:
    """Watch polls until terminal status."""
    fake = FakeRunService()
    monkeypatch.setattr("navbe.cli.actions.get_run_service", lambda: fake)
    runner = CliRunner()

    result = runner.invoke(cli, ["runs", "watch", "r1", "--interval", "0.01"])
    assert result.exit_code == 0
    assert "completed" in result.output.lower()


def test_runs_watch_all_until_idle(monkeypatch) -> None:
    """Watch with no run_id polls all runs until none are active."""
    fake = FakeRunService()
    monkeypatch.setattr("navbe.cli.actions.get_run_service", lambda: fake)
    runner = CliRunner()

    result = runner.invoke(cli, ["runs", "watch", "--interval", "0.01"])
    assert result.exit_code == 0
    assert "r1" in result.output
    assert "completed" in result.output.lower()
