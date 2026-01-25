from zrb.llm.skill.manager import SkillManager


def create_activate_skill_tool(skill_manager: SkillManager):
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

    activate_skill_impl.__name__ = "activate_skill"
    activate_skill_impl.__doc__ = (
        "Immediately activates a specialized expertise 'skill' to handle complex or domain-specific tasks. "
        "Returns a set of authoritative instructions that YOU MUST follow to complete the task successfully. "
        "Use this as soon as you identify a task that matches an available skill. "
        "\n\n**ARGS:**"
        "\n- `name`: The unique name of the skill to activate."
    )
    return activate_skill_impl
