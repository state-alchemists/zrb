import os

from zrb.builtin.project._helper import (
    create_register_module,
    validate_existing_project_dir,
    validate_inexisting_automation,
)
from zrb.builtin.project._input import project_dir_input
from zrb.builtin.project.add.task._group import project_add_task_group
from zrb.builtin.project.add.task._input import task_name_input
from zrb.helper.typing import Any
from zrb.runner import runner
from zrb.task.decorator import python_task
from zrb.task.resource_maker import ResourceMaker
from zrb.task.task import Task

_CURRENT_DIR = os.path.dirname(__file__)


@python_task(
    name="validate",
    inputs=[
        project_dir_input,
        task_name_input,
    ],
)
async def validate(*args: Any, **kwargs: Any):
    project_dir = kwargs.get("project_dir")
    validate_existing_project_dir(project_dir)
    task_name = kwargs.get("task_name")
    validate_inexisting_automation(project_dir, task_name)


copy_resource = ResourceMaker(
    name="copy-resource",
    inputs=[
        project_dir_input,
        task_name_input,
    ],
    upstreams=[validate],
    replacements={
        "zrbTaskName": "{{input.task_name}}",
    },
    template_path=os.path.join(_CURRENT_DIR, "template"),
    destination_path="{{ input.project_dir }}",
    excludes=[
        "*/__pycache__",
    ],
)

register_module = create_register_module(
    module_path="_automate.{{util.to_snake_case(input.task_name)}}",
    alias="_automate_{{util.to_snake_case(input.task_name)}}",
    inputs=[task_name_input],
    upstreams=[copy_resource],
)


@python_task(
    name="cmd", group=project_add_task_group, upstreams=[register_module], runner=runner
)
async def add_cmd_task(*args: Any, **kwargs: Any):
    task: Task = kwargs.get("_task")
    task.print_out("Success")
