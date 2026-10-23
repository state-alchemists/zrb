"""Render a skill as the text the model receives when it activates.

Both activation paths use this: the `ActivateSkill` tool and the slash command
built from the skill. A `preload:` dependency renders first, in its own
`<ACTIVATED_SKILL>` block, so it arrives without a second round trip.
"""

from pathlib import Path

from zrb.llm.skill.manager import Skill
from zrb.llm.skill.util import discover_companion_files, format_companion_file_lines


def skill_body(content: str) -> str:
    """The skill's markdown body, without the YAML frontmatter it may open with.

    Frontmatter is metadata for the loader, not instructions for the model;
    re-sending it wastes tokens and repeats the description as prose. Only a
    line that is exactly `---` closes the block: a quoted YAML value may
    contain that text without ending it.
    """
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return content
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[index + 1 :]).strip()
    return content


def build_activation_block(
    skill: Skill,
    content: str,
    *,
    preloaded_by: str | None = None,
    announce: bool = False,
) -> str:
    """One `<ACTIVATED_SKILL>` block: header, companion list, then the body."""
    skill_dir = str(Path(skill.path).parent)
    companions = skill.companion_files or discover_companion_files(skill.path)
    lines: list[str] = []
    if announce:
        lines.extend(["Skill activated. The following context applies:", ""])
    if preloaded_by:
        lines.extend([f"Preloaded by `{preloaded_by}`.", ""])
    lines.extend(
        [
            f"Skill directory (working directory): {skill_dir}",
            "",
            "All file paths in the skill instructions below are relative to this "
            "directory.",
            "Use companion files (scripts, tools, references) by resolving them "
            "against this path.",
        ]
    )
    lines.extend(format_companion_file_lines(companions))
    lines.extend(["", "---"])
    attrs = f' name="{skill.name}"'
    if preloaded_by:
        attrs += f' preloaded-by="{preloaded_by}"'
    body = skill_body(content)
    return f"<ACTIVATED_SKILL{attrs}>\n" + "\n".join(lines) + f"\n\n{body}\n</ACTIVATED_SKILL>"
