"""Rebuild Claude Desktop upload zips with Unix forward-slash paths.

Do not use PowerShell Compress-Archive — it embeds backslashes and Claude
rejects the zip with \"path with invalid characters\".
"""

from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent


def _write_zip(dest: Path, members: list[tuple[Path, str]]) -> None:
    """Write ``dest`` from (source_path, arcname) pairs using POSIX arcnames."""
    if dest.exists():
        dest.unlink()
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for source, arcname in members:
            assert "\\" not in arcname, arcname
            zf.write(source, arcname)


def main() -> None:
    """Build navbe-plugin.zip and navbe-flows-skill.zip."""
    _write_zip(
        ROOT / "navbe-plugin.zip",
        [
            (ROOT / ".claude-plugin" / "plugin.json", ".claude-plugin/plugin.json"),
            (ROOT / ".mcp.json", ".mcp.json"),
            (ROOT / "skills" / "navbe-flows" / "SKILL.md", "skills/navbe-flows/SKILL.md"),
        ],
    )
    _write_zip(
        ROOT / "navbe-flows-skill.zip",
        [
            # Folder name must match YAML ``name: navbe-flows``.
            (ROOT / "skills" / "navbe-flows" / "SKILL.md", "navbe-flows/SKILL.md"),
        ],
    )
    print("Wrote navbe-plugin.zip and navbe-flows-skill.zip")


if __name__ == "__main__":
    main()
