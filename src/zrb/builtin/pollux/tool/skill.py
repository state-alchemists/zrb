from pydantic_ai import Tool

from zrb.builtin.pollux.skill.manager import SkillManager


def create_activate_skill_tool(skill_manager: SkillManager):
    async def activate_skill_impl(name: str) -> str:
        """
        Activates a specialized agent skill by name.
        Returns the skill's instructions wrapped in <ACTIVATED_SKILL> tags.
        These provide specialized guidance for the current task.
        Use this when you identify a task that matches a skill's description.
        """
        content = skill_manager.get_skill_content(name)
        if content:
            return f"<ACTIVATED_SKILL>\n{content}\n</ACTIVATED_SKILL>"
        return f"Skill '{name}' not found."

    activate_skill = Tool(
        activate_skill_impl,
        name="activate_skill",
        description=(
            "Activates a specialized agent skill by name. "
            "Returns the skill's instructions wrapped in <ACTIVATED_SKILL> tags. "
            "These provide specialized guidance for the current task. "
            "Use this when you identify a task that matches a skill's description."
        ),
    )
    return activate_skill
