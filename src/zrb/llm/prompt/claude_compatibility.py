import os
from typing import Callable

from zrb.llm.skill.manager import SkillManager
from zrb.context.any_context import AnyContext
from zrb.runner.cli import cli
from zrb.util.markdown import make_markdown_section


def create_claude_compatibility_prompt(skill_manager: SkillManager):
    def claude_compatibility(
        ctx: AnyContext,
        current_prompt: str,
        next_handler: Callable[[AnyContext, str], str],
    ) -> str:
        additional_context = []

        # 1. CLAUDE.md
        if os.path.exists("CLAUDE.md"):
            try:
                with open("CLAUDE.md", "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        additional_context.append(
                            make_markdown_section(
                                "Project Instructions (CLAUDE.md)", content
                            )
                        )
            except Exception:
                pass

        # 2. AGENTS.md
        if os.path.exists("AGENTS.md"):
            try:
                with open("AGENTS.md", "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        additional_context.append(
                            make_markdown_section(
                                "Agent Definitions (AGENTS.md)", content
                            )
                        )
            except Exception:
                pass

        # 3. Available Claude Skills
        skills = skill_manager.scan()
        if skills:
            skills_context = []
            skills_context.append(
                "Use 'activate_skill' to load instructions for a skill."
            )
            for skill in skills:
                skills_context.append(f"- {skill.name}")
            additional_context.append(
                make_markdown_section(
                    "Available Skills (Claude Skills)", "\n".join(skills_context)
                )
            )

        new_section = "\n\n".join(additional_context)
        return next_handler(ctx, f"{current_prompt}\n\n{new_section}")

    return claude_compatibility
