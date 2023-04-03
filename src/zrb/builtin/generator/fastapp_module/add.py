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
from ....helper.codemod.add_import_module import add_import_module
from ....helper.codemod.add_function_call import add_function_call

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


@python_task(
    name='register-module',
    inputs=[project_dir_input, app_name_input, module_name_input],
    upstreams=[copy_resource]
)
def register_module(*args: Any, **kwargs: Any):
    task: Task = kwargs.get('_task')
    project_dir = kwargs.get('project_dir', '.')
    app_name = kwargs.get('app_name')
    module_name = kwargs.get('module_name')
    kebab_app_name = util.to_kebab_case(app_name)
    snake_module_name = util.to_snake_case(module_name)
    import_module_path = '.'.join([
        'module', snake_module_name
    ])
    function_name = f'register_{snake_module_name}'
    main_file_path = os.path.join(
        project_dir, 'src', kebab_app_name, 'src', 'main.py'
    )
    task.print_out(f'Read code from: {main_file_path}')
    with open(main_file_path, 'r') as f:
        code = f.read()
        task.print_out(
            f'Add import "{function_name}" from "{import_module_path}" ' +
            'to the code'
        )
        code = add_import_module(
            code=code,
            module_path=import_module_path,
            resource=function_name
        )
        task.print_out(
            f'Add "{function_name}" call to the code'
        )
        code = add_function_call(
            code=code,
            function_name=function_name,
            parameters=[]
        )
    task.print_out(f'Write modified code to: {main_file_path}')
    with open(main_file_path, 'w') as f:
        f.write(code)
    task.print_out('👌')


@python_task(
    name='create-automation-config',
    inputs=[project_dir_input, app_name_input, module_name_input],
    upstreams=[copy_resource]
)
def create_automation_config(*args: Any, **kwargs: Any):
    pass


# TODO: add env to template.env
# TODO: add env to module_enabled.env
# TODO: add env to module_disabled.env
# TODO: create service in docker compose
# TODO: create runner for local microservices


@python_task(
    name='fastapp-module',
    group=project_add_group,
    upstreams=[
        register_module,
        create_automation_config,
    ],
    runner=runner
)
async def add_fastapp_module(*args: Any, **kwargs: Any):
    task: Task = kwargs.get('_task')
    task.print_out('Success')
