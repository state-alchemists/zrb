from pathlib import Path

from zrb.llm.skill.manager import SkillManager
from zrb.llm.skill.manager import skill_manager as default_skill_manager


def _get_companion_files(skill_path: str) -> list[str]:
    """Return companion files for skills that live in their own directory.

    Only applies when the skill file is named exactly SKILL.md or SKILL.py,
    meaning it has a dedicated directory. Flat *.skill.md files share a directory
    with other skills so companions are not reported for them.
    """
    skill_file = Path(skill_path)
    if skill_file.name not in ("SKILL.md", "SKILL.py"):
        return []
    skill_dir = skill_file.parent
    if not skill_dir.is_dir():
        return []
    return sorted(
        str(f)
        for f in skill_dir.iterdir()
        if f.is_file() and f.name not in ("SKILL.md", "SKILL.py")
    )


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
        companion_files = _get_companion_files(skill.path)

        header_lines = [f"Skill directory: {skill_dir}"]
        if companion_files:
            header_lines.append("Companion files:")
            for f in companion_files:
                header_lines.append(f"  - {f}")
        else:
            header_lines.append("Companion files: none")

        header = "\n".join(header_lines)
        return f"<ACTIVATED_SKILL>\n{header}\n\n{content}\n</ACTIVATED_SKILL>"

    activate_skill_impl.__name__ = "ActivateSkill"
    activate_skill_impl.__doc__ = (
        "Activates specialized expertise from a skill.\n\n"
        "Returns the skill's full content, its directory path, and a listing of any\n"
        "companion files (scripts, docs, data). Use Read/Glob on the directory to\n"
        "access companion files referenced in the skill content.\n\n"
        "MANDATES:\n"
        "- Use when task matches a skill's domain.\n"
        "- Re-activate if conversation gets long and you lose context."
    )
    return activate_skill_impl
