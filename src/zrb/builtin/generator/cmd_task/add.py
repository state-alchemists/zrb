from typing import Any
from ..._group import project_add_group
from ....task.task import Task
from ....task.decorator import python_task
from ....task.resource_maker import ResourceMaker
from ....runner import runner
from .._common import (
    default_task_inputs, validate_project_dir, create_register_task_module,
    get_default_task_replacements, get_default_task_replacement_middlewares,
    new_task_scaffold_lock
)
from ....helper import util

import os

# Common definitions

current_dir = os.path.dirname(__file__)


@python_task(
    name='validate',
    inputs=default_task_inputs
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
    inputs=default_task_inputs,
    upstreams=[validate],
    replacements=get_default_task_replacements(),
    replacement_middlewares=get_default_task_replacement_middlewares(),
    template_path=os.path.join(current_dir, 'template'),
    destination_path='{{ input.project_dir }}',
    scaffold_locks=[new_task_scaffold_lock]
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
