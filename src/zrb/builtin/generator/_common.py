from typing import List
from ...helper.middlewares.replacement import (
    Replacement, ReplacementMiddleware
)
from ...task_input.str_input import StrInput
from ...task_input.int_input import IntInput
from ...helper import util
from ...helper.accessories.name import get_random_name
from ...helper.codemod.add_assert_resource import add_assert_resource
from ...helper.codemod.add_import_module import add_import_module
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


def get_automation_file(zrb_project_dir: str, automation_name: str) -> str:
    snake_automation_name = util.to_snake_case(automation_name)
    return os.path.join(
        zrb_project_dir,
        '_automate',
        f'{snake_automation_name}.py'
    )


def validate_automation_name(project_dir: str, automation_name: str):
    automation_file = get_automation_file(project_dir, automation_name)
    if os.path.isfile(automation_file):
        raise Exception(f'File already exists: {automation_file}')


def register_task(project_dir: str, task_name: str):
    task_module_path = '.'.join([
        '_automate',
        util.to_snake_case(task_name)
    ])
    zrb_init_path = os.path.join(project_dir, 'zrb_init.py')
    with open(zrb_init_path, 'r') as f:
        code = f.read()
        import_alias = task_module_path.split('.')[-1]
        code = add_import_module(
            code=code,
            module_path=task_module_path,
            alias=import_alias
        )
        code = add_assert_resource(code, import_alias)
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
