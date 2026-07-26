"""CLI root and serve."""

from typer.testing import CliRunner

from navbe.cli.main import cli


def test_navbe_help_lists_command_groups() -> None:
    """Root help exposes human command groups."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "setup" in result.output
    assert "bootstrap" in result.output
    assert "info" in result.output
    assert "login" in result.output
    assert "secret" in result.output
    assert "sync" in result.output
    assert "flows" in result.output
    assert "runs" in result.output
    assert "steps" in result.output
    assert "serve" in result.output
    assert "status" in result.output
    assert "stop" in result.output
    assert "interactive" in result.output.lower() or "slash" in result.output.lower()


def test_bare_navbe_non_tty_prints_quick_start(monkeypatch) -> None:
    """Piped / non-TTY stdin keeps banner + quick start (no REPL hang)."""
    monkeypatch.setattr("navbe.cli.main.should_start_interactive", lambda: False)
    runner = CliRunner()
    result = runner.invoke(cli, [])
    assert result.exit_code == 0
    assert "navbe bootstrap" in result.output.lower() or "Quick start" in result.output


def test_bare_navbe_tty_runs_slash_session(monkeypatch) -> None:
    """TTY stdin enters interactive session; /help then /exit."""
    monkeypatch.setattr("navbe.cli.main.should_start_interactive", lambda: True)
    runner = CliRunner()
    result = runner.invoke(cli, [], input="/help\n/exit\n")
    assert result.exit_code == 0
    assert "Navbe" in result.output or "Welcome" in result.output
    assert (
        "/help" in result.output
        or "Slash commands" in result.output
        or "/flows" in result.output
    )


def test_serve_help() -> None:
    """Serve subcommand documents host/port."""
    runner = CliRunner()
    result = runner.invoke(cli, ["serve", "--help"])
    assert result.exit_code == 0
    assert "--host" in result.output
    assert "--port" in result.output
