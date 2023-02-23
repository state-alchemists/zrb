from typing import Any
from ...._group import project_add_group
from .....task_input.str_input import StrInput
from .....helper.middlewares.replacement import (
    add_pascal_key, add_snake_key, add_camel_key,
    add_kebab_key, add_human_readable_key
)
from .....task.task import Task
from .....task.resource_maker import ResourceMaker
from .....runner import runner
from .....helper import util
from .....helper.codemod.add_import_module import add_import_module
from .....helper.codemod.add_assert_module import add_assert_module

import os

# Common definitions

current_dir = os.path.dirname(__file__)


def validate_project_dir(project_dir: str):
    if not os.path.isfile(os.path.join(project_dir, 'zrb_init.py')):
        raise Exception(f'Not a project: {project_dir}')


def get_task_file(zrb_project_dir: str, task_name: str) -> str:
    snake_task_name = util.to_snake_case(task_name)
    return os.path.join(
        zrb_project_dir,
        '_automate',
        f'{snake_task_name}.py'
    )


def _validate(*args: Any, **kwargs: Any):
    project_dir = kwargs.get('project_dir')
    validate_project_dir(project_dir)
    task_name = kwargs.get(project_dir, 'task_name')
    task_file = get_task_file(project_dir, task_name)
    if os.path.isfile(task_file):
        raise Exception(f'File already exists: {task_file}')


def _create_task(*args: Any, **kwargs: Any):
    project_dir = kwargs.get('project_dir')
    validate_project_dir(project_dir)
    task_name = kwargs.get('task_name')
    task_module_path = '.'.join([
        '_automate',
        util.to_snake_case(task_name)
    ])
    zrb_init_path = os.path.join(project_dir, 'zrb_init.py')
    with open(zrb_init_path, 'r') as f:
        code = f.read()
        import_alias = task_module_path.split('.')[-1]
        code = add_import_module(code, task_module_path, import_alias)
        code = add_assert_module(code, import_alias)
    with open(zrb_init_path, 'w') as f:
        f.write(code)
    return True


project_dir_input = StrInput(
    name='project-dir', shortcut='d', prompt='Project directory', default='.'
)

task_name_input = StrInput(
    name='task-name',
    prompt='Task name',
    default='new_cmd_task'
)

# Task definitions

validate_task = Task(
    name='task-validate-create',
    inputs=[project_dir_input, task_name_input],
    run=_validate
)

copy_resource_task = ResourceMaker(
    name='copy-resource',
    inputs=[project_dir_input, task_name_input],
    upstreams=[validate_task],
    replacements={
        'taskName': '{{input.task_name}}'
    },
    replacement_middlewares=[
        add_pascal_key('PascalTaskName', 'taskName'),
        add_camel_key('camelTaskName', 'taskName'),
        add_snake_key('snake_task_name', 'taskName'),
        add_kebab_key('kebab-task-name', 'taskName'),
        add_human_readable_key('human readable task name', 'taskName'),
    ],
    template_path=os.path.join(current_dir, 'task_template'),
    destination_path='{{ os.path.join(input.project_dir, "_automate") }}',
    scaffold_locks=[
        os.path.sep.join([
            '{{ os.path.join(input.project_dir, "_automate") }}',
            '{{ util.to_snake_case(input.task_name) }}.py'
        ])
    ]
)

add_task = Task(
    name='cmd-task',
    group=project_add_group,
    inputs=[project_dir_input, task_name_input],
    run=_create_task,
    upstreams=[copy_resource_task]
)
runner.register(add_task)
