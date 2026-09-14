from zrb.group.any_group import AnyGroup


class SubCommand:
    def __init__(
        self,
        paths: list[str] | None = None,
        nexts: list[str] | None = None,
    ):
        """`paths`: the group path leading here. `nexts`: the task/subgroup
        names reachable directly from it."""
        self.paths = paths if paths is not None else []
        self.nexts = nexts if nexts is not None else []

    def __repr__(self):
        return f"<{self.__class__.__name__} paths={self.paths} nexts={self.nexts}>"


def get_group_subcommands(
    group: AnyGroup,
    previous_path: list[str] | None = None,
    subcommands: list[SubCommand] | None = None,
) -> list[SubCommand]:
    """One `SubCommand` per group/subgroup in the hierarchy rooted at
    `group`, each paired with the task and subgroup names reachable directly
    from it. `previous_path` and `subcommands` are recursion-internal
    accumulators; call with just `group`."""
    if previous_path is None:
        previous_path = []
    if subcommands is None:
        subcommands = []
    nexts = []
    for task_alias in group.get_subtasks():
        nexts.append(task_alias)
    for subgroup_alias, subgroup in group.get_non_empty_subgroups().items():
        nexts.append(subgroup_alias)
        get_group_subcommands(
            group=subgroup,
            previous_path=previous_path + [group.name],
            subcommands=subcommands,
        )
    if len(nexts) > 0:
        subcommands.append(SubCommand(paths=previous_path + [group.name], nexts=nexts))
    return subcommands
