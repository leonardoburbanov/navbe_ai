"""CLI steps commands."""

from __future__ import annotations

from typer.testing import CliRunner

from navbe.cli.main import cli
from tests.unit.cli.conftest import FakeCatalogService


def test_steps_list_and_show(monkeypatch) -> None:
    """Steps list/show use CatalogService."""
    fake = FakeCatalogService()
    monkeypatch.setattr("navbe.cli.steps.get_catalog_service", lambda: fake)
    monkeypatch.setattr("navbe.cli.actions.get_catalog_service", lambda: fake)
    runner = CliRunner()

    result = runner.invoke(cli, ["steps"])
    assert result.exit_code == 0
    assert "set_var" in result.output

    result = runner.invoke(cli, ["steps", "show", "set_var"])
    assert result.exit_code == 0
    assert "Extract a value" in result.output


def test_steps_show_unknown(monkeypatch) -> None:
    """Unknown step type exits with error."""
    fake = FakeCatalogService()
    monkeypatch.setattr("navbe.cli.steps.get_catalog_service", lambda: fake)
    monkeypatch.setattr("navbe.cli.actions.get_catalog_service", lambda: fake)
    runner = CliRunner()

    result = runner.invoke(cli, ["steps", "show", "nope"])
    assert result.exit_code == 1
    assert "not_found" in result.output.lower() or "Unknown" in result.output
