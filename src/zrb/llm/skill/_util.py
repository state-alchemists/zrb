"""Internal utilities for the skill package.

Holds companion-file discovery and formatting logic shared across
manager.py, tool/skill.py, and skill_command_factory.py.
"""

from pathlib import Path


def discover_companion_files(skill_path: str) -> list[str]:
    """Discover companion files recursively for dedicated-directory skills.

    Only applies when the skill file is named exactly SKILL.md or SKILL.py,
    meaning it has a dedicated directory. Flat ``*.skill.md`` files share
    a directory with other skills so companions are not reported for them.
    """
    skill_file = Path(skill_path)
    if skill_file.name not in ("SKILL.md", "SKILL.py"):
        return []
    skill_dir = skill_file.parent
    if not skill_dir.is_dir():
        return []
    return sorted(
        str(f.relative_to(skill_dir))
        for f in skill_dir.rglob("*")
        if f.is_file() and f.name not in ("SKILL.md", "SKILL.py")
    )


def format_companion_file_lines(companion_files: list[str]) -> list[str]:
    """Format companion file paths into human-readable lines grouped by directory.

    Returns lines ready to be appended to a header block (e.g. ``context_lines``
    or ``header_lines``). Each line is a plain string without trailing newline.

    Returns an empty list when *companion_files* is empty.
    """
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
