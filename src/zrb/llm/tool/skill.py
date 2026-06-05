from pathlib import Path

from zrb.llm.skill.manager import SkillManager
from zrb.llm.skill.manager import skill_manager as default_skill_manager
from zrb.llm.skill.util import discover_companion_files, format_companion_file_lines


def create_activate_skill_tool(skill_manager: SkillManager | None = None):
    if skill_manager is None:
        skill_manager = default_skill_manager

    async def activate_skill_impl(name: str) -> str:
        skill = skill_manager.get_skill(name)

        if not skill:
            return f"Skill '{name}' not found."

        if not skill.model_invocable:
            return f"Skill '{name}' is not invocable by the model."

        content = skill_manager.get_skill_content(name)
        if not content:
            return f"Skill '{name}' not found."

        skill_dir = str(Path(skill.path).parent)
        companion_files = skill.companion_files or discover_companion_files(skill.path)

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
    activate_skill_impl.__doc__ = (
        "Activates specialized expertise from a skill.\n\n"
        "Returns the skill's full content, its directory path, and a listing of any\n"
        "companion files (scripts, docs, data). Use Read/Glob on the directory to\n"
        "access companion files referenced in the skill content."
    )
    return activate_skill_impl
