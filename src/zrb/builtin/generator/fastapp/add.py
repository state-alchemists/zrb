from typing import Any
from ..._group import project_add_group
from ....task.task import Task
from ....task.decorator import python_task
from ....task.resource_maker import ResourceMaker
from ....runner import runner
from .._common import (
    default_app_inputs, project_dir_input, app_name_input,
    validate_project_dir, create_register_local_app_module,
    create_register_container_app_module, create_register_image_app_module,
    create_register_deployment_app_module, get_default_app_replacements,
    get_default_app_replacement_middlewares, new_app_scaffold_lock
)
from ..project_task.task_factory import (
    create_add_project_automation, create_register_app_start,
    create_register_app_start_container, create_register_app_stop_container,
    create_register_app_remove_container, create_register_app_build_image,
    create_register_app_push_image, create_register_app_deploy,
    create_register_app_destroy
)
from ....helper import util

import os

# Common definitions

current_dir = os.path.dirname(__file__)


@python_task(
    name='validate',
    inputs=[project_dir_input, app_name_input],
)
async def validate(*args: Any, **kwargs: Any):
    project_dir = kwargs.get('project_dir')
    validate_project_dir(project_dir)
    app_name = kwargs.get('app_name')
    automation_dir = os.path.join(
        project_dir, '_automate', util.to_snake_case(app_name)
    )
    if os.path.exists(automation_dir):
        raise Exception(
            f'Automation directory already exists: {automation_dir}'
        )
    source_dir = os.path.join(
        project_dir, 'src', f'{util.to_kebab_case(app_name)}'
    )
    if os.path.exists(source_dir):
        raise Exception(f'Source already exists: {source_dir}')


copy_resource = ResourceMaker(
    name='copy-resource',
    inputs=default_app_inputs,
    upstreams=[validate],
    replacements=get_default_app_replacements(),
    replacement_middlewares=get_default_app_replacement_middlewares(),
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

register_local_app_module = create_register_local_app_module(
    upstreams=[copy_resource]
)

register_container_app_module = create_register_container_app_module(
    upstreams=[register_local_app_module]
)

register_image_app_module = create_register_image_app_module(
    upstreams=[register_container_app_module]
)

register_deployment_app_module = create_register_deployment_app_module(
    upstreams=[register_image_app_module]
)

add_project_task = create_add_project_automation(
    upstreams=[copy_resource]
)

register_start = create_register_app_start(
    upstreams=[add_project_task]
)

register_start_container = create_register_app_start_container(
    upstreams=[add_project_task]
)

register_stop_container = create_register_app_stop_container(
    upstreams=[add_project_task]
)

register_remove_container = create_register_app_remove_container(
    upstreams=[add_project_task]
)

register_push_image = create_register_app_push_image(
    upstreams=[add_project_task]
)

register_build_image = create_register_app_build_image(
    upstreams=[add_project_task]
)

register_deploy = create_register_app_deploy(
    upstreams=[add_project_task]
)

register_destroy = create_register_app_destroy(
    upstreams=[add_project_task]
)


@python_task(
    name='fastapp',
    group=project_add_group,
    upstreams=[
        register_local_app_module,
        register_container_app_module,
        register_image_app_module,
        register_deployment_app_module,
        register_start,
        register_start_container,
        register_stop_container,
        register_remove_container,
        register_build_image,
        register_push_image,
        register_deploy,
        register_destroy
    ],
    runner=runner
)
async def add_fastapp(*args: Any, **kwargs: Any):
    task: Task = kwargs.get('_task')
    task.print_out('Success')
