from typing import Any
from ..._group import project_add_group
from ....task.task import Task
from ....task.decorator import python_task
from ....task.cmd_task import CmdTask
from ....task.resource_maker import ResourceMaker
from ....runner import runner
from ....helper import util
from ....helper.codemod.add_import_module import add_import_module
from ....helper.codemod.append_code_to_function import append_code_to_function
from ....helper.file.text import read_text_file_async, write_text_file_async
from .._common.input import (
    project_dir_input, app_name_input, module_name_input, entity_name_input,
    plural_entity_name_input, main_column_name_input
)
from .._common.helper import validate_project_dir
from .add_navigation import create_add_navigation_task

import asyncio
import os

current_dir = os.path.dirname(__file__)
codemod_dir = os.path.join(current_dir, 'nodejs', 'codemod')

###############################################################################
# Task Definitions
###############################################################################


@python_task(
    name='validate',
    inputs=[
        project_dir_input, app_name_input, module_name_input, entity_name_input
    ],
)
async def validate(*args: Any, **kwargs: Any):
    project_dir = kwargs.get('project_dir')
    validate_project_dir(project_dir)
    app_name = kwargs.get('app_name')
    module_name = kwargs.get('module_name')
    entity_name = kwargs.get('entity_name')
    snake_module_name = util.to_snake_case(module_name)
    snake_entity_name = util.to_snake_case(entity_name)
    automation_dir = os.path.join(
        project_dir, '_automate', util.to_snake_case(app_name)
    )
    if not os.path.exists(automation_dir):
        raise Exception(
            f'Automation directory does not exist: {automation_dir}'
        )
    app_dir = os.path.join(
        project_dir, 'src', f'{util.to_kebab_case(app_name)}'
    )
    if not os.path.exists(app_dir):
        raise Exception(f'App directory does not exist: {app_dir}')
    module_path = os.path.join(app_dir, 'src', 'module', snake_module_name)
    if not os.path.exists(module_path):
        raise Exception(f'Module directory does not exist: {module_path}')
    entity_path = os.path.join(module_path, 'entity', snake_entity_name)
    if os.path.exists(entity_path):
        raise Exception(f'Entity directory already exists: {entity_path}')


copy_resource = ResourceMaker(
    name='copy-resource',
    inputs=[
        project_dir_input,
        app_name_input,
        module_name_input,
        entity_name_input,
        plural_entity_name_input,
        main_column_name_input,
    ],
    upstreams=[validate],
    replacements={
        'appName': '{{input.app_name}}',
        'moduleName': '{{input.module_name}}',
        'entityName': '{{input.entity_name}}',
        'pluralEntityName': '{{input.plural_entity_name}}',
        'columnName': '{{input.column_name}}',
    },
    template_path=os.path.join(current_dir, 'template'),
    destination_path='{{ input.project_dir }}',
    excludes=[
        '*/__pycache__',
    ]
)


@python_task(
    name='register-crud',
    inputs=[
        project_dir_input,
        app_name_input,
        module_name_input,
        entity_name_input,
        plural_entity_name_input,
        main_column_name_input,
    ],
    upstreams=[
        copy_resource,
    ]
)
async def register_crud(*args: Any, **kwargs: Any):
    task: Task = kwargs.get('_task')
    project_dir = kwargs.get('project_dir', '.')
    app_name = kwargs.get('app_name')
    module_name = kwargs.get('module_name')
    entity_name = kwargs.get('entity_name')
    kebab_app_name = util.to_kebab_case(app_name)
    snake_module_name = util.to_snake_case(module_name)
    snake_entity_name = util.to_snake_case(entity_name)
    await asyncio.gather(
        asyncio.create_task(register_api(
            task, project_dir, kebab_app_name, snake_module_name,
            snake_entity_name
        )),
        asyncio.create_task(register_rpc(
            task, project_dir, kebab_app_name, snake_module_name,
            snake_entity_name
        )),
        asyncio.create_task(register_permission(
            task, project_dir, kebab_app_name, snake_module_name,
            snake_entity_name
        )),
    )


