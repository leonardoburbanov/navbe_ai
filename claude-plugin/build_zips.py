"""Rebuild Claude upload packages with Unix forward-slash zip paths.

Do not use PowerShell Compress-Archive — it embeds backslashes and Claude
rejects the zip with \"path with invalid characters\".

Produces:
- navbe-plugin.zip / navbe.plugin — Customize → Plugins (skill + .mcp.json)
- navbe.mcpb — Desktop Extensions (Settings → Extensions; may require .mcpb)
- navbe-flows-skill.zip — skill-only upload
"""

import shutil
import zipfile
from pathlib import Path

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
    """Build plugin, mcpb, and skill packages."""
    plugin_members = [
        (ROOT / ".claude-plugin" / "plugin.json", ".claude-plugin/plugin.json"),
        (ROOT / ".mcp.json", ".mcp.json"),
        (ROOT / "skills" / "navbe-flows" / "SKILL.md", "skills/navbe-flows/SKILL.md"),
    ]
    _write_zip(ROOT / "navbe-plugin.zip", plugin_members)
    # Same bytes, extension Claude's Plugins UI also accepts.
    shutil.copyfile(ROOT / "navbe-plugin.zip", ROOT / "navbe.plugin")

    _write_zip(
        ROOT / "navbe.mcpb",
        [
            (ROOT / "manifest.json", "manifest.json"),
            (ROOT / "run.cmd", "run.cmd"),
        ],
    )
    _write_zip(
        ROOT / "navbe-flows-skill.zip",
        [
            (ROOT / "skills" / "navbe-flows" / "SKILL.md", "navbe-flows/SKILL.md"),
        ],
    )
    print(
        "Wrote navbe-plugin.zip, navbe.plugin, navbe.mcpb, "
        "and navbe-flows-skill.zip"
    )


if __name__ == "__main__":
    main()
