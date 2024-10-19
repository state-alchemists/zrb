from typing import Any
from collections.abc import Mapping
from ..group import Group
from ..task import AnyTask
from ..session import Session

import sys


class Cli(Group):

    def run(self):
        positional, options = self._parse_args(sys.argv[1:])
        node, args = self._get_node_from_positional_argv(positional)
        if isinstance(node, Group):
            self._show_group_info(node)
            return
        if "h" in options or "help" in options:
            self._show_task_info(node)
            return
        self._run_task(node, args, options)

    def _get_node_from_positional_argv(
        self, positional: list[str]
    ) -> tuple[Group | AnyTask, list[str]]:
        node = self
        args = []
        for index, name in enumerate(positional):
            task = node.get_task_by_name(name)
            group = node.get_group_by_name(name)
            if task is None and group is None:
                raise ValueError("Invalid positional arguments")
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
        session = Session(
            inputs=options,
            args=args
        )
        inputs = task.get_inputs()
        for task_input in inputs:
            if task_input.get_name() not in session.inputs:
                print(task_input.get_name())
                pass
        task.run(session)

    def _show_task_info(self, task: AnyTask):
        description = task.get_description()
        inputs = task.get_inputs()
        print(description)
        for task_input in inputs:
            print(f"--{task_input.get_name()}: {task_input.get_description()}")

    def _show_group_info(self, group: Group):
        description = group.get_description()
        sub_groups = group.get_sub_groups()
        sub_tasks = group.get_sub_tasks()
        print(description)
        print()
        print("GROUPS")
        for group in sub_groups:
            print(f"- {group.get_name()}: {group.get_description()}")
        print()
        print("TASKS")
        for task in sub_tasks:
            print(f"- {task.get_name()}: {task.get_description()}")

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


cli = Cli(
    name="zrb",
    description="A Framework to Enhanche your workflow"
)