prepare_codemod = CmdTask(
    name='prepare-codemod',
    cwd=codemod_dir,
    cmd=[
        'npm install --save-dev',
        'node_modules/.bin/tsc'
    ]
)

add_navigation = create_add_navigation_task(
    upstreams=[
        copy_resource,
        prepare_codemod,
    ]
)


@python_task(
    name='fastapp-crud',
    group=project_add_group,
    upstreams=[
        register_crud,
        add_navigation
    ],
    runner=runner
)
async def add_fastapp_crud(*args: Any, **kwargs: Any):
    task: Task = kwargs.get('_task')
    task.print_out('Success')


###############################################################################
# Helper Definitions
###############################################################################


async def register_api(
    task: Task,
    project_dir: str,
    kebab_app_name: str,
    snake_module_name: str,
    snake_entity_name: str
):
    module_api_file_path = os.path.join(
        project_dir, 'src', kebab_app_name, 'src', 'module', snake_module_name,
        'api.py'
    )
    register_function_path = '.'.join([
        'module', snake_module_name, 'entity', snake_entity_name, 'api'
    ])
    register_function = f'register_{snake_entity_name}_api'
    task.print_out(f'Read code from: {module_api_file_path}')
    code = await read_text_file_async(module_api_file_path)
    task.print_out(
        f'Add import "register_api" as "{register_function}" ' +
        f'from "{register_function_path}" to the code'
    )
    code = add_import_module(
        code=code,
        module_path=register_function_path,
        resource='register_api',
        alias=register_function
    )
    task.print_out(f'Add "{register_function}" call to the code')
    code = append_code_to_function(
        code=code,
        function_name='register_api',
        new_code=f'{register_function}(logger, app, authorizer, rpc_caller, publisher)' # noqa
    )
    task.print_out(f'Write modified code to: {module_api_file_path}')
    await write_text_file_async(module_api_file_path, code)


async def register_rpc(
    task: Task,
    project_dir: str,
    kebab_app_name: str,
    snake_module_name: str,
    snake_entity_name: str
):
    module_rpc_file_path = os.path.join(
        project_dir, 'src', kebab_app_name, 'src', 'module', snake_module_name,
        'rpc.py'
    )
    register_function_path = '.'.join([
        'module', snake_module_name, 'entity', snake_entity_name, 'rpc'
    ])
    register_function = f'register_{snake_entity_name}_rpc'
    task.print_out(f'Read code from: {module_rpc_file_path}')
    code = await read_text_file_async(module_rpc_file_path)
    task.print_out(
        f'Add import "register_rpc" as "{register_function}" ' +
        f'from "{register_function_path}" to the code'
    )
    code = add_import_module(
        code=code,
        module_path=register_function_path,
        resource='register_rpc',
        alias=register_function
    )
    task.print_out(f'Add "{register_function}" call to the code')
    code = append_code_to_function(
        code=code,
        function_name='register_rpc',
        new_code=f'{register_function}(logger, rpc_server, rpc_caller, publisher)' # noqa
    )
    task.print_out(f'Write modified code to: {module_rpc_file_path}')
    await write_text_file_async(module_rpc_file_path, code)


async def register_permission(
    task: Task,
    project_dir: str,
    kebab_app_name: str,
    snake_module_name: str,
    snake_entity_name: str
):
    module_register_permission_file_path = os.path.join(
        project_dir, 'src', kebab_app_name, 'src', 'module', 'auth',
        'register_permission.py'
    )
    task.print_out(f'Read code from: {module_register_permission_file_path}')
    code = await read_text_file_async(module_register_permission_file_path)
    code = append_code_to_function(
        code=code,
        function_name='register_permission',
        new_code='\n'.join([
            'await ensure_entity_permission(',
            f"    module_name='{snake_module_name}', entity_name='{snake_entity_name}'", # noqa
            ')'
        ])
    )
    task.print_out(
        f'Add "ensure_entity_permission" call for {snake_entity_name} ' +
        'to the code'
    )
    task.print_out(
        f'Write modified code to: {module_register_permission_file_path}'
    )
    await write_text_file_async(module_register_permission_file_path, code)
