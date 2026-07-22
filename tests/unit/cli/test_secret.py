"""CLI secret commands."""

from __future__ import annotations

from typer.testing import CliRunner

from navbe.cli.main import cli
from tests.unit.cli.conftest import FakeSecretsService


def test_secret_set_list_has_delete(monkeypatch) -> None:
    """Secret commands never echo values."""
    fake = FakeSecretsService()
    monkeypatch.setattr("navbe.cli.secret.get_secrets_service", lambda: fake)
    monkeypatch.setattr("navbe.cli.actions.get_secrets_service", lambda: fake)
    runner = CliRunner()

    result = runner.invoke(cli, ["secret", "set", "API_KEY"], input="super-secret\n")
    assert result.exit_code == 0
    assert "super-secret" not in result.output
    assert "Stored" in result.output

    result = runner.invoke(cli, ["secret", "list"])
    assert result.exit_code == 0
    assert "API_KEY" in result.output

    result = runner.invoke(cli, ["secret", "has", "API_KEY"])
    assert result.exit_code == 0
    assert "yes" in result.output

    result = runner.invoke(cli, ["secret", "delete", "API_KEY"])
    assert result.exit_code == 0
    assert "Deleted" in result.output

    result = runner.invoke(cli, ["secret", "has", "API_KEY"])
    assert result.exit_code == 0
    assert "no" in result.output
