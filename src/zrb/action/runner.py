import sys

import click

from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Any, Callable, List, Mapping, Union
from zrb.task.any_task import AnyTask
from zrb.task_group.group import Group as TaskGroup

CliSubcommand = Union[click.Group, click.Command]


@typechecked
class Runner:
    """
    Runner class.
    Any tasks registered to the runner will be accessible from the terminal
    """

    def __init__(self, env_prefix: str = ""):
        logger.info(colored("Create runner", attrs=["dark"]))
        self.__env_prefix = env_prefix
        self.__tasks: List[AnyTask] = []
        self.__registered_groups: Mapping[str, click.Group] = {}
        self.__top_levels: List[CliSubcommand] = []
        self.__subcommands: Mapping[str, List[click.Group]] = {}
        self.__registered_task_cli_name: List[str] = []
        logger.info(colored("Runner created", attrs=["dark"]))

    def register(self, *tasks: AnyTask):
        for task in tasks:
            task._set_has_cli_interface()
            cli_name = task._get_full_cli_name()
            if cli_name in self.__registered_task_cli_name:
                raise RuntimeError(f'Task "{cli_name}" has already been registered')
            logger.debug(colored(f'Register task: "{cli_name}"', attrs=["dark"]))
            self.__tasks.append(task)
            self.__registered_task_cli_name.append(cli_name)
            logger.debug(colored(f'Task registered: "{cli_name}"', attrs=["dark"]))

    def serve(self, cli: click.Group) -> click.Group:
        for task in self.__tasks:
            subcommand = self.__create_cli_subcommand(task)
            if subcommand not in self.__top_levels:
                self.__top_levels.append(subcommand)
                cli.add_command(subcommand)
        return cli

    def __create_cli_subcommand(
        self, task: AnyTask
    ) -> Union[click.Group, click.Command]:
        subcommand: CliSubcommand = self.__create_cli_command(task)
        task_group = task._group
        while task_group is not None:
            group = self.__register_sub_command(task_group, subcommand)
            parent_group = task_group.get_parent()
            if parent_group is None:
                return group
            subcommand = group
            task_group = parent_group
        return subcommand

    def __register_sub_command(
        self, task_group: TaskGroup, subcommand: CliSubcommand
    ) -> click.Group:
        task_group_id = task_group._get_full_cli_name()
        group = self.__get_cli_group(task_group)
        if task_group_id not in self.__subcommands:
            self.__subcommands[task_group_id] = []
        if subcommand not in self.__subcommands[task_group_id]:
            group.add_command(subcommand)
            self.__subcommands[task_group_id].append(subcommand)
        return group

    def __get_cli_group(self, task_group: TaskGroup) -> click.Group:
        task_group_id = task_group._get_full_cli_name()
        if task_group_id in self.__registered_groups:
            return self.__registered_groups[task_group_id]
        group_cli_name = task_group.get_cli_name()
        group_description = task_group.get_description()
        group = click.Group(name=group_cli_name, help=group_description)
        self.__registered_groups[task_group_id] = group
        return group

    def __create_cli_command(self, task: AnyTask) -> click.Command:
        task_inputs = task._get_combined_inputs()
        task_cli_name = task.get_cli_name()
        task_description = task.get_description()
        task_function = task.to_function(env_prefix=self.__env_prefix, raise_error=True)
        callback = self.__wrap_task_function(task_function)
        command = click.Command(
            callback=callback, name=task_cli_name, help=task_description
        )
        # by default, add an argument named _args
        command.params.append(click.Argument(["_args"], nargs=-1))
        # add task inputs,
        # if there are inputs with the same name, choose the first.
        registered_input: Mapping[str, bool] = {}
        for task_input in task_inputs:
            if task_input.get_name() in registered_input:
                continue
            registered_input[task_input.get_name()] = True
            param_decl = task_input.get_param_decl()
            options = task_input.get_options()
            command.params.append(click.Option(param_decl, **options))
        return command

    def __wrap_task_function(self, function: Callable[..., Any]) -> Callable[..., Any]:
        def wrapped_function(*args: Any, **kwargs: Any) -> Any:
            try:
                function(*args, **kwargs)
            except Exception:
                sys.exit(1)

        return wrapped_function
