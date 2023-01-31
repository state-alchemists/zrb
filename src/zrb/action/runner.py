from typing import List, Mapping, Union
from ..action.base_action import BaseAction
from ..task.base_task import BaseTask
from ..task_group.group import Group as TaskGroup
from click import Group as CliGroup, Command as CliCommand, Option as CliOption
import copy

CliSubcommand = Union[CliGroup, CliCommand]


class Runner(BaseAction):
    env_prefix: str = ''
    zrb_registered_groups: Mapping[str, CliGroup] = {}
    zrb_top_levels: List[CliSubcommand] = []
    zrb_subcommands: Mapping[str, List[CliGroup]] = {}

    def serve(self, cli: CliGroup) -> CliGroup:
        for original_task in self.tasks:
            task = copy.deepcopy(original_task)
            subcommand = self._create_cli_subcommand(task)
            if subcommand not in self.zrb_top_levels:
                self.zrb_top_levels.append(subcommand)
                cli.add_command(subcommand)
        return cli

    def _create_cli_subcommand(self, task: BaseTask) -> CliGroup:
        subcommand: CliSubcommand = self._create_cli_command(task)
        task_group = task.group
        while task_group is not None:
            group = self._register_sub_command(task_group, subcommand)
            if task_group.parent is None:
                return group
            subcommand = group
            task_group = task_group.parent
        return subcommand

    def _register_sub_command(
        self, task_group: TaskGroup, subcommand: CliSubcommand
    ) -> CliGroup:
        task_group_id = task_group.get_id()
        group = self._get_cli_group(task_group)
        if task_group_id not in self.zrb_subcommands:
            self.zrb_subcommands[task_group_id] = []
        if subcommand not in self.zrb_subcommands[task_group_id]:
            group.add_command(subcommand)
            self.zrb_subcommands[task_group_id].append(subcommand)
        return group

    def _get_cli_group(self, task_group: TaskGroup) -> CliGroup:
        task_group_id = task_group.get_id()
        if task_group_id in self.zrb_registered_groups:
            return self.zrb_registered_groups[task_group_id]
        group_cmd_name = task_group.get_cmd_name()
        group_description = task_group.description
        group = CliGroup(name=group_cmd_name, help=group_description)
        self.zrb_registered_groups[task_group_id] = group
        return group

    def _create_cli_command(self, task: BaseTask) -> CliCommand:
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
