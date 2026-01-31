from typing import Callable

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.runner.cli import cli
from zrb.util.markdown import make_markdown_section


def create_zrb_skills_prompt():
    def zrb_prompt(
        ctx: AnyContext,
        current_prompt: str,
        next_handler: Callable[[AnyContext, str], str],
    ) -> str:
        additional_context = []
        # Available Zrb Workflows (Skills)
        zrb_cmd = CFG.ROOT_GROUP_NAME
        zrb_context = []

        # List top-level groups
        if cli.subgroups:
            zrb_context.append(f"Groups (Use 'list_{zrb_cmd}_tasks' to see details):")
            for alias, grp in cli.subgroups.items():
                zrb_context.append(f"- {alias}: {grp.description}")

        # List top-level tasks
        if cli.subtasks:
            zrb_context.append("Tasks:")
            for alias, task in cli.subtasks.items():
                zrb_context.append(f"- {alias}: {task.description}")

        additional_context.append(
            make_markdown_section(
                f"Available Skills ({zrb_cmd} Workflows)", "\n".join(zrb_context)
            )
        )

        new_section = "\n\n".join(additional_context)
        return next_handler(ctx, f"{current_prompt}\n\n{new_section}")

    return zrb_prompt
