from typing import Mapping
from ....group.any_group import AnyGroup


class CommandCompletion():
    def __init__(self, paths: list[str] = [], subcommands: list[str] = []):
        self.paths = paths
        self.subcommands = subcommands

    def __repr__(self):
        return f"<CommandCompletion paths={self.paths} subcommands={self.subcommands}>"


def get_command_completions(
    group: AnyGroup,
    previous_path: str = [],
    command_completions: list[CommandCompletion] = []
) -> Mapping[str, list[str]]:
    group_name = group.get_name()
    subcommands = []
    for task_alias in group.get_sub_tasks():
        subcommands.append(task_alias)
        pass
    for subgroup_name, subgroup in group.get_sub_groups().items():
        subcommands.append(subgroup_name)
        get_command_completions(
            group=subgroup,
            previous_path=previous_path + [group_name],
            command_completions=command_completions,
        )
    if len(subcommands) > 0:
        command_completions.append(
            CommandCompletion(
                paths=previous_path + [group_name],
                subcommands=subcommands
            )
        )
    return command_completions
