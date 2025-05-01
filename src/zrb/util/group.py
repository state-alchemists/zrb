from zrb.group.any_group import AnyGroup
from zrb.task.any_task import AnyTask


class NodeNotFoundError(ValueError):
    pass


def extract_node_from_args(
    root_group: AnyGroup, args: list[str], web_only: bool = False
) -> tuple[AnyGroup | AnyTask, list[str], list[str]]:
    """
    Extract a node (Group or Task) from a list of command-line arguments.

    Args:
        root_group (AnyGroup): The root group to start the search from.
        args (list[str]): The list of command-line arguments.
        web_only (bool): If True, only consider tasks that are not CLI-only.

    Returns:
        tuple[AnyGroup | AnyTask, list[str], list[str]]: A tuple containing the
            extracted node, the path to the node, and any residual arguments.

    Raises:
        NodeNotFoundError: If no matching task or group is found for a given argument.
    """
    node = root_group
    node_path = []
    residual_args = []
    for index, name in enumerate(args):
        task = node.get_task_by_alias(name)
        if web_only and task is not None and task.cli_only:
            task = None
        group = node.get_group_by_alias(name)
        # Only ignore empty groups if web_only is True
        if (
            group is not None
            and web_only
            and len(get_all_subtasks(group, web_only)) == 0
        ):
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


def get_node_path(group: AnyGroup, node: AnyGroup | AnyTask) -> list[str] | None:
    """
    Get the path (aliases) to a specific node within a group hierarchy.

    Args:
        group (AnyGroup): The group to search within.
        node (AnyGroup | AnyTask): The target node.

    Returns:
        list[str] | None: A list of aliases representing the path to the node,
            or None if the node is not found.
    """
    if group is None:
        return []
    if group == node:  # Handle the case where the target is the starting group
        return [group.name]
    if isinstance(node, AnyTask):
        for alias, subtask in group.subtasks.items():
            if subtask == node:
                return [alias]
    if isinstance(node, AnyGroup):
        for alias, subgroup in group.subgroups.items():
            if subgroup == node:
                return [alias]
    for alias, subgroup in group.subgroups.items():
        result = get_node_path(subgroup, node)
        if result is not None:
            return [alias] + result
    return None


def get_non_empty_subgroups(
    group: AnyGroup, web_only: bool = False
) -> dict[str, AnyGroup]:
    """
    Get subgroups that contain at least one task.

    Args:
        group (AnyGroup): The group to search within.
        web_only (bool): If True, only consider tasks that are not CLI-only.

    Returns:
        dict[str, AnyGroup]: A dictionary of subgroups that are not empty.
    """
    return {
        alias: subgroup
        for alias, subgroup in group.subgroups.items()
        if len(get_all_subtasks(subgroup, web_only)) > 0
    }


def get_subtasks(group: AnyGroup, web_only: bool = False) -> dict[str, AnyTask]:
    """
    Get the direct subtasks of a group.

    Args:
        group (AnyGroup): The group to search within.
        web_only (bool): If True, only include tasks that are not CLI-only.

    Returns:
        dict[str, AnyTask]: A dictionary of subtasks.
    """
    return {
        alias: subtask
        for alias, subtask in group.subtasks.items()
        if not web_only or (web_only and not subtask.cli_only)
    }


def get_all_subtasks(group: AnyGroup, web_only: bool = False) -> list[AnyTask]:
    """
    Get all subtasks (including nested ones) within a group hierarchy.

    Args:
        group (AnyGroup): The group to search within.
        web_only (bool): If True, only include tasks that are not CLI-only.

    Returns:
        list[AnyTask]: A list of all subtasks.
    """
    subtasks = [
        subtask
        for subtask in group.subtasks.values()
        if not web_only or (web_only and not subtask.cli_only)
    ]
    for subgroup in group.subgroups.values():
        subtasks += get_all_subtasks(subgroup, web_only)
    return subtasks
