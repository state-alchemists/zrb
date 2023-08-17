from typing import Any
from ..._group import project_add_group
from ....task.task import Task
from ....task.decorator import python_task
from ....task.resource_maker import ResourceMaker
from ....runner import runner
from .._common.task_input import (
    project_dir_input, app_name_input, app_image_name_input, http_port_input,
    env_prefix_input
)
from .._common.helper import (
    validate_existing_project_dir, validate_inexisting_automation
)
from .._common.task_factory import create_register_module
from ..project_task.task_factory import (
    create_ensure_project_tasks, create_register_app_task
)
from ....helper import util

import os

current_dir = os.path.dirname(__file__)

###############################################################################
# Task Definitions
###############################################################################


@python_task(
    name='validate',
    inputs=[project_dir_input, app_name_input],
)
async def validate(*args: Any, **kwargs: Any):
    project_dir = kwargs.get('project_dir')
    validate_existing_project_dir(project_dir)
    app_name = kwargs.get('app_name')
    validate_inexisting_automation(project_dir, app_name)
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
        'zrbAppName': '{{input.app_name}}',
        'zrbAppHttpPort': '{{util.coalesce(input.http_port, "3001")}}',
        'ZRB_ENV_PREFIX': '{{util.coalesce(input.env_prefix, "MY").upper()}}',
        'zrb-app-image-name': '{{input.app_image_name}}',
        'zrbAppHttpAuthPort': '{{util.coalesce(input.http_port, "3001") + 1}}',
        'zrbAppHttpLogPort': '{{util.coalesce(input.http_port, "3001") + 2}}'
    },
    template_path=os.path.join(current_dir, 'template'),
    destination_path='{{ input.project_dir }}',
    excludes=[
        '*/__pycache__',
        '*/deployment/venv',
        '*/src/kebab-app-name/.venv',
        '*/src/kebab-app-name/src/frontend/node_modules',
        '*/src/kebab-app-name/src/frontend/build',
        '*/src/kebab-app-name/src/frontend/.svelte-kit',
    ]
)

register_local_module = create_register_module(
    module_path='_automate.{{util.to_snake_case(input.app_name)}}.local',
    alias='{{util.to_snake_case(input.app_name)}}_local',
    inputs=[app_name_input],
    upstreams=[copy_resource]
)

register_container_module = create_register_module(
    module_path='_automate.{{util.to_snake_case(input.app_name)}}.container',
    alias='{{util.to_snake_case(input.app_name)}}_container',
    inputs=[app_name_input],
    upstreams=[register_local_module]
)

register_image_module = create_register_module(
    module_path='_automate.{{util.to_snake_case(input.app_name)}}.image',
    alias='{{util.to_snake_case(input.app_name)}}_image',
    inputs=[app_name_input],
    upstreams=[register_container_module]
)

register_deployment_module = create_register_module(
    module_path='_automate.{{util.to_snake_case(input.app_name)}}.deployment',
    alias='{{util.to_snake_case(input.app_name)}}_deployment',
    inputs=[app_name_input],
    upstreams=[register_image_module]
)

register_test_module = create_register_module(
    module_path='_automate.{{util.to_snake_case(input.app_name)}}.test',
    alias='{{util.to_snake_case(input.app_name)}}_test',
    inputs=[app_name_input],
    upstreams=[register_deployment_module]
)

register_load_test_module = create_register_module(
    module_path='_automate.{{util.to_snake_case(input.app_name)}}.load_test',
    alias='{{util.to_snake_case(input.app_name)}}_load_test',
    inputs=[app_name_input],
    upstreams=[register_test_module]
)

ensure_project_tasks = create_ensure_project_tasks(
    upstreams=[copy_resource]
)

register_start = create_register_app_task(
    task_name='register-start',
    project_task_file_name='start_project.py',
    project_task_name='start',
    app_task_file_name='local.py',
    app_task_var_name_tpl='start_{snake_app_name}',
    upstreams=[ensure_project_tasks]
)

register_start_container = create_register_app_task(
    task_name='register-start-container',
    project_task_file_name='start_project_containers.py',
    project_task_name='start-containers',
    app_task_file_name='container.py',
    app_task_var_name_tpl='start_{snake_app_name}_container',
    upstreams=[ensure_project_tasks]
)

register_stop_container = create_register_app_task(
    task_name='register-stop-container',
    project_task_file_name='stop_project_containers.py',
    project_task_name='stop-containers',
    app_task_file_name='container.py',
    app_task_var_name_tpl='stop_{snake_app_name}_container',
    upstreams=[ensure_project_tasks]
)

register_remove_container = create_register_app_task(
    task_name='register-remove-container',
    project_task_file_name='remove_project_containers.py',
    project_task_name='remove-containers',
    app_task_file_name='container.py',
    app_task_var_name_tpl='remove_{snake_app_name}_container',
    upstreams=[ensure_project_tasks]
)

register_push_image = create_register_app_task(
    task_name='register-push-image',
    project_task_file_name='push_project_images.py',
    project_task_name='push-images',
    app_task_file_name='image.py',
    app_task_var_name_tpl='push_{snake_app_name}_image',
    upstreams=[ensure_project_tasks]
)

register_build_image = create_register_app_task(
    task_name='register-build-image',
    project_task_file_name='build_project_images.py',
    project_task_name='build-images',
    app_task_file_name='image.py',
    app_task_var_name_tpl='build_{snake_app_name}_image',
    upstreams=[ensure_project_tasks]
)

register_deploy = create_register_app_task(
    task_name='register-deploy',
    project_task_file_name='deploy_project.py',
    project_task_name='deploy',
    app_task_file_name='deployment.py',
    app_task_var_name_tpl='deploy_{snake_app_name}',
    upstreams=[ensure_project_tasks]
)

register_destroy = create_register_app_task(
    task_name='register-destroy',
    project_task_file_name='destroy_project.py',
    project_task_name='destroy',
    app_task_file_name='deployment.py',
    app_task_var_name_tpl='destroy_{snake_app_name}',
    upstreams=[ensure_project_tasks]
)


@python_task(
    name='fastapp',
    group=project_add_group,
    upstreams=[
        register_local_module,
        register_container_module,
        register_image_module,
        register_deployment_module,
        register_test_module,
        register_load_test_module,
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
