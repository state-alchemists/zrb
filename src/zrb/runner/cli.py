import sys
from typing import Any

from zrb.config import BANNER, VERSION, WEB_HTTP_PORT
from zrb.context.any_context import AnyContext
from zrb.context.shared_context import SharedContext
from zrb.group.group import Group
from zrb.runner.common_util import get_run_kwargs
from zrb.runner.web_app import create_web_app
from zrb.runner.web_config.config_factory import web_config
from zrb.session.session import Session
from zrb.session_state_logger.session_state_logger_factory import session_state_logger
from zrb.task.any_task import AnyTask
from zrb.task.make_task import make_task
from zrb.util.cli.style import (
    stylize_bold_yellow,
    stylize_faint,
    stylize_section_header,
)
from zrb.util.group import extract_node_from_args, get_non_empty_subgroups, get_subtasks
from zrb.util.string.conversion import double_quote


class Cli(Group):
    def run(self, args: list[str] = []):
        kwargs, args = self._extract_kwargs_from_args(args)
        node, node_path, args = extract_node_from_args(self, args)
        if isinstance(node, Group):
            self._show_group_info(node)
            return
        if "h" in kwargs or "help" in kwargs:
            self._show_task_info(node)
            return
        run_kwargs = get_run_kwargs(task=node, args=args, kwargs=kwargs, cli_mode=True)
        try:
            result = self._run_task(node, args, run_kwargs)
            if result is not None:
                print(result)
            return result
        finally:
            run_command = self._get_run_command(node_path, run_kwargs)
            self._print_run_command(run_command)

    def _print_run_command(self, run_command: str):
        print(
            stylize_faint("To run again:"),
            stylize_bold_yellow(run_command),
            file=sys.stderr,
        )

    def _get_run_command(self, node_path: list[str], run_kwargs: dict[str, str]) -> str:
        parts = [self.name] + node_path
        if len(run_kwargs) > 0:
            parts += [
                self._get_run_command_param(key, val) for key, val in run_kwargs.items()
            ]
        return " ".join(parts)

    def _get_run_command_param(self, key: str, val: str) -> str:
        if '"' in val or "'" in val or " " in val or val == "":
            return f"--{key} {double_quote(val)}"
        return f"--{key} {val}"

    def _run_task(
        self, task: AnyTask, args: list[str], run_kwargs: dict[str, str]
    ) -> tuple[Any]:
        shared_ctx = SharedContext(args=args)
        for task_input in task.inputs:
            if task_input.name in run_kwargs:
                task_input.update_shared_context(
                    shared_ctx, run_kwargs[task_input.name]
                )
                continue
        return task.run(Session(shared_ctx=shared_ctx, root_group=self))

    def _show_task_info(self, task: AnyTask):
        description = task.description
        inputs = task.inputs
        if description != task.name and description != "":
            print(stylize_section_header("DESCRIPTION"))
            print(description)
            print()
        if len(inputs) > 0:
            print(stylize_section_header("INPUTS"))
            max_input_name_length = max(len(task_input.name) for task_input in inputs)
            for task_input in inputs:
                task_input_name = task_input.name.ljust(max_input_name_length + 1)
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
        subgroups = get_non_empty_subgroups(group)
        if len(subgroups) > 0:
            print(stylize_section_header("GROUPS"))
            max_subgroup_alias_length = max(len(s) for s in subgroups)
            for alias, subgroup in subgroups.items():
                alias = alias.ljust(max_subgroup_alias_length + 1)
                print(f"  {alias}: {subgroup.description}")
            print()
        subtasks = get_subtasks(group)
        if len(subtasks) > 0:
            print(stylize_section_header("TASKS"))
            max_subtask_alias_length = max(len(s) for s in subtasks)
            for alias, subtask in subtasks.items():
                alias = alias.ljust(max_subtask_alias_length + 1)
                print(f"  {alias}: {subtask.description}")
            print()

    def _extract_kwargs_from_args(
        self, args: list[str]
    ) -> tuple[dict[str, Any], list[str]]:
        residual_args = []  # To store positional arguments
        kwargs = {}  # To store options as a dictionary
        i = 0
        while i < len(args):
            arg = args[i]
            if arg.startswith("--"):
                # Handle key-value pairs like --keyword=value
                if "=" in arg:
                    key, value = arg[2:].split("=", 1)
                    kwargs[key] = value
                else:
                    # Handle flags like --this followed by a value or set to True
                    key = arg[2:]
                    # Check if the next item is a value or another flag
                    if i + 1 < len(args) and not args[i + 1].startswith("-"):
                        kwargs[key] = args[i + 1]
                        i += 1  # Skip the next argument as it's a value
                    else:
                        kwargs[key] = True
            elif arg.startswith("-"):
                # Handle short flags like -t or -n
                key = arg[1:]
                kwargs[key] = True
            else:
                # Anything else is considered a positional argument
                residual_args.append(arg)
            i += 1
        return kwargs, residual_args


cli = Cli(name="zrb", description="Your Automation Powerhouse", banner=BANNER)


@make_task(
    name="version", description="🌟 Get current Zrb version", retries=0, group=cli
)
def get_version(_: AnyContext):
    return VERSION


server_group = cli.add_group(
    Group(name="server", description="🌐 Server related command")
)


@make_task(
    name="start-server",
    description="🚀 Start Zrb Web Server",
    cli_only=True,
    retries=0,
    group=server_group,
    alias="start",
)
async def start_server(_: AnyContext):
    from uvicorn import Config, Server

    app = create_web_app(cli, web_config, session_state_logger)
    server = Server(Config(app=app, host="0.0.0.0", port=WEB_HTTP_PORT, loop="asyncio"))
    await server.serve()
