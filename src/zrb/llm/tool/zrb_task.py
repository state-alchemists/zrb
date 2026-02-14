from zrb.config.config import CFG
from zrb.llm.tool.bash import run_shell_command
from zrb.runner.cli import cli


def create_list_zrb_task_tool():
    def list_zrb_tasks_impl(group_name: str | None = None) -> str:
        target_group = cli
        if group_name:
            parts = group_name.split()
            for part in parts:
                next_group = target_group.get_group_by_alias(part)
                if not next_group:
                    return f"Error: Group '{part}' not found in '{group_name}'."
                target_group = next_group
        output = [f"Tasks in '{target_group.name}':"]
        # Subgroups
        if target_group.subgroups:
            output.append("\n  Groups:")
            for alias, grp in target_group.subgroups.items():
                output.append(f"    - {alias}: {grp.description}")
        # Tasks
        if target_group.subtasks:
            output.append("\n  Tasks:")
            for alias, task in target_group.subtasks.items():
                output.append(f"    - {alias}: {task.description}")
        return "\n".join(output)

    zrb_cmd = CFG.ROOT_GROUP_NAME
    list_zrb_tasks_impl.__name__ = f"List{zrb_cmd.capitalize()}Tasks"
    list_zrb_tasks_impl.__doc__ = (
        f"Discovery tool to see available {zrb_cmd} capabilities"
        "\n\n**OPERATIONAL MANDATE:**"
        f"\n- You SHOULD ALWAYS check this to see available {zrb_cmd} capabilities."
        "\n\n**ARGS:**"
        "\n- `group_name`: Optional group to browse (e.g., 'server')."
    )
    return list_zrb_tasks_impl


def create_run_zrb_task_tool():
    async def run_zrb_task(
        task_name: str, args: dict[str, str] = {}, timeout: int = 30
    ) -> str:
        """ """
        # Construct command
        cmd_parts = ["zrb"] + task_name.split()

        for key, val in args.items():
            cmd_parts.append(f"--{key}")
            cmd_parts.append(str(val))

        command = " ".join(cmd_parts)
        return await run_shell_command(command, timeout=timeout)

    zrb_cmd = CFG.ROOT_GROUP_NAME
    run_zrb_task.__name__ = f"Run{zrb_cmd.capitalize()}Task"
    run_zrb_task.__doc__ = (
        f"Executes a predefined {zrb_cmd} automation task. "
        "\n\n**OPERATIONAL MANDATE:**"
        f"\n- This is the PREFERRED way to run {zrb_cmd} automation tasks."
        "\n- You MUST provide all required arguments."
        "\n\n**ARGS:**"
        "\n- `task_name`: The full alias path (e.g., 'server start')."
        "\n- `args`: Dictionary of arguments (e.g., {'port': '8080'})."
        "\n- `timeout`: Max wait time in seconds (default 30)."
    )
    return run_zrb_task
