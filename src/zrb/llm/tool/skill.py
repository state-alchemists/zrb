from pathlib import Path

from zrb.llm.skill.manager import SkillManager
from zrb.llm.skill.manager import skill_manager as default_skill_manager
from zrb.llm.skill.util import discover_companion_files, format_companion_file_lines


def create_activate_skill_tool(skill_manager: SkillManager | None = None):
    if skill_manager is None:
        skill_manager = default_skill_manager

    async def activate_skill_impl(skill: str) -> str:
        found = skill_manager.get_skill(skill)

        if not found:
            return _skill_not_found_message(skill, skill_manager)

        if not found.model_invocable:
            return (
                f"Skill '{skill}' is not invocable by the model. "
                "[SYSTEM SUGGESTION]: it is a user-facing command, not an "
                "agent skill — carry out the work yourself. "
                + _available_skills_hint(skill_manager)
            )

        content = skill_manager.get_skill_content(skill)
        if not content:
            return _skill_not_found_message(skill, skill_manager)

        skill_dir = str(Path(found.path).parent)
        companion_files = found.companion_files or discover_companion_files(found.path)

        header_lines = [
            "Skill activated. The following context applies:",
            "",
            f"Skill directory (working directory): {skill_dir}",
            "",
            "All file paths in the skill instructions below are relative to this directory.",
            "Use companion files (scripts, tools, references) by resolving them against this path.",
        ]
        header_lines.extend(format_companion_file_lines(companion_files))
        header_lines.append("")
        header_lines.append("---")

        header = "\n".join(header_lines)
        return f"<ACTIVATED_SKILL>\n{header}\n\n{content}\n</ACTIVATED_SKILL>"

    activate_skill_impl.__name__ = "ActivateSkill"
    # The roster is deliberately NOT embedded here: unlike DelegateToAgent's
    # agent list, it is already spelled out in the prompt's skill catalogue, and
    # duplicating it would pay for the same names twice on every request. The
    # docstring must not point *at* that catalogue either — sections toggle
    # independently, so a pointer dangles the moment one is trimmed. An unknown
    # name therefore resolves itself: the error lists the valid ones.
    activate_skill_impl.__doc__ = (
        "Activates specialized expertise from a skill.\n\n"
        "Returns the skill's full content, its directory path, and a listing of any\n"
        "companion files (scripts, docs, data). Use Read/Glob on the directory to\n"
        "access companion files referenced in the skill content.\n\n"
        "skill: an exact skill name, e.g. 'core-coding'. A name that does not\n"
        "resolve comes back with the valid ones listed — do not guess twice."
    )
    return activate_skill_impl


def _available_skills_hint(skill_manager: SkillManager) -> str:
    """The valid `skill` values, for an error the model has to recover from."""
    names = sorted(s.name for s in skill_manager.get_skills() if s.model_invocable)
    if not names:
        return "No activatable skills are registered."
    return f"Activatable skills are: {', '.join(names)}."


def _skill_not_found_message(skill: str, skill_manager: SkillManager) -> str:
    """Name the valid skills rather than telling the model to look them up.

    Mirrors ``agent_not_found_message`` for delegation: the usual failure is a
    misremembered name, so listing the real ones turns the retry into a
    correction instead of another guess.
    """
    return (
        f"Skill '{skill}' not found. [SYSTEM SUGGESTION]: "
        + _available_skills_hint(skill_manager)
    )
