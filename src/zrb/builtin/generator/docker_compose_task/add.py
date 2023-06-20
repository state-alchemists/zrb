from typing import Any
from ..._group import project_add_group
from ....task.task import Task
from ....task.decorator import python_task
from ....task_input.str_input import StrInput
from ....task.resource_maker import ResourceMaker
from ....runner import runner
from .._common.input import (
   project_dir_input, task_name_input, http_port_input, env_prefix_input
)
from .._common.helper import validate_project_dir, create_register_task_module
from .._common.lock import new_task_lock
from ....helper import util

import os

current_dir = os.path.dirname(__file__)

###############################################################################
# Task Definitions
###############################################################################


@python_task(
    name='validate',
    inputs=[
        project_dir_input,
        task_name_input
    ],
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
    source_dir = os.path.join(
        project_dir, 'src', f'{util.to_kebab_case(task_name)}'
    )
    if os.path.exists(source_dir):
        raise Exception(f'Source already exists: {source_dir}')


copy_resource = ResourceMaker(
    name='copy-resource',
    inputs=[
        project_dir_input,
        task_name_input,
        http_port_input,
        StrInput(
            name='compose-command',
            description='Compose command (e.g., up, down, start, remove, etc)',
            prompt='Compose command (e.g., up, down, start, remove, etc)',
            default='up'
        ),
        env_prefix_input,
    ],
    upstreams=[validate],
    replacements={
        'taskName': '{{input.task_name}}',
        'httpPort': '{{util.coalesce(input.http_port, "3000")}}',
        'composeCommand': '{{ util.coalesce(input.compose_command, "up") }}',
        'ENV_PREFIX': '{{ util.coalesce(input.env_prefix, "MY").upper() }}',
    },
    template_path=os.path.join(current_dir, 'template'),
    destination_path='{{ input.project_dir }}',
    locks=[new_task_lock]
)

register_task_module = create_register_task_module(
    upstreams=[copy_resource]
)


@python_task(
    name='docker-compose-task',
    group=project_add_group,
    upstreams=[register_task_module],
    runner=runner
)
async def add_docker_compose_task(*args: Any, **kwargs: Any):
    task: Task = kwargs.get('_task')
    task.print_out('Success')
