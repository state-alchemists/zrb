from ..task.any_task import AnyTask
from ..group.any_group import AnyGroup


class InvalidCommandError(ValueError):
    pass


def extract_node_from_args(
    root_group: AnyGroup, args: list[str]
) -> tuple[AnyGroup | AnyTask, list[str], list[str]]:
    node = root_group
    node_path = []
    residual_args = []
    for index, name in enumerate(args):
        task = node.get_task_by_alias(name)
        group = node.get_group_by_alias(name)
        if group is not None and not group.contain_tasks:
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
                residual_args = args[index+1:]
                break
            node = group
            continue
        if task is not None:
            node = task
            residual_args = args[index+1:]
            break
    return node, node_path, residual_args


def extract_node_from_url(root_group: AnyGroup, url: str) -> tuple[AnyGroup | AnyTask, str]:
    stripped_url = url.strip("/")
    args = stripped_url.split("/")
    try:
        node, node_path, _ = extract_node_from_args(root_group, args)
        url = "/" + "/".join(node_path)
        return node, url
    except InvalidCommandError:
        return None, url
