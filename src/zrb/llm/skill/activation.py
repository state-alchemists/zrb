"""Render a skill as the text the model receives when it activates.

Both activation paths use this: the `ActivateSkill` tool and the slash command
built from the skill. A `preload:` dependency renders first, in its own
`<ACTIVATED_SKILL>` block, so it arrives without a second round trip.
"""

from html import escape
from pathlib import Path

from zrb.llm.skill.manager import Skill
from zrb.llm.skill.util import discover_companion_files, format_companion_file_lines

_DELIMITERS = ("<ACTIVATED_SKILL", "</ACTIVATED_SKILL>")


def _neutralize_delimiters(body: str) -> str:
    """Stop a body from faking the tag that wraps it.

    The body is model-authored and rendered inside `<ACTIVATED_SKILL>`; a skill
    documenting this markup would otherwise close or reopen the block it lives
    in — for the model reading it, and for the reader that re-attaches the block
    after compaction. Only the tag literals change, so markdown and code fences
    stay exactly as written.
    """
    for delimiter in _DELIMITERS:
        body = body.replace(delimiter, delimiter.replace("<", "&lt;"))
    return body


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
        # Also escaped here: the body is model-visible markup, and an
        # unescaped `<...>` would read as a tag.
        lines.extend([f"Preloaded by `{escape(preloaded_by)}`.", ""])
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
    # A name comes from project frontmatter, so it is untrusted in the XML
    # attribute: an unescaped quote would close the tag and inject markup.
    attrs = f' name="{escape(skill.name, quote=True)}"'
    if preloaded_by:
        attrs += f' preloaded-by="{escape(preloaded_by, quote=True)}"'
    body = _neutralize_delimiters(skill_body(content))
    return (
        f"<ACTIVATED_SKILL{attrs}>\n"
        + "\n".join(lines)
        + f"\n\n{body}\n</ACTIVATED_SKILL>"
    )
