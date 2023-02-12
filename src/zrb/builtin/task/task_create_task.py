from typing import Any, Optional
from .._group import task_group
from ...task_input.str_input import StrInput
from ...helper.middlewares.replacement import (
    coalesce, add_pascal_key, add_snake_key, add_camel_key,
    add_kebab_key, add_human_readable_key, add_base_name_key
)
from ...task.task import Task
from ...task.resource_maker import ResourceMaker
from ...runner import runner
from ...helper import util
from ...helper.codemod.add_import_module import add_import_module
from ...helper.codemod.add_assert_module import add_assert_module

import os

# Common definitions

current_dir = os.path.dirname(__file__)


def get_zrb_project_dir(project_dir: str) -> Optional[str]:
    if os.path.isfile(os.path.join(project_dir, 'zrb_init.py')):
        return project_dir
    new_project_dir = os.path.dirname(project_dir)
    if new_project_dir == project_dir:
        # No project found
        return None
    return get_zrb_project_dir(new_project_dir)


def _task_validate_create(*args: Any, **kwargs: Any):
    task: Task = kwargs['_task']
    input_map = task.get_input_map()
    task_dir = os.path.abspath(input_map.get('task_dir'))
    zrb_project_dir = get_zrb_project_dir(task_dir)
    if not zrb_project_dir:
        raise Exception(' '.join([
            f'Task directory: {task_dir}',
            'is not located in a project'
        ]))


def _task_create(*args: Any, **kwargs: Any):
    task_dir = os.path.abspath(kwargs.get('task_dir'))
    snake_task_name = util.to_snake_case(util.coalesce(
        kwargs.get('task_name'), os.path.basename(task_dir)
    ))
    zrb_project_dir = get_zrb_project_dir(task_dir)
    task_module_path = '.'.join(
        os.path.relpath(
            os.path.join(task_dir, snake_task_name),
            zrb_project_dir
        ).split(os.path.sep)
    )
    zrb_init_path = os.path.join(zrb_project_dir, 'zrb_init.py')
    with open(zrb_init_path, 'r') as f:
        code = f.read()
        code = add_import_module(code, task_module_path)
        code = add_assert_module(code, task_module_path)
    with open(zrb_init_path, 'w') as f:
        f.write(code)
    return True


# Task definitions

task_validate_create_task = Task(
    name='task-validate-create',
    inputs=[
        StrInput(
            name='task-dir',
            prompt='Task directory',
            default='myTask'
        )
    ],
    run=_task_validate_create
)

task_copy_resource_task = ResourceMaker(
    name='copy-resource',
    inputs=[
        StrInput(
            name='task-dir',
            prompt='Task directory',
            default='myTask'
        ),
        StrInput(
            name='task-name',
            prompt='Task name (can be empty)',
            default=''
        ),
    ],
    upstreams=[task_validate_create_task],
    replacements={
        'taskDir': '{{input.task_dir}}',
        'taskName': '{{input.task_name}}'
    },
    replacement_middlewares=[
        add_base_name_key('baseTaskDir', 'taskDir'),
        coalesce('taskName', ['baseTaskDir']),
        add_pascal_key('PascalTaskName', 'taskName'),
        add_camel_key('camelTaskName', 'taskName'),
        add_snake_key('snake_task_name', 'taskName'),
        add_kebab_key('kebab-task-name', 'taskName'),
        add_human_readable_key('human readable task name', 'taskName'),
    ],
    template_path=os.path.join(current_dir, 'task_template'),
    destination_path='{{input.task_dir}}',
    scaffold_locks=['{{input.task_dir}}']
)

task_create_task = Task(
    name='create',
    group=task_group,
    inputs=[
        StrInput(
            name='task-dir',
            prompt='Task directory',
            default='myTask'
        ),
        StrInput(
            name='task-name',
            prompt='Task name (can be empty)',
            default=''
        ),
    ],
    run=_task_create,
    upstreams=[task_copy_resource_task]
)
runner.register(task_create_task)
