"""Interactive picker for GitHub repos the Navbe AI app can access."""

from __future__ import annotations

import typer
from rich.table import Table

from navbe.cli.format import console
from navbe.domains.sync.github_auth import GitHubRepoRef


def pick_accessible_repo(
    repos: list[GitHubRepoRef],
    *,
    default_login: str | None = None,
) -> tuple[str, str, bool]:
    """Prompt the user to pick a granted repo or type owner/name manually.

    Returns ``(owner, name, private)``. ``private`` only matters when creating.
    """
    if repos:
        table = Table(title="Repos Navbe AI can access")
        table.add_column("#", style="cyan", justify="right")
        table.add_column("repository")
        table.add_column("visibility")
        for index, repo in enumerate(repos, start=1):
            table.add_row(
                str(index),
                repo.full_name,
                "private" if repo.private else "public",
            )
        console.print(table)
        console.print("  [cyan]0[/cyan]  Type owner/name (create if missing)")
        console.print()

        while True:
            raw = typer.prompt("Choose a repo number", default="1")
            try:
                choice = int(raw.strip())
            except ValueError:
                console.print("[red]Enter a number from the list.[/red]")
                continue
            if choice == 0:
                break
            if 1 <= choice <= len(repos):
                selected = repos[choice - 1]
                return selected.owner, selected.name, selected.private
            console.print(f"[red]Pick 0–{len(repos)}.[/red]")
    else:
        console.print(
            "[yellow]No repos granted to Navbe AI yet.[/yellow]\n"
            "Add repository access on the app installation, or create a new one below."
        )
        console.print()

    owner_default = default_login or ""
    owner = typer.prompt("GitHub owner (user or org)", default=owner_default or None)
    name = typer.prompt("Repository name", default="navbe-workspace")
    private = typer.confirm("Private repo if creating?", default=True)
    return owner.strip(), name.strip(), private
