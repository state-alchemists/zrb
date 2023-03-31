from typing import Any
from ..._group import project_add_group
from ....task.task import Task
from ....task.decorator import python_task
from ....task.resource_maker import ResourceMaker
from ....runner import runner
from .._common import (
    default_module_inputs, project_dir_input, app_name_input,
    module_name_input, validate_project_dir, get_default_module_replacements,
    get_default_module_replacement_middlewares, new_app_scaffold_lock
)
from ....helper import util

import os


current_dir = os.path.dirname(__file__)


@python_task(
    name='validate',
    inputs=[project_dir_input, app_name_input, module_name_input],
)
async def validate(*args: Any, **kwargs: Any):
    project_dir = kwargs.get('project_dir')
    validate_project_dir(project_dir)
    app_name = kwargs.get('app_name')
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


copy_resource = ResourceMaker(
    name='copy-resource',
    inputs=default_module_inputs,
    upstreams=[validate],
    replacements=get_default_module_replacements(),
    replacement_middlewares=get_default_module_replacement_middlewares(),
    template_path=os.path.join(current_dir, 'template'),
    destination_path='{{ input.project_dir }}',
    scaffold_locks=[new_app_scaffold_lock],
    excludes=[
        '*/deployment/venv',
        '*/src/kebab-app-name/venv',
        '*/src/kebab-app-name/frontend/node_modules',
        '*/src/kebab-app-name/frontend/build',
    ]
)

# TODO: generate src
# TODO: add env to template.env
# TODO: add env to module_enabled.env
# TODO: add env to module_disabled.env
# TODO: import module from main
# TODO: init module
# TODO: create service in docker compose
# TODO: create runner for local microservices


@python_task(
    name='fastapp-module',
    group=project_add_group,
    upstreams=[
        copy_resource
    ],
    runner=runner
)
async def add_fastapp_module(*args: Any, **kwargs: Any):
    task: Task = kwargs.get('_task')
    task.print_out('Success')
