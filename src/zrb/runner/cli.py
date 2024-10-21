from typing import Any
from collections.abc import Mapping
from ..config import VERSION
from ..util.cli.style import section_header
from ..util.load import load_zrb_init
from ..group.group import Group
from ..task.any_task import AnyTask
from ..session.shared_context import SharedContext

import sys


class Cli(Group):

    def run(self):
        load_zrb_init()
        positional, options = self._parse_args(sys.argv[1:])
        node, args = self._get_node_from_positional_argv(positional)
        if isinstance(node, Group):
            self._show_group_info(node)
            return
        if "h" in options or "help" in options:
            self._show_task_info(node)
            return
        result = self._run_task(node, args, options)
        if result is not None:
            print(result)
        return result

    def _get_node_from_positional_argv(
        self, positional: list[str]
    ) -> tuple[Group | AnyTask, list[str]]:
        node = self
        args = []
        for index, name in enumerate(positional):
            task = node.get_task_by_alias(name)
            group = node.get_group_by_name(name)
            if task is None and group is None:
                raise ValueError("Invalid command")
            if group is not None:
                if task is not None and index == len(positional) - 1:
                    node = task
                    args = positional[index+1:]
                    break
                node = group
                continue
            if task is not None:
                node = task
                args = positional[index+1:]
                break
        return node, args

    def _run_task(self, task: AnyTask, args: list[str], options: list[str]):
        session = SharedContext(inputs=options, args=args)
        inputs = task.get_inputs()
        arg_index = 0
        for task_input in inputs:
            if task_input.get_name() not in session.inputs:
                if arg_index < len(args):
                    task_input.update_shared_context(session, args[arg_index])
                    arg_index += 1
                    continue
                input_value = task_input.prompt_cli(session)
                task_input.update_shared_context(session, input_value)
        return task.run(session)

    def _show_task_info(self, task: AnyTask):
        description = task.get_description()
        inputs = task.get_inputs()
        if description != task.get_name() and description != "":
            print(section_header("DESCRIPTION"))
            print(description)
            print()
        if len(inputs) > 0:
            print(section_header("INPUTS"))
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
            print(section_header("DESCRIPTION"))
            print(description)
            print()
        if len(sub_groups) > 0:
            print(section_header("GROUPS"))
            for group_name, group in sub_groups.items():
                group_name = group_name.ljust(20)
                print(f"  {group_name}: {group.get_description()}")
            print()
        if len(sub_tasks) > 0:
            print(section_header("TASKS"))
            for alias, task in sub_tasks.items():
                alias = alias.ljust(20)
                print(f"  {alias}: {task.get_description()}")
            print()

    def _parse_args(self, args: list[str]) -> tuple[list[str], Mapping[str, Any]]:
        positional = []  # To store positional arguments
        options = {}     # To store options as a dictionary
        i = 0
        while i < len(args):
            arg = args[i]
            if arg.startswith('--'):
                # Handle key-value pairs like --keyword=value
                if '=' in arg:
                    key, value = arg[2:].split('=', 1)
                    options[key] = value
                else:
                    # Handle flags like --this followed by a value or set to True
                    key = arg[2:]
                    # Check if the next item is a value or another flag
                    if i + 1 < len(args) and not args[i + 1].startswith('-'):
                        options[key] = args[i + 1]
                        i += 1  # Skip the next argument as it's a value
                    else:
                        options[key] = True
            elif arg.startswith('-'):
                # Handle short flags like -t or -n
                key = arg[1:]
                options[key] = True
            else:
                # Anything else is considered a positional argument
                positional.append(arg)
            i += 1
        return positional, options


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
