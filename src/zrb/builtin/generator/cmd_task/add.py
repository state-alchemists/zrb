from typing import Any
from ..._group import project_add_group
from ....task.task import Task
from ....task.decorator import python_task
from ....task.resource_maker import ResourceMaker
from ....runner import runner
from .._common.input import project_dir_input, task_name_input
from .._common.helper import validate_project_dir, create_register_task_module
from .._common.lock import new_task_lock
from ....helper import util

import os

# Common definitions

current_dir = os.path.dirname(__file__)


@python_task(
    name='validate',
    inputs=[
        project_dir_input,
        task_name_input,
    ]
)
async def validate(*args: Any, **kwargs: Any):
    project_dir = kwargs.get('project_dir')
    validate_project_dir(project_dir)
    task_name = kwargs.get('task_name')
    automation_file = os.path.join(
        project_dir, '_automate', f'{util.to_snake_case(task_name)}.py'
    )
    if os.path.exists(automation_file):
        raise Exception(f'Automation file already exists: {automation_file}')


copy_resource = ResourceMaker(
    name='copy-resource',
    inputs=[
        project_dir_input,
        task_name_input,
    ],
    upstreams=[validate],
    replacements={
        'taskName': '{{input.task_name}}',
    },
    template_path=os.path.join(current_dir, 'template'),
    destination_path='{{ input.project_dir }}',
    locks=[new_task_lock]
)

register_task_module = create_register_task_module(
    upstreams=[copy_resource]
)


@python_task(
    name='cmd-task',
    group=project_add_group,
    upstreams=[register_task_module],
    runner=runner
)
async def add_cmd_task(*args: Any, **kwargs: Any):
    task: Task = kwargs.get('_task')
    task.print_out('Success')
