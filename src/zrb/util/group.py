from ..task.any_task import AnyTask
from ..group.any_group import AnyGroup


def get_non_empty_subgroups(group: AnyGroup, web_only: bool = False) -> dict[str, AnyGroup]:
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
