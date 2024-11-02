from typing import Any
from .util import InvalidCommandError, extract_node_from_args
from .web_server import run_web_server
from ..config import BANNER, WEB_HTTP_PORT
from ..util.cli.style import stylize_section_header, stylize_faint, stylize_bold_yellow
from ..util.load import load_zrb_init
from ..group.group import Group
from ..session.session import Session
from ..task.any_task import AnyTask
from ..task.task import Task
from ..context.shared_context import SharedContext
import sys


class Cli(Group):

    def run(self, args: list[str] = []):
        load_zrb_init()
        kwargs, args = self._extract_kwargs_from_args(args)
        node, node_path, args = extract_node_from_args(self, args)
        if isinstance(node, Group):
            self._show_group_info(node)
            return
        if "h" in kwargs or "help" in kwargs:
            self._show_task_info(node)
            return
        result = self._run_task(node, args, kwargs)
        if result is not None:
            print(result)
        run_command = self._get_run_command(node_path, kwargs, args)
        self._print_run_command(run_command)
        return result

    def _print_run_command(self, run_command: str):
        print(
            stylize_faint("To run again:"),
            stylize_bold_yellow(run_command),
            file=sys.stderr
        )

    def _get_run_command(
        self, node_path: list[str], kwargs: dict[str, Any], args: list[str]
    ) -> str:
        parts = [self.name] + node_path
        if len(kwargs) > 0:
            parts += [f"--{key}={val}" for key, val in kwargs.items()]
        if len(args) > 0:
            parts += args
        return " ".join(parts)

    def _extract_node_from_args(
        self, positional: list[str]
    ) -> tuple[Group | AnyTask, list[str], list[str]]:
        node = self
        node_path = []
        residual_args = []
        for index, name in enumerate(positional):
            task = node.get_task_by_alias(name)
            group = node.get_group_by_alias(name)
            if group is not None and not group.contain_tasks:
                # If group doesn't contain any task, then ignore its existence
                group = None
            if task is None and group is None:
                raise InvalidCommandError(
                    f"Invalid subcommand: {self.name} {' '.join(positional)}"
                )
            node_path.append(name)
            if group is not None:
                if task is not None and index == len(positional) - 1:
                    node = task
                    residual_args = positional[index+1:]
                    break
                node = group
                continue
            if task is not None:
                node = task
                residual_args = positional[index+1:]
                break
        return node, node_path, residual_args

    def _run_task(
        self, task: AnyTask, args: list[str], options: list[str]
    ) -> Any:
        shared_ctx = SharedContext(input=options, args=args)
        task_inputs = task.inputs
        arg_index = 0
        for task_input in task_inputs:
            task_input_name = task_input.name
            if task_input_name in shared_ctx.input:
                str_value = shared_ctx.input[task_input_name]
                task_input.update_shared_context(shared_ctx, str_value)
                continue
            if arg_index < len(args):
                task_input.update_shared_context(shared_ctx, args[arg_index])
                arg_index += 1
                continue
            str_value = task_input.prompt_cli_str(shared_ctx)
            task_input.update_shared_context(shared_ctx, str_value)
        return task.run(Session(shared_ctx=shared_ctx))

    def _show_task_info(self, task: AnyTask):
        description = task.description
        inputs = task.inputs
        if description != task.name and description != "":
            print(stylize_section_header("DESCRIPTION"))
            print(description)
            print()
        if len(inputs) > 0:
            print(stylize_section_header("INPUTS"))
            for task_input in inputs:
                task_input_name = task_input.name.ljust(20)
                print(f"  --{task_input_name}: {task_input.description}")
            print()

    def _show_group_info(self, group: Group):
        if group.banner != "":
            print(group.banner)
            print()
        if group.description != group.name and group.description != "":
            print(stylize_section_header("DESCRIPTION"))
            print(group.description)
            print()
        if len(group.subgroups) > 0:
            print(stylize_section_header("GROUPS"))
            for alias, subgroup in group.subgroups.items():
                if not subgroup.contain_tasks:
                    continue
                alias = alias.ljust(20)
                print(f"  {alias}: {subgroup.description}")
            print()
        if len(group.subtasks) > 0:
            print(stylize_section_header("TASKS"))
            for alias, subtask in group.subtasks.items():
                alias = alias.ljust(20)
                print(f"  {alias}: {subtask.description}")
            print()

    def _extract_kwargs_from_args(
        self, args: list[str]
    ) -> tuple[dict[str, Any], list[str]]:
        residual_args = []  # To store positional arguments
        kwargs = {}     # To store options as a dictionary
        i = 0
        while i < len(args):
            arg = args[i]
            if arg.startswith('--'):
                # Handle key-value pairs like --keyword=value
                if '=' in arg:
                    key, value = arg[2:].split('=', 1)
                    kwargs[key] = value
                else:
                    # Handle flags like --this followed by a value or set to True
                    key = arg[2:]
                    # Check if the next item is a value or another flag
                    if i + 1 < len(args) and not args[i + 1].startswith('-'):
                        kwargs[key] = args[i + 1]
                        i += 1  # Skip the next argument as it's a value
                    else:
                        kwargs[key] = True
            elif arg.startswith('-'):
                # Handle short flags like -t or -n
                key = arg[1:]
                kwargs[key] = True
            else:
                # Anything else is considered a positional argument
                residual_args.append(arg)
            i += 1
        return kwargs, residual_args


cli = Cli(
    name="zrb",
    description="A framework to enhance your workflow",
    banner=BANNER
)

cli.add_task(
    Task(
        name="start-server",
        description="Make tasks available via HTTP Requests",
        action=lambda ctx: run_web_server(
            ctx=ctx, root_group=cli, port=WEB_HTTP_PORT
        ),
        retries=0
    )
)
