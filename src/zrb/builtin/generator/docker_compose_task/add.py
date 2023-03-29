from typing import Any
from ..._group import project_add_group
from ....task.task import Task
from ....task.decorator import python_task
from ....task_input.str_input import StrInput
from ....task.resource_maker import ResourceMaker
from ....runner import runner
from .._common import (
    default_task_inputs, http_port_input, env_prefix_input,
    validate_project_dir, create_register_task_module,
    get_default_task_replacements, get_default_task_replacement_middlewares,
    new_task_scaffold_lock
)
from ....helper import util

import os

# Common definitions

current_dir = os.path.dirname(__file__)


@python_task(
    name='validate',
    inputs=default_task_inputs,
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


replacements = get_default_task_replacements()
replacements.update({
    'httpPort': '{{util.coalesce(input.http_port, "3000")}}',
    'composeCommand': '{{ util.coalesce(input.compose_command, "up") }}',
    'ENV_PREFIX': '{{ util.coalesce(input.env_prefix, "MY").upper() }}',
})
copy_resource = ResourceMaker(
    name='copy-resource',
    inputs=default_task_inputs + [
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
    replacements=replacements,
    replacement_middlewares=get_default_task_replacement_middlewares(),
    template_path=os.path.join(current_dir, 'template'),
    destination_path='{{ input.project_dir }}',
    scaffold_locks=[new_task_scaffold_lock]
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
