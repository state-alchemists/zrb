from zrb.builtin.pollux.tool.bash import run_shell_command
from zrb.runner.cli import cli


def list_zrb_tasks(group_name: str | None = None) -> str:
    """
    Lists available Zrb tasks and groups.
    If group_name is provided, lists tasks under that group.
    """
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


async def run_zrb_task(task_name: str, args: dict[str, str] = {}) -> str:
    """
    Executes a Zrb task.

    Args:
        task_name: The full name/alias path of the task (e.g., "server start").
        args: Dictionary of arguments to pass to the task (e.g., {"port": "8080"}).
    """
    # Construct command
    cmd_parts = ["zrb"] + task_name.split()

    for key, val in args.items():
        cmd_parts.append(f"--{key}")
        cmd_parts.append(str(val))

    command = " ".join(cmd_parts)
    return await run_shell_command(command)
