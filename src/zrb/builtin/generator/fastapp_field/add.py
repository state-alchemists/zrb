from typing import Any
from ..._group import project_add_group
from ....task.task import Task
from ....task.decorator import python_task
from ....runner import runner
from .._common.input import (
    project_dir_input, app_name_input, module_name_input, entity_name_input,
    column_name_input, column_type_input
)
from .._common.helper import validate_project_dir
from ....helper import util
from ....helper.codemod.add_property_to_class import add_property_to_class
from ....helper.codemod.add_key_value_to_dict import add_key_value_to_dict
from ....helper.file.text import read_text_file_async, write_text_file_async

import asyncio
import os

current_dir = os.path.dirname(__file__)


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
    source_dir = os.path.join(
        project_dir, 'src', f'{util.to_kebab_case(app_name)}'
    )
    if not os.path.exists(source_dir):
        raise Exception(f'Source does not exist: {source_dir}')
    module_path = os.path.join(source_dir, 'module', snake_module_name)
    if os.path.exists(module_path):
        raise Exception(f'Module directory already exists: {module_path}')
    entity_path = os.path.join(module_path, 'entity', snake_entity_name)
    if os.path.exists(entity_path):
        raise Exception(f'Entity directory already exists: {entity_path}')


@python_task(
    name='fastapp-field',
    group=project_add_group,
    inputs=[
        project_dir_input,
        app_name_input,
        module_name_input,
        entity_name_input,
        column_name_input,
        column_type_input,
    ],
    upstreams=[
        validate,
    ],
    runner=runner
)
async def add_fastapp_field(*args: Any, **kwargs: Any):
    task: Task = kwargs.get('_task')
    project_dir = kwargs.get('project_dir', '.')
    app_name = kwargs.get('app_name')
    module_name = kwargs.get('module_name')
    entity_name = kwargs.get('entity_name')
    column_name = kwargs.get('column_name')
    column_type = kwargs.get('column_name')
    kebab_app_name = util.to_kebab_case(app_name)
    snake_module_name = util.to_snake_case(module_name)
    snake_entity_name = util.to_snake_case(entity_name)
    pascal_entity_name = util.to_pascal_case(entity_name)
    snake_column_name = util.to_snake_case(column_name)
    await asyncio.gather(
        asyncio.create_task(add_column_to_test(
            task, project_dir, kebab_app_name, snake_module_name,
            snake_entity_name, snake_column_name, column_type
        )),
        asyncio.create_task(add_column_to_schema(
            task, project_dir, kebab_app_name, snake_module_name,
            snake_entity_name, pascal_entity_name, snake_column_name,
            column_type
        )),
        asyncio.create_task(add_column_to_repo(
            task, project_dir, kebab_app_name, snake_module_name,
            snake_entity_name, pascal_entity_name, snake_column_name,
            column_type
        )),
    )
    task.print_out('Success')


async def add_column_to_test(
    task: Task,
    project_dir: str,
    kebab_app_name: str,
    snake_module_name: str,
    snake_entity_name: str,
    snake_column_name: str,
    column_type: str
):
    test_file_path = os.path.join(
        project_dir, 'src', kebab_app_name, 'test', snake_module_name,
        f'test_{snake_entity_name}.py'
    )
    task.print_out(f'Read code from: {test_file_path}')
    code = await read_text_file_async(test_file_path)
    task.print_out(
        f'Add column "{snake_column_name}" to the test'
    )
    dict_names = [
        'inserted_success_data', 'to_be_updated_success_data',
        'updated_success_data', 'to_be_deleted_success_data'
    ]
    for dict_name in dict_names:
        code = add_key_value_to_dict(
            code=code,
            dict_name=dict_name,
            key=f"'{snake_column_name}'",
            value="''"
        )
    task.print_out(f'Write modified code to: {test_file_path}')
    await write_text_file_async(test_file_path, code)


async def add_column_to_schema(
    task: Task,
    project_dir: str,
    kebab_app_name: str,
    snake_module_name: str,
    snake_entity_name: str,
    pascal_entity_name: str,
    snake_column_name: str,
    column_type: str
):
    schema_file_path = os.path.join(
        project_dir, 'src', kebab_app_name, 'src', 'module', snake_module_name,
        'schema', f'{snake_entity_name}.py'
    )
    task.print_out(f'Read code from: {schema_file_path}')
    code = await read_text_file_async(schema_file_path)
    task.print_out(
        f'Add column "{snake_column_name}" to the schema'
    )
    code = add_property_to_class(
        code=code,
        class_name=f'{pascal_entity_name}Data',
        property_name=snake_column_name,
        property_type='str'
    )
    task.print_out(f'Write modified code to: {schema_file_path}')
    await write_text_file_async(schema_file_path, code)


async def add_column_to_repo(
    task: Task,
    project_dir: str,
    kebab_app_name: str,
    snake_module_name: str,
    snake_entity_name: str,
    pascal_entity_name: str,
    snake_column_name: str,
    column_type: str
):
    repo_file_path = os.path.join(
        project_dir, 'src', kebab_app_name, 'src', 'module', snake_module_name,
        'entity', snake_entity_name, 'repo.py'
    )
    task.print_out(f'Read code from: {repo_file_path}')
    code = await read_text_file_async(repo_file_path)
    task.print_out(
        f'Add column "{snake_column_name}" to the repo'
    )
    code = add_property_to_class(
        code=code,
        class_name=f'DBEntity{pascal_entity_name}',
        property_name=snake_column_name,
        property_type='Column',
        property_value='Column(String)'
    )
    task.print_out(f'Write modified code to: {repo_file_path}')
    await write_text_file_async(repo_file_path, code)
