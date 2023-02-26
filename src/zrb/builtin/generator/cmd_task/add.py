from typing import Any
from ..._group import project_add_group
from ....task.task import Task
from ....task.decorator import python_task
from ....task.resource_maker import ResourceMaker
from ....runner import runner
from .._common import (
    project_dir_input, task_name_input, validate_project_dir,
    validate_automation_name, register_task, get_default_task_replacements,
    get_default_task_replacement_middlewares, new_task_scaffold_lock
)

import os

# Common definitions

current_dir = os.path.dirname(__file__)


@python_task(
    name='task-validate-create',
    inputs=[project_dir_input, task_name_input],
)
def validate(*args: Any, **kwargs: Any):
    project_dir = kwargs.get('project_dir')
    validate_project_dir(project_dir)
    task_name = kwargs.get(project_dir, 'task_name')
    validate_automation_name(project_dir, task_name)


copy_resource = ResourceMaker(
    name='copy-resource',
    inputs=[project_dir_input, task_name_input],
    upstreams=[validate],
    replacements=get_default_task_replacements(),
    replacement_middlewares=get_default_task_replacement_middlewares(),
    template_path=os.path.join(current_dir, 'template'),
    destination_path='{{ input.project_dir }}',
    scaffold_locks=[new_task_scaffold_lock]
)


@python_task(
    name='cmd-task',
    group=project_add_group,
    inputs=[project_dir_input, task_name_input],
    upstreams=[copy_resource],
    runner=runner
)
def add_cmd_task(*args: Any, **kwargs: Any):
    task: Task = kwargs.get('_task')
    project_dir = kwargs.get('project_dir')
    validate_project_dir(project_dir)
    task_name = kwargs.get('task_name')
    task.print_out(f'Register cmd task: {task_name}')
    register_task(project_dir, task_name)
