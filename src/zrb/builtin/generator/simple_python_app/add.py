from typing import Any
from ..._group import project_add_group
from ....task.task import Task
from ....task.decorator import python_task
from ....task_input.str_input import StrInput
from ....task.resource_maker import ResourceMaker
from ....runner import runner
from .._common import (
    project_dir_input, app_name_input, http_port_input, validate_project_dir,
    get_automation_module_name, validate_automation_name, register_module,
    get_default_task_replacements, get_default_task_replacement_middlewares,
    new_app_scaffold_lock
)
from ..project_task.add import (
    add_project_automation, register_project_upstream
)
from ....helper import util

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
    inputs=[project_dir_input, app_name_input],
    upstreams=[copy_resource]
)
def add_project_task(*args: Any, **kwargs: Any):
    project_dir = kwargs.get('project_dir', '.')
    add_project_automation(project_dir)


@python_task(
    name='register-start',
    inputs=[project_dir_input, app_name_input],
    upstreams=[add_project_task]
)
def register_start(*args: Any, **kwargs: Any):
    project_dir = kwargs.get('project_dir', '.')
    app_name = kwargs.get('app_name')
    snake_app_name = util.to_snake_case(app_name)
    file_name = os.path.join(
        project_dir, '_automate', f'{snake_app_name}.py'
    )
    register_project_upstream(
        project_dir=project_dir,
        project_automation_file='start_project.py',
        project_automation_task_name='start',
        upstream_task_file=file_name,
        upstream_task_var=f'start_{snake_app_name}'
    )


@python_task(
    name='register-start-container',
    inputs=[project_dir_input, app_name_input],
    upstreams=[add_project_task]
)
def register_start_container(*args: Any, **kwargs: Any):
    project_dir = kwargs.get('project_dir', '.')
    app_name = kwargs.get('app_name')
    snake_app_name = util.to_snake_case(app_name)
    file_name = os.path.join(
        project_dir, '_automate', f'{snake_app_name}_container.py'
    )
    register_project_upstream(
        project_dir=project_dir,
        project_automation_file='start_project_containers.py',
        project_automation_task_name='start-containers',
        upstream_task_file=file_name,
        upstream_task_var=f'start_{snake_app_name}_container'
    )


@python_task(
    name='register-stop-container',
    inputs=[project_dir_input, app_name_input],
    upstreams=[add_project_task]
)
def register_stop_container(*args: Any, **kwargs: Any):
    project_dir = kwargs.get('project_dir', '.')
    app_name = kwargs.get('app_name')
    snake_app_name = util.to_snake_case(app_name)
    file_name = os.path.join(
        project_dir, '_automate', f'{snake_app_name}_container.py'
    )
    register_project_upstream(
        project_dir=project_dir,
        project_automation_file='stop_project_containers.py',
        project_automation_task_name='stop-containers',
        upstream_task_file=file_name,
        upstream_task_var=f'stop_{snake_app_name}_container'
    )


@python_task(
    name='register-remove-container',
    inputs=[project_dir_input, app_name_input],
    upstreams=[add_project_task]
)
def register_remove_container(*args: Any, **kwargs: Any):
    project_dir = kwargs.get('project_dir', '.')
    app_name = kwargs.get('app_name')
    snake_app_name = util.to_snake_case(app_name)
    file_name = os.path.join(
        project_dir, '_automate', f'{snake_app_name}_container.py'
    )
    register_project_upstream(
        project_dir=project_dir,
        project_automation_file='remove_project_containers.py',
        project_automation_task_name='remove-containers',
        upstream_task_file=file_name,
        upstream_task_var=f'remove_{snake_app_name}_container'
    )


@python_task(
    name='register-push-image',
    inputs=[project_dir_input, app_name_input],
    upstreams=[add_project_task]
)
def register_push_image(*args: Any, **kwargs: Any):
    project_dir = kwargs.get('project_dir', '.')
    app_name = kwargs.get('app_name')
    snake_app_name = util.to_snake_case(app_name)
    file_name = os.path.join(
        project_dir, '_automate', f'{snake_app_name}_container.py'
    )
    register_project_upstream(
        project_dir=project_dir,
        project_automation_file='push_project_images.py',
        project_automation_task_name='push-images',
        upstream_task_file=file_name,
        upstream_task_var=f'push_{snake_app_name}_image'
    )


@python_task(
    name='register-build-image',
    inputs=[project_dir_input, app_name_input],
    upstreams=[add_project_task]
)
def register_build_image(*args: Any, **kwargs: Any):
    project_dir = kwargs.get('project_dir', '.')
    app_name = kwargs.get('app_name')
    snake_app_name = util.to_snake_case(app_name)
    file_name = os.path.join(
        project_dir, '_automate', f'{snake_app_name}_container.py'
    )
    register_project_upstream(
        project_dir=project_dir,
        project_automation_file='build_project_images.py',
        project_automation_task_name='build-images',
        upstream_task_file=file_name,
        upstream_task_var=f'build_{snake_app_name}_image'
    )


register_task = Task(
    name='register-tasks',
    upstreams=[
        register_start,
        register_start_container,
        register_stop_container,
        register_remove_container,
        register_build_image,
        register_push_image
    ]
)


@python_task(
    name='simple-python-app',
    group=project_add_group,
    inputs=[project_dir_input, app_name_input],
    upstreams=[register_task],
    runner=runner
)
def add_simple_python_app(*args: Any, **kwargs: Any):
    task: Task = kwargs.get('_task')
    project_dir = kwargs.get('project_dir')
    app_name = kwargs.get('app_name')
    task.print_out(f'Register app: {app_name}')
    register_module(
        project_dir, get_automation_module_name(app_name)
    )
    register_module(
        project_dir, get_automation_module_name(f'{app_name}_container')
    )

