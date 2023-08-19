from typing import Any
from ..common.task_input import project_dir_input, task_name_input
from ..common.helper import (
    validate_existing_project_dir, validate_inexisting_automation
)
from ..common.task_factory import create_register_module
from ....task.decorator import python_task
from ....task.task import Task
from ....task.resource_maker import ResourceMaker
from ....runner import runner
from ...group import project_add_group

import os

CURRENT_DIR = os.path.dirname(__file__)

###############################################################################
# Task Definitions
###############################################################################


@python_task(
    name='validate',
    inputs=[
        project_dir_input,
        task_name_input
    ]
)
async def validate(*args: Any, **kwargs: Any):
    project_dir = kwargs.get('project_dir')
    validate_existing_project_dir(project_dir)
    task_name = kwargs.get('task_name')
    validate_inexisting_automation(project_dir, task_name)


copy_resource = ResourceMaker(
    name='copy-resource',
    inputs=[
        project_dir_input,
        task_name_input
    ],
    upstreams=[validate],
    replacements={
        'zrbTaskName': '{{input.task_name}}',
    },
    template_path=os.path.join(CURRENT_DIR, 'template'),
    destination_path='{{ input.project_dir }}',
    excludes=[
        '*/__pycache__',
    ]
)

register_module = create_register_module(
    module_path='_automate.{{util.to_snake_case(input.task_name)}}',
    inputs=[task_name_input],
    upstreams=[copy_resource]
)


@python_task(
    name='python-task',
    group=project_add_group,
    upstreams=[register_module],
    runner=runner
)
async def add_python_task(*args: Any, **kwargs: Any):
    task: Task = kwargs.get('_task')
    task.print_out('Success')
