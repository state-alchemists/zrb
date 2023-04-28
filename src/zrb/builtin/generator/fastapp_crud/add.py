from typing import Any
from ..._group import project_add_group
from ....task.task import Task
from ....task.decorator import python_task
from ....task.resource_maker import ResourceMaker
from ....runner import runner
from .._common import (
    default_crud_inputs, project_dir_input, app_name_input,
    module_name_input, entity_name_input, validate_project_dir,
    get_default_crud_replacements, get_default_crud_replacement_middlewares,
    new_app_scaffold_lock
)
from ....helper import util

import os

current_dir = os.path.dirname(__file__)


@python_task(
    name='validate',
    inputs=[
        project_dir_input, app_name_input, module_name_input, entity_name_input
    ],
)
async def validate(*args: Any, **kwargs: Any):
    project_dir = kwargs.get('project_dir')
    validate_project_dir(project_dir)
    app_name = kwargs.get('app_name')
    module_name = kwargs.get('module_name')
    snake_module_name = util.to_snake_case(module_name)
    automation_dir = os.path.join(
        project_dir, '_automate', util.to_snake_case(app_name)
    )
    if not os.path.exists(automation_dir):
        raise Exception(
            f'Automation directory does not exist: {automation_dir}'
        )
    source_dir = os.path.join(
        project_dir, 'src', f'{util.to_kebab_case(app_name)}'
    )
    if not os.path.exists(source_dir):
        raise Exception(f'Source does not exist: {source_dir}')
    module_path = os.path.join(source_dir, 'module', snake_module_name)
    if os.path.exists(module_path):
        raise Exception(f'Module directory already exists: {module_path}')


copy_resource = ResourceMaker(
    name='copy-resource',
    inputs=default_crud_inputs,
    upstreams=[validate],
    replacements=get_default_crud_replacements(),
    replacement_middlewares=get_default_crud_replacement_middlewares(),
    template_path=os.path.join(current_dir, 'template'),
    destination_path='{{ input.project_dir }}',
    scaffold_locks=[new_app_scaffold_lock],
    excludes=[]
)


@python_task(
    name='fastapp-crud',
    group=project_add_group,
    upstreams=[copy_resource],
    runner=runner
)
async def add_fastapp_crud(*args: Any, **kwargs: Any):
    task: Task = kwargs.get('_task')
    project_dir = kwargs.get('project_dir', '.')
    app_name = kwargs.get('app_name')
    module_name = kwargs.get('module_name')
    task.print_out(f'{project_dir} {app_name} {module_name}')
