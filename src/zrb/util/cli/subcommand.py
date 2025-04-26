from zrb.group.any_group import AnyGroup
from zrb.util.group import get_non_empty_subgroups, get_subtasks


class SubCommand:
    def __init__(self, paths: list[str] = [], nexts: list[str] = []):
        """
        Initialize a SubCommand object.

        Args:
            paths (list[str]): The list of path components leading to this subcommand.
            nexts (list[str]): The list of possible next subcommand or task names.
        """
        self.paths = paths
        self.nexts = nexts

    def __repr__(self):
        """
        Return a string representation of the SubCommand object.
        """
        return f"<{self.__class__.__name__} paths={self.paths} nexts={self.nexts}>"


def get_group_subcommands(
    group: AnyGroup, previous_path: list[str] = [], subcommands: list[SubCommand] = []
) -> list[SubCommand]:
    """
    Recursively get all possible subcommands within a group hierarchy.

    Args:
        group (AnyGroup): The current group to process.
        previous_path (list[str]): The path leading to the current group.
        subcommands (list[SubCommand]): The list to accumulate subcommands.

    Returns:
        list[SubCommand]: A list of all discovered subcommands.
    """
    nexts = []
    for task_alias in get_subtasks(group):
        nexts.append(task_alias)
    for subgroup_alias, subgroup in get_non_empty_subgroups(group).items():
        nexts.append(subgroup_alias)
        # Recursively add subgroup
        get_group_subcommands(
            group=subgroup,
            previous_path=previous_path + [group.name],
            subcommands=subcommands,
        )
    if len(nexts) > 0:
        subcommands.append(SubCommand(paths=previous_path + [group.name], nexts=nexts))
    return subcommands
