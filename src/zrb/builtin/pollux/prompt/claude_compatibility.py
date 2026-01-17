import os
from typing import Callable

from zrb.builtin.pollux.skill.manager import SkillManager
from zrb.context.any_context import AnyContext
from zrb.runner.cli import cli


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
                            f"# Project Instructions (CLAUDE.md)\n{content}"
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
                            f"# Agent Definitions (AGENTS.md)\n{content}"
                        )
            except Exception:
                pass

        # 3. Available Claude Skills
        skills = skill_manager.scan()
        if skills:
            skills_context = ["# Available Skills (Claude Skills)"]
            skills_context.append(
                "Use 'activate_skill' to load instructions for a skill."
            )
            for skill in skills:
                skills_context.append(f"- {skill.name}")
            additional_context.append("\n".join(skills_context))

        # 4. Available Zrb Workflows (Skills)
        zrb_context = ["# Available Skills (Zrb Workflows)"]

        # List top-level groups
        if cli.subgroups:
            zrb_context.append("Groups (Use 'list_zrb_tasks' to see details):")
            for alias, grp in cli.subgroups.items():
                zrb_context.append(f"- {alias}: {grp.description}")

        # List top-level tasks
        if cli.subtasks:
            zrb_context.append("Tasks:")
            for alias, task in cli.subtasks.items():
                zrb_context.append(f"- {alias}: {task.description}")

        additional_context.append("\n".join(zrb_context))

        new_section = "\n\n".join(additional_context)
        return next_handler(ctx, f"{current_prompt}\n\n{new_section}")

    return claude_compatibility
