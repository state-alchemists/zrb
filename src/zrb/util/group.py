from ..group.any_group import AnyGroup
from ..task.any_task import AnyTask


class NodeNotFoundError(ValueError):
    pass


def extract_node_from_url(
    root_group: AnyGroup, url: str
) -> tuple[AnyGroup | AnyTask, str]:
    stripped_url = url.strip("/")
    args = stripped_url.split("/")
    try:
        node, node_path, residual_args = extract_node_from_args(
            root_group, args, web_only=True
        )
        url = "/" + "/".join(node_path)
        return node, url, residual_args
    except NodeNotFoundError:
        return None, url, []


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
            raise NodeNotFoundError(
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


def get_non_empty_subgroups(
    group: AnyGroup, web_only: bool = False
) -> dict[str, AnyGroup]:
    return {
        alias: subgroup
        for alias, subgroup in group.subgroups.items()
        if len(get_all_subtasks(subgroup, web_only)) > 0
    }


def get_subtasks(group: AnyGroup, web_only: bool = False) -> dict[str, AnyTask]:
    return {
        alias: subtask
        for alias, subtask in group.subtasks.items()
        if not web_only or (web_only and not subtask.cli_only)
    }


def get_all_subtasks(group: AnyGroup, web_only: bool = False) -> list[AnyTask]:
    subtasks = [
        subtask
        for subtask in group.subtasks.values()
        if not web_only or (web_only and not subtask.cli_only)
    ]
    for subgroup in group.subgroups.values():
        subtasks += get_all_subtasks(subgroup, web_only)
    return subtasks
