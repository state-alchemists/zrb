from typing import Any, List, Optional
from ...helper.middlewares.replacement import (
    Replacement, ReplacementMiddleware
)
from ...task.decorator import python_task
from ...task.task import Task
from ...task_input.str_input import StrInput
from ...task_input.int_input import IntInput
from ...helper.accessories.name import get_random_name
from ...helper.codemod.add_assert_resource import add_assert_resource
from ...helper.codemod.add_import_module import add_import_module
from ...helper import util
from ...helper.middlewares.replacement import (
    add_pascal_key, add_snake_key, add_camel_key,
    add_kebab_key, add_human_readable_key
)
import os


project_dir_input = StrInput(
    name='project-dir',
    shortcut='d',
    prompt='Project directory',
    default='.'
)

project_name_input = StrInput(
    name='project-name',
    shortcut='n',
    prompt='Project name (can be empty)',
    default=''
)

app_name_input = StrInput(
    name='app-name',
    shortcut='a',
    prompt='App name',
    default=get_random_name()
)

task_name_input = StrInput(
    name='task-name',
    shortcut='t',
    prompt='Task name',
    default=f'run-{get_random_name()}'
)
http_port_input = IntInput(
    name='http-port',
    shortcut='p',
    prompt='Port',
    default=8080
)

new_task_scaffold_lock = os.path.sep.join([
    '{{ os.path.join(input.project_dir, "_automate") }}',
    '{{ util.to_snake_case(input.task_name) }}.py'
])

new_app_scaffold_lock = os.path.sep.join([
    '{{ os.path.join(input.project_dir, "_automate") }}',
    '{{ util.to_snake_case(input.app_name) }}.py'
])


def validate_project_dir(project_dir: str):
    if not os.path.isfile(os.path.join(project_dir, 'zrb_init.py')):
        raise Exception(f'Not a project: {project_dir}')


def create_register_task_module(
    upstreams: Optional[List[Task]] = None
) -> Task:
    @python_task(
        name='register-task-module',
        inputs=[project_dir_input, task_name_input],
        upstreams=[] if upstreams is None else upstreams
    )
    def task(*args: Any, **kwargs: Any):
        task: Task = kwargs.get('_task')
        project_dir = kwargs.get('project_dir')
        validate_project_dir(project_dir)
        task_name = kwargs.get('task_name')
        task.print_out(f'Register module: _automate.{task_name}')
        register_module(
            project_dir=project_dir,
            module_name='.'.join([
                '_automate', util.to_snake_case(task_name)
            ])
        )
    return task


def create_register_local_app_module(
    upstreams: Optional[List[Task]] = None
) -> Task:
    return _create_register_app_module('local', upstreams)


def create_register_container_app_module(
    upstreams: Optional[List[Task]] = None
) -> Task:
    return _create_register_app_module('container', upstreams)


def create_register_deployment_app_module(
    upstreams: Optional[List[Task]] = None
) -> Task:
    return _create_register_app_module('deployment', upstreams)


def _create_register_app_module(
    module: str,
    upstreams: Optional[List[Task]] = None
) -> Task:
    @python_task(
        name='register-app-module',
        inputs=[project_dir_input, app_name_input],
        upstreams=[] if upstreams is None else upstreams
    )
    def task(*args: Any, **kwargs: Any):
        task: Task = kwargs.get('_task')
        project_dir = kwargs.get('project_dir')
        validate_project_dir(project_dir)
        app_name = kwargs.get('app_name')
        task.print_out(f'Register module: _automate.{app_name}.{module}')
        snake_app_name = util.to_snake_case(app_name)
        register_module(
            project_dir=project_dir,
            module_name='.'.join([
                '_automate', snake_app_name, module
            ]),
            alias=f'{snake_app_name}_{module}'
        )
    return task


def register_module(
    project_dir: str, module_name: str, alias: Optional[str] = None
):
    zrb_init_path = os.path.join(project_dir, 'zrb_init.py')
    with open(zrb_init_path, 'r') as f:
        code = f.read()
        if alias is None:
            alias = module_name.split('.')[-1]
        code = add_import_module(
            code=code,
            module_path=module_name,
            alias=alias
        )
        code = add_assert_resource(code, alias)
    with open(zrb_init_path, 'w') as f:
        f.write(code)
    return True


def get_default_task_replacements() -> Replacement:
    return {
        'taskName': '{{input.task_name}}',
        'appName': '{{input.app_name}}',
        'httpPort': '{{util.coalesce(input.http_port, "3000")}}',
    }


def get_default_task_replacement_middlewares() -> List[ReplacementMiddleware]:
    return [
        # task
        add_pascal_key('PascalTaskName', 'taskName'),
        add_camel_key('camelTaskName', 'taskName'),
        add_snake_key('snake_task_name', 'taskName'),
        add_kebab_key('kebab-task-name', 'taskName'),
        add_human_readable_key('human readable task name', 'taskName'),
        # app
        add_pascal_key('PascalAppName', 'appName'),
        add_camel_key('camelAppName', 'appName'),
        add_snake_key('snake_app_name', 'appName'),
        add_kebab_key('kebab-app-name', 'appName'),
        add_human_readable_key('human readable app name', 'appName'),
    ]

