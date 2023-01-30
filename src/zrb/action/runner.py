from typing import List, Mapping, Union
from ..action.base_action import BaseAction
from ..task.base_task import BaseTask
from ..task_group.group import Group as TaskGroup
from click import Group as CliGroup, Command as CliCommand, Option as CliOption
import copy

CliSubcommand = Union[CliGroup, CliCommand]


class Runner(BaseAction):
    env_prefix: str = ''
    registered_groups: Mapping[str, CliGroup] = {}
    top_levels: List[CliSubcommand] = []

    def serve(self, cli: CliGroup) -> CliGroup:
        for original_task in self.tasks:
            task = copy.deepcopy(original_task)
            subcommand = self._create_subcommand(task)
            if subcommand not in self.top_levels:
                self.top_levels.append(subcommand)
                cli.add_command(subcommand)
        return cli

    def _create_subcommand(self, task: BaseTask) -> CliGroup:
        subcommand: CliSubcommand = self._create_task_command(task)
        task_group = task.group
        while task_group is not None:
            group = self._get_group(task_group)
            group.add_command(subcommand)
            if task_group.parent is None:
                return group
            subcommand = group
            task_group = task_group.parent
        return subcommand

    def _get_group(self, task_group: TaskGroup) -> CliGroup:
        task_group_id = task_group.get_id()
        if task_group_id in self.registered_groups:
            return self.registered_groups[task_group_id]
        group_cmd_name = task_group.get_cmd_name()
        group_description = task_group.description
        group = CliGroup(name=group_cmd_name, help=group_description)
        self.registered_groups[task_group_id] = group
        return group

    def _create_task_command(self, task: BaseTask) -> CliCommand:
        task_inputs = task.get_all_inputs()
        task_cmd_name = task.get_cmd_name()
        task_description = task.get_description()
        task_main_loop = task.create_main_loop(env_prefix=self.env_prefix)
        command = CliCommand(
            callback=task_main_loop, name=task_cmd_name, help=task_description
        )
        for task_input in task_inputs:
            param_decl = task_input.get_param_decl()
            options = task_input.get_options()
            command.params.append(CliOption(param_decl, **options))
        return command
