# Contributing to Navbe

Thanks for helping improve Navbe. This guide covers how to propose changes safely.

## Development setup

```bash
git clone https://github.com/leonardoburbanov/navbe_ai.git
cd navbe_ai
uv sync
uv run navbe bootstrap
```

Use `uv run …` inside a checkout so you exercise the working tree.

## Before you open a PR

```bash
uv run ruff check .
uv run ty check src/
uv run lint-imports
uv run pytest
```

## Branching and PRs

1. Create a feature branch from `main` (direct pushes to `main` are blocked).
2. Keep PRs focused — one concern per PR when practical.
3. Fill in the PR template.
4. Wait for the **CI** check to pass.
5. Squash-merge is the default merge style.

## Code guidelines

Authoritative rules for agents and humans live in [`AGENTS.md`](AGENTS.md). Highlights:

- Business logic in domain `service.py` files; keep MCP tools and FastAPI routes thin.
- Type hints on public APIs; docstrings on public functions/classes.
- Do not commit secrets, `.env`, or `navbe_credentials.json`.
- Prefer extending an existing domain over adding a new top-level package.
- Ask before changing MCP tool names or argument shapes.

## Tests

- Prefer fakes at Protocol boundaries — no live production APIs in unit tests.
- Add or update tests when asked / when behavior changes in a non-trivial way.

## Reporting bugs / requesting features

Use the GitHub issue templates. For security issues, see [`SECURITY.md`](SECURITY.md).

## License

By contributing, you agree that your contributions are licensed under the
[Apache License 2.0](LICENSE).
