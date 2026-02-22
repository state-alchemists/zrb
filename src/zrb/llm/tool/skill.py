from zrb.llm.skill.manager import (
    SkillManager,
)
from zrb.llm.skill.manager import skill_manager as default_skill_manager


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
        if content:
            return f"<ACTIVATED_SKILL>\n{content}\n</ACTIVATED_SKILL>"
        return f"Skill '{name}' not found."

    activate_skill_impl.__name__ = "ActivateSkill"
    activate_skill_impl.__doc__ = (
        "Activates specialized expertise 'skill' instructions.\n\n"
        "MANDATES:\n"
        "- MUST follow the returned instructions strictly.\n"
        "- ALWAYS use as soon as a task matches an available skill."
    )
    return activate_skill_impl
