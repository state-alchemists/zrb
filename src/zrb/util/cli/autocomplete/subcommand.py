from ....group.any_group import AnyGroup


class SubCommand():
    def __init__(self, paths: list[str] = [], nexts: list[str] = []):
        self.paths = paths
        self.nexts = nexts

    def __repr__(self):
        return f"<{self.__class__.__name__} paths={self.paths} nexts={self.nexts}>"


def get_group_subcommands(
    group: AnyGroup,
    previous_path: str = [],
    subcommands: list[SubCommand] = []
) -> list[SubCommand]:
    group_name = group.get_name()
    nexts = []
    for task_alias in group.get_sub_tasks():
        nexts.append(task_alias)
    for subgroup_name, subgroup in group.get_sub_groups().items():
        nexts.append(subgroup_name)
        # Recursively add subgroup
        get_group_subcommands(
            group=subgroup,
            previous_path=previous_path + [group_name],
            subcommands=subcommands,
        )
    if len(nexts) > 0:
        subcommands.append(
            SubCommand(
                paths=previous_path + [group_name],
                nexts=nexts
            )
        )
    return subcommands
