from typing import List, Mapping, Union
from ..action.base_action import BaseAction
from ..task.base_task import BaseTask
from ..task_group.group import Group as TaskGroup
import click

CliSubcommand = Union[click.Group, click.Command]


class Runner(BaseAction):
    '''
    Runner class.
    Any tasks registered to the runner will be accessible from the terminal
    '''

    def __init__(self, env_prefix: str = ''):
        BaseAction.__init__(self)
        self.env_prefix = env_prefix
        self._registered_groups: Mapping[str, click.Group] = {}
        self._top_levels: List[CliSubcommand] = []
        self._subcommands: Mapping[str, List[click.Group]] = {}

    def serve(self, cli: click.Group) -> click.Group:
        for task in self._tasks:
            subcommand = self._create_cli_subcommand(task)
            if subcommand not in self._top_levels:
                self._top_levels.append(subcommand)
                cli.add_command(subcommand)
        return cli

    def _create_cli_subcommand(self, task: BaseTask) -> click.Group:
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
    ) -> click.Group:
        task_group_id = task_group.get_id()
        group = self._get_cli_group(task_group)
        if task_group_id not in self._subcommands:
            self._subcommands[task_group_id] = []
        if subcommand not in self._subcommands[task_group_id]:
            group.add_command(subcommand)
            self._subcommands[task_group_id].append(subcommand)
        return group

    def _get_cli_group(self, task_group: TaskGroup) -> click.Group:
        task_group_id = task_group.get_id()
        if task_group_id in self._registered_groups:
            return self._registered_groups[task_group_id]
        group_cmd_name = task_group.get_cmd_name()
        group_description = task_group.description
        group = click.Group(name=group_cmd_name, help=group_description)
        self._registered_groups[task_group_id] = group
        return group

    def _create_cli_command(self, task: BaseTask) -> click.Command:
        task_inputs = task.get_all_inputs()
        task_cmd_name = task.get_cmd_name()
        task_description = task.get_description()
        task_main_loop = task.create_main_loop(
            env_prefix=self.env_prefix, raise_error=False
         )
        command = click.Command(
            callback=task_main_loop, name=task_cmd_name, help=task_description
        )
        # by default, add an argument named _args
        command.params.append(click.Argument(['_args'], nargs=-1))
        # add task inputs,
        # if there are inputs with the same name, choose the first.
        registered_input: Mapping[str, bool] = {}
        for task_input in task_inputs:
            if task_input.name in registered_input:
                continue
            registered_input[task_input.name] = True
            param_decl = task_input.get_param_decl()
            options = task_input.get_options()
            command.params.append(click.Option(param_decl, **options))
        return command
