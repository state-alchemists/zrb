from typing import Any
from zrb.builtin import group
from zrb import Task, python_task, ResourceMaker, runner
from zrb.helper import util
from zrb.builtin.generator import (
    task_input, task_factory, helper, project_task_factory as ptask_factory
)

import os

CURRENT_DIR = os.path.dirname(__file__)
SNAKE_APP_NAME_TPL = '{{util.to_snake_case(input.app_name)}}'

###############################################################################
# Task Definitions
###############################################################################


@python_task(
    name='validate',
    inputs=[
        task_input.project_dir_input,
        task_input.app_name_input
    ],
)
async def validate(*args: Any, **kwargs: Any):
    project_dir = kwargs.get('project_dir')
    helper.validate_existing_project_dir(project_dir)
    app_name = kwargs.get('app_name')
    helper.validate_inexisting_automation(project_dir, app_name)
    source_dir = os.path.join(
        project_dir, 'src', f'{util.to_kebab_case(app_name)}'
    )
    if os.path.exists(source_dir):
        raise Exception(f'Source already exists: {source_dir}')


copy_resource = ResourceMaker(
    name='copy-resource',
    inputs=[
        task_input.project_dir_input,
        task_input.app_name_input,
        task_input.app_image_name_input,
        task_input.http_port_input,
        task_input.env_prefix_input,
    ],
    upstreams=[validate],
    replacements={
        'zrbAppName': '{{input.app_name}}',
        'zrbAppHttpPort': '{{util.coalesce(input.http_port, "3000")}}',
        'ZRB_ENV_PREFIX': '{{util.coalesce(input.env_prefix, "MY").upper()}}',
        'zrb-app-image-name': '{{input.app_image_name}}'
    },
    template_path=os.path.join(CURRENT_DIR, 'template'),
    destination_path='{{ input.project_dir }}',
    excludes=[
        '*/deployment/venv',
        '*/__pycache__',
    ]
)

register_local_module = task_factory.create_register_module(
    module_path=f'_automate.{SNAKE_APP_NAME_TPL}.local',
    alias=f'{SNAKE_APP_NAME_TPL}_local',
    inputs=[task_input.app_name_input],
    upstreams=[copy_resource]
)

register_container_module = task_factory.create_register_module(
    module_path=f'_automate.{SNAKE_APP_NAME_TPL}.container',
    alias=f'{SNAKE_APP_NAME_TPL}_container',
    inputs=[task_input.app_name_input],
    upstreams=[register_local_module]
)

register_image_module = task_factory.create_register_module(
    module_path=f'_automate.{SNAKE_APP_NAME_TPL}.image',
    alias=f'{SNAKE_APP_NAME_TPL}_image',
    inputs=[task_input.app_name_input],
    upstreams=[register_container_module]
)

register_deployment_module = task_factory.create_register_module(
    module_path=f'_automate.{SNAKE_APP_NAME_TPL}.deployment',
    alias=f'{SNAKE_APP_NAME_TPL}_deployment',
    inputs=[task_input.app_name_input],
    upstreams=[register_image_module]
)

ensure_project_tasks = ptask_factory.create_ensure_project_tasks(
    upstreams=[copy_resource]
)

add_start = ptask_factory.create_add_start_upstream(
    upstream_module=f'_automate.{SNAKE_APP_NAME_TPL}.local',
    upstream_task_var=f'start_{SNAKE_APP_NAME_TPL}',
    upstreams=[ensure_project_tasks],
    inputs=[task_input.app_name_input]
)

add_start_container = ptask_factory.create_add_start_containers_upstream(
    upstream_module=f'_automate.{SNAKE_APP_NAME_TPL}.container',
    upstream_task_var=f'start_{SNAKE_APP_NAME_TPL}_container',
    upstreams=[ensure_project_tasks],
    inputs=[task_input.app_name_input]
)

add_stop_container = ptask_factory.create_add_stop_containers_upstream(
    upstream_module=f'_automate.{SNAKE_APP_NAME_TPL}.container',
    upstream_task_var=f'stop_{SNAKE_APP_NAME_TPL}_container',
    upstreams=[ensure_project_tasks],
    inputs=[task_input.app_name_input]
)

add_remove_container = ptask_factory.create_add_remove_containers_upstream(
    upstream_module=f'_automate.{SNAKE_APP_NAME_TPL}.container',
    upstream_task_var=f'remove_{SNAKE_APP_NAME_TPL}_container',
    upstreams=[ensure_project_tasks],
    inputs=[task_input.app_name_input]
)

add_build_image = ptask_factory.create_add_build_images_upstream(
    upstream_module=f'_automate.{SNAKE_APP_NAME_TPL}.image',
    upstream_task_var=f'build_{SNAKE_APP_NAME_TPL}_image',
    upstreams=[ensure_project_tasks],
    inputs=[task_input.app_name_input]
)

add_push_image = ptask_factory.create_add_push_images_upstream(
    upstream_module=f'_automate.{SNAKE_APP_NAME_TPL}.image',
    upstream_task_var=f'push_{SNAKE_APP_NAME_TPL}_image',
    upstreams=[ensure_project_tasks],
    inputs=[task_input.app_name_input]
)

add_deploy = ptask_factory.create_add_deploy_upstream(
    upstream_module=f'_automate.{SNAKE_APP_NAME_TPL}.deployment',
    upstream_task_var=f'deploy_{SNAKE_APP_NAME_TPL}',
    upstreams=[ensure_project_tasks],
    inputs=[task_input.app_name_input]
)

add_destroy = ptask_factory.create_add_destroy_upstream(
    upstream_module=f'_automate.{SNAKE_APP_NAME_TPL}.deployment',
    upstream_task_var=f'destroy_{SNAKE_APP_NAME_TPL}',
    upstreams=[ensure_project_tasks],
    inputs=[task_input.app_name_input]
)


@python_task(
    name='simple-python-app',
    group=group.project_add_group,
    upstreams=[
        register_local_module,
        register_container_module,
        register_image_module,
        register_deployment_module,
        add_start,
        add_start_container,
        add_stop_container,
        add_remove_container,
        add_build_image,
        add_push_image,
        add_deploy,
        add_destroy
    ],
    runner=runner
)
async def add_simple_python_app(*args: Any, **kwargs: Any):
    task: Task = kwargs.get('_task')
    task.print_out('Success')
