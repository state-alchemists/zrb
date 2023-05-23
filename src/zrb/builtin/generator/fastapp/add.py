from typing import Any
from ..._group import project_add_group
from ....task.task import Task
from ....task.decorator import python_task
from ....task.resource_maker import ResourceMaker
from ....runner import runner
from .._common.input import (
    project_dir_input, app_name_input, app_image_name_input, http_port_input,
    env_prefix_input
)
from .._common.helper import validate_project_dir, create_register_app_module
from .._common.lock import new_task_app_lock
from ..project_task.task_factory import (
    create_add_project_automation_task, create_register_app_task
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
    app_dir = os.path.join(
        project_dir, 'src', f'{util.to_kebab_case(app_name)}'
    )
    if os.path.exists(app_dir):
        raise Exception(f'App directory already exists: {app_dir}')


copy_resource = ResourceMaker(
    name='copy-resource',
    inputs=[
        project_dir_input,
        app_name_input,
        app_image_name_input,
        http_port_input,
        env_prefix_input,
    ],
    upstreams=[validate],
    replacements={
        'appName': '{{input.app_name}}',
        'httpPort': '{{util.coalesce(input.http_port, "3000")}}',
        'ENV_PREFIX': '{{util.coalesce(input.env_prefix, "MY").upper()}}',
        'app-image-name': '{{input.app_image_name}}',
        'httpAuthPort': '{{util.coalesce(input.http_port, "3000") + 1}}'
    },
    template_path=os.path.join(current_dir, 'template'),
    destination_path='{{ input.project_dir }}',
    locks=[new_task_app_lock],
    excludes=[
        '*/deployment/venv',
        '*/src/kebab-app-name/venv',
        '*/src/kebab-app-name/src/frontend/node_modules',
        '*/src/kebab-app-name/src/frontend/build',
        '*/src/kebab-app-name/src/frontend/.svelte-kit',
    ]
)

register_local_app_module = create_register_app_module(
    module='local', upstreams=[copy_resource]
)

register_container_app_module = create_register_app_module(
    module='container', upstreams=[register_local_app_module]
)

register_image_app_module = create_register_app_module(
    module='image', upstreams=[register_container_app_module]
)

register_deployment_app_module = create_register_app_module(
    module='deployment', upstreams=[register_image_app_module]
)

register_test_app_module = create_register_app_module(
    module='test', upstreams=[register_deployment_app_module]
)

add_project_task = create_add_project_automation_task(
    upstreams=[copy_resource]
)

register_start = create_register_app_task(
    task_name='register-start',
    project_automation_file_name='start_project.py',
    project_automation_task_name='start',
    app_automation_file_name='local.py',
    app_automation_task_var_name_tpl='start_{snake_app_name}',
    upstreams=[add_project_task]
)

register_start_container = create_register_app_task(
    task_name='register-start-container',
    project_automation_file_name='start_project_containers.py',
    project_automation_task_name='start-containers',
    app_automation_file_name='container.py',
    app_automation_task_var_name_tpl='start_{snake_app_name}_container',
    upstreams=[add_project_task]
)

register_stop_container = create_register_app_task(
    task_name='register-stop-container',
    project_automation_file_name='stop_project_containers.py',
    project_automation_task_name='stop-containers',
    app_automation_file_name='container.py',
    app_automation_task_var_name_tpl='stop_{snake_app_name}_container',
    upstreams=[add_project_task]
)

register_remove_container = create_register_app_task(
    task_name='register-remove-container',
    project_automation_file_name='remove_project_containers.py',
    project_automation_task_name='remove-containers',
    app_automation_file_name='container.py',
    app_automation_task_var_name_tpl='remove_{snake_app_name}_container',
    upstreams=[add_project_task]
)

register_push_image = create_register_app_task(
    task_name='register-push-image',
    project_automation_file_name='push_project_images.py',
    project_automation_task_name='push-images',
    app_automation_file_name='image.py',
    app_automation_task_var_name_tpl='push_{snake_app_name}_image',
    upstreams=[add_project_task]
)

register_build_image = create_register_app_task(
    task_name='register-build-image',
    project_automation_file_name='build_project_images.py',
    project_automation_task_name='build-images',
    app_automation_file_name='image.py',
    app_automation_task_var_name_tpl='build_{snake_app_name}_image',
    upstreams=[add_project_task]
)

register_deploy = create_register_app_task(
    task_name='register-deploy',
    project_automation_file_name='deploy_project.py',
    project_automation_task_name='deploy',
    app_automation_file_name='deployment.py',
    app_automation_task_var_name_tpl='deploy_{snake_app_name}',
    upstreams=[add_project_task]
)

register_destroy = create_register_app_task(
    task_name='register-destroy',
    project_automation_file_name='destroy_project.py',
    project_automation_task_name='destroy',
    app_automation_file_name='deployment.py',
    app_automation_task_var_name_tpl='destroy_{snake_app_name}',
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
        register_test_app_module,
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
