from typing import Any, Optional
from .._group import task_group
from ...task_input.str_input import StrInput
from ...task.resource_maker import ResourceMaker
from ...task.task import Task
from ...runner import runner
from ...helper.render_data.replacement_template import (
    Replacement
)
from ...helper.common import to_snake_case, coalesce
from ...helper.codemod.add_import_module import add_import_module
from ...helper.codemod.add_assert_module import add_assert_module

import os

# Common definitions

current_dir = os.path.dirname(__file__)

inputs = [
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
]

replacements = Replacement().add_key_val(
    key='taskDir',
    value='input.task_dir'
).add_transformed_key_val(Replacement.ALL)(
    key='taskName',
    value=[
        'input.task_name',
        'os.path.basename(input.task_dir)'
    ]
).get()


def is_path_inside(path, parent_path):
    # Normalize the paths to avoid inconsistencies due to
    # different separators, etc.
    path = os.path.normpath(path)
    parent_path = os.path.normpath(parent_path)

    # Split the paths into components
    path_components = path.split(os.sep)
    parent_path_components = parent_path.split(os.sep)

    # Check if all components of `path` match the corresponding
    # components of `parent_path`
    return all(a == b for a, b in zip(path_components, parent_path_components))


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
    snake_task_name = to_snake_case(coalesce(
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

task_validate_create = Task(
    name='task-validate-create',
    inputs=inputs,
    runner=_task_validate_create
)

task_copy_resource = ResourceMaker(
    name='task-copy-resource',
    inputs=inputs,
    upstreams=[task_validate_create],
    replacements=replacements,
    template_path=os.path.join(current_dir, 'task_template'),
    destination_path='{{input.task_dir}}',
    scaffold_locks=['{{input.task_dir}}']
)

task_create = Task(
    name='task',
    group=task_group,
    inputs=inputs,
    runner=_task_create,
    upstreams=[task_copy_resource]
)
runner.register(task_create)
