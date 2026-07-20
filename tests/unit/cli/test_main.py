"""CLI root and serve."""

from click.testing import CliRunner

from navbe.cli.main import cli


def test_navbe_help_lists_command_groups() -> None:
    """Root help exposes human command groups."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "secret" in result.output
    assert "sync" in result.output
    assert "runs" in result.output
    assert "steps" in result.output
    assert "serve" in result.output


def test_serve_help() -> None:
    """Serve subcommand documents host/port."""
    runner = CliRunner()
    result = runner.invoke(cli, ["serve", "--help"])
    assert result.exit_code == 0
    assert "--host" in result.output
    assert "--port" in result.output
