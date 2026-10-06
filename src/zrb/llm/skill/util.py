"""Companion-file discovery and formatting for skills."""

from pathlib import Path


def discover_companion_files(skill_path: str) -> list[str]:
    """Discover companion files recursively for dedicated-directory skills.

    Only for ``SKILL.md``/``SKILL.py``; flat ``*.skill.md`` files share a directory.
    """
    skill_file = Path(skill_path)
    if skill_file.name not in ("SKILL.md", "SKILL.py"):
        return []
    skill_dir = skill_file.parent
    if not skill_dir.is_dir():
        return []
    return sorted(
        f.relative_to(skill_dir).as_posix()
        for f in skill_dir.rglob("*")
        if f.is_file() and f.name not in ("SKILL.md", "SKILL.py")
    )


def format_companion_file_lines(companion_files: list[str]) -> list[str]:
    """Format companion file paths into lines grouped by directory (empty for none)."""
    if not companion_files:
        return []
    groups: dict[str, list[str]] = {}
    standalone: list[str] = []
    for f in companion_files:
        parts = f.split("/")
        if len(parts) > 1:
            group = parts[0]
            groups.setdefault(group, []).append(f)
        else:
            standalone.append(f)
    lines = [""]
    lines.append("Companion files available in this directory:")
    for f in sorted(standalone):
        lines.append(f"  {f}")
    for group in sorted(groups):
        lines.append(f"  {group}/")
        for f in sorted(groups[group]):
            lines.append(f"    {f.split('/', 1)[1]}")
    return lines
