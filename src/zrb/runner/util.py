from ..group.any_group import AnyGroup
from ..task.any_task import AnyTask
from ..util.group import get_all_subtasks


class InvalidCommandError(ValueError):
    pass


def extract_node_from_args(
    root_group: AnyGroup, args: list[str], web_only: bool = False
) -> tuple[AnyGroup | AnyTask, list[str], list[str]]:
    node = root_group
    node_path = []
    residual_args = []
    for index, name in enumerate(args):
        task = node.get_task_by_alias(name)
        if web_only and task is not None and task.cli_only:
            task = None
        group = node.get_group_by_alias(name)
        if group is not None and len(get_all_subtasks(group, web_only)) == 0:
            # If group doesn't contain any task, then ignore its existence
            group = None
        if task is None and group is None:
            raise InvalidCommandError(
                f"Invalid subcommand: {root_group.name} {' '.join(args)}"
            )
        node_path.append(name)
        if group is not None:
            if task is not None and index == len(args) - 1:
                node = task
                residual_args = args[index + 1 :]
                break
            node = group
            continue
        if task is not None:
            node = task
            residual_args = args[index + 1 :]
            break
    return node, node_path, residual_args
