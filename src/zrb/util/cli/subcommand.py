from ...group.any_group import AnyGroup


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
    nexts = []
    for task_alias in group.subtasks:
        nexts.append(task_alias)
    for subgroup_alias, subgroup in group.subgroups.items():
        if not subgroup.contain_tasks:
            continue
        nexts.append(subgroup_alias)
        # Recursively add subgroup
        get_group_subcommands(
            group=subgroup,
            previous_path=previous_path + [group.name],
            subcommands=subcommands,
        )
    if len(nexts) > 0:
        subcommands.append(
            SubCommand(
                paths=previous_path + [group.name],
                nexts=nexts
            )
        )
    return subcommands
