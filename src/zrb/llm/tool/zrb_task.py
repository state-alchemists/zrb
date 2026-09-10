import shlex
from typing import Annotated

from pydantic import Field

from zrb.config.config import CFG
from zrb.llm.tool.shell import run_shell_command
from zrb.runner.cli import cli


def create_list_zrb_task_tool():  # noqa: C901 -- registration/factory fn; mccabe sums nested handlers into this line, radon scores each separately (near-trivial on its own)
    def list_zrb_tasks_impl(
        group_name: Annotated[
            str,
            Field(
                description=(
                    "Space-separated group path to list, e.g. 'foo bar'; omit "
                    "to list the root group's tasks and subgroups."
                )
            ),
        ] = "",
    ) -> str:
        target_group = cli
        if group_name:
            parts = group_name.split()
            for part in parts:
                next_group = target_group.get_group_by_alias(part)
                if not next_group:
                    return (
                        f"Error: Group '{part}' not found in '{group_name}'. "
                        "[SYSTEM SUGGESTION]: List available groups first (call "
                        "this tool with an empty group_name) to discover valid "
                        "group aliases, then retry."
                    )
                target_group = next_group
        output = [f"Tasks in '{target_group.name}':"]
        if target_group.subgroups:
            output.append("\n  Groups:")
            for alias, grp in target_group.subgroups.items():
                output.append(f"    - {alias}: {grp.description}")
        if target_group.subtasks:
            output.append("\n  Tasks:")
            for alias, task in target_group.subtasks.items():
                output.append(f"    - {alias}: {task.description}")
        return "\n".join(output)

    zrb_cmd = CFG.ROOT_GROUP_NAME
    list_zrb_tasks_impl.__name__ = f"List{zrb_cmd.capitalize()}Tasks"
    list_zrb_tasks_impl.__doc__ = f"Lists available {zrb_cmd} groups and tasks. Use to discover automation capabilities before running them."
    return list_zrb_tasks_impl


def create_run_zrb_task_tool():
    async def run_zrb_task(
        task_name: Annotated[
            str,
            Field(description="Space-separated task path to run, e.g. 'foo bar-task'."),
        ],
        # Mutable default is intentional: pydantic-ai converts it to
        # default_factory internally, so each LLM call gets a fresh dict.
        # Using `= {}` instead of `dict[str, str] | None` keeps the JSON
        # schema compact (no anyOf + null bloat in the LLM tool description).
        args: Annotated[
            dict[str, str],
            Field(
                description=(
                    "Task arguments as {flag_name: value}; each becomes "
                    "`--flag_name value` on the command line."
                )
            ),
        ] = {},  # noqa: B006
        timeout: Annotated[
            int,
            Field(
                description="Seconds to wait for the task to finish before timing out."
            ),
        ] = 30,
    ) -> str:
        """Run an automation task by name with optional --key value args."""
        # Construct command, quoting every part so values containing spaces
        # or shell metacharacters cannot be word-split or injected.
        zrb_cmd = CFG.ROOT_GROUP_NAME
        cmd_parts = [zrb_cmd] + task_name.split()

        for key, val in args.items():
            cmd_parts.append(f"--{key}")
            cmd_parts.append(str(val))

        command = " ".join(shlex.quote(part) for part in cmd_parts)
        return await run_shell_command(command, timeout=timeout)

    zrb_cmd = CFG.ROOT_GROUP_NAME
    run_zrb_task.__name__ = f"Run{zrb_cmd.capitalize()}Task"
    run_zrb_task.__doc__ = (
        f"Executes a {zrb_cmd} automation task by name. Provide all required args."
    )
    return run_zrb_task
