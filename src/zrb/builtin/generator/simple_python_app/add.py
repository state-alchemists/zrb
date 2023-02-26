from typing import Any
from ..._group import project_add_group
from ....task.task import Task
from ....task.decorator import python_task
from ....task_input.str_input import StrInput
from ....task.resource_maker import ResourceMaker
from ....runner import runner
from .._common import (
    project_dir_input, app_name_input, http_port_input, validate_project_dir,
    validate_automation_name, register_task, get_default_task_replacements,
    get_default_task_replacement_middlewares, new_app_scaffold_lock
)

from ..project_task.add import add_default_project_task
import os

# Common definitions

current_dir = os.path.dirname(__file__)


@python_task(
    name='task-validate-create',
    inputs=[project_dir_input, app_name_input],
)
def validate(*args: Any, **kwargs: Any):
    project_dir = kwargs.get('project_dir')
    validate_project_dir(project_dir)
    app_name = kwargs.get(project_dir, 'app_name')
    validate_automation_name(project_dir, app_name)


replacements = get_default_task_replacements()
replacements.update({
    'ENV_PREFIX': '{{ util.coalesce(input.env_prefix, "MY").upper() }}'
})
copy_resource = ResourceMaker(
    name='copy-resource',
    inputs=[
        project_dir_input,
        app_name_input,
        http_port_input,
        StrInput(
            name='env-prefix', prompt='Env prefix', default='MY'
        ),
    ],
    upstreams=[validate],
    replacements=replacements,
    replacement_middlewares=get_default_task_replacement_middlewares(),
    template_path=os.path.join(current_dir, 'template'),
    destination_path='{{ input.project_dir }}',
    scaffold_locks=[new_app_scaffold_lock]
)


@python_task(
    name='add-project-task',
    inputs=[project_dir_input],
    upstreams=[copy_resource]
)
def add_project_task(*args: Any, **kwargs: Any):
    project_dir = kwargs.get('project_dir', '.')
    add_default_project_task(project_dir)


@python_task(
    name='simple-python-app',
    group=project_add_group,
    inputs=[project_dir_input, app_name_input],
    upstreams=[add_project_task],
    runner=runner
)
def add_simple_python_app(*args: Any, **kwargs: Any):
    task: Task = kwargs.get('_task')
    project_dir = kwargs.get('project_dir')
    validate_project_dir(project_dir)
    app_name = kwargs.get('app_name')
    task.print_out(f'Register app: {app_name}')
    register_task(project_dir, app_name)