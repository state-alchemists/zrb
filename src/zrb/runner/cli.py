from typing import Any
from collections.abc import Mapping
from ..config import VERSION
from ..util.cli.style import stylize_section_header, stylize_faint, stylize_bold_yellow
from ..util.load import load_zrb_init
from ..group.group import Group
from ..task.any_task import AnyTask
from ..context.shared_context import SharedContext
import sys


class Cli(Group):

    def run(self, args: list[str]):
        load_zrb_init()
        kwargs, args = self._extract_kwargs_from_args(args)
        node, node_path, args = self._extract_node_from_args(args)
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
        self, node_path: list[str], kwargs: Mapping[str, Any], args: list[str]
    ) -> str:
        parts = [self.get_name()] + node_path
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
            group = node.get_group_by_name(name)
            if task is None and group is None:
                raise ValueError("Invalid command")
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
        task_inputs = task.get_inputs()
        arg_index = 0
        for task_input in task_inputs:
            if task_input.get_name() not in shared_ctx._input:
                if arg_index < len(args):
                    task_input.update_shared_context(shared_ctx, args[arg_index])
                    arg_index += 1
                    continue
                input_value = task_input.prompt_cli(shared_ctx)
                task_input.update_shared_context(shared_ctx, input_value)
        return task.run(shared_ctx)

    def _show_task_info(self, task: AnyTask):
        description = task.get_description()
        inputs = task.get_inputs()
        if description != task.get_name() and description != "":
            print(stylize_section_header("DESCRIPTION"))
            print(description)
            print()
        if len(inputs) > 0:
            print(stylize_section_header("INPUTS"))
            for task_input in inputs:
                task_input_name = task_input.get_name().ljust(20)
                print(f"  --{task_input_name}: {task_input.get_description()}")
            print()

    def _show_group_info(self, group: Group):
        banner = group.get_banner()
        description = group.get_description()
        sub_groups = group.get_sub_groups()
        sub_tasks = group.get_sub_tasks()
        if banner != "":
            print(banner)
            print()
        if description != group.get_name() and description != "":
            print(stylize_section_header("DESCRIPTION"))
            print(description)
            print()
        if len(sub_groups) > 0:
            print(stylize_section_header("GROUPS"))
            for group_name, group in sub_groups.items():
                group_name = group_name.ljust(20)
                print(f"  {group_name}: {group.get_description()}")
            print()
        if len(sub_tasks) > 0:
            print(stylize_section_header("TASKS"))
            for alias, task in sub_tasks.items():
                alias = alias.ljust(20)
                print(f"  {alias}: {task.get_description()}")
            print()

    def _extract_kwargs_from_args(
        self, args: list[str]
    ) -> tuple[Mapping[str, Any], list[str]]:
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


ZRB_BANNER = f"""
                bb
   zzzzz rr rr  bb
     zz  rrr  r bbbbbb
    zz   rr     bb   bb
   zzzzz rr     bbbbbb   {VERSION}
   _ _ . .  . _ .  _ . . .

Super framework for your super app.

☕ Donate at: https://stalchmst.com/donation
🐙 Submit issues/PR at: https://github.com/state-alchemists/zrb
🐤 Follow us at: https://twitter.com/zarubastalchmst
"""

cli = Cli(
    name="zrb",
    description="A Framework to Enhanche your workflow",
    banner=ZRB_BANNER
)
