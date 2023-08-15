from typing import Any, List, Optional
from ....task.decorator import python_task
from ....task.task import Task
from ....helper.codemod.add_assert_resource import add_assert_resource
from ....helper.codemod.add_import_module import add_import_module
from ....helper.file.text import read_text_file_async, write_text_file_async
from ....helper import util
from .input import project_dir_input, task_name_input, app_name_input
import os


def validate_existing_project_dir(project_dir: str):
    if not os.path.isfile(os.path.join(project_dir, 'zrb_init.py')):
        raise Exception(f'Not a project: {project_dir}')


def validate_inexisting_automation(project_dir: str, automation_name: str):
    validate_inexisting_automation_package(project_dir, automation_name)
    validate_inexisting_automation_module(project_dir, automation_name)


def validate_inexisting_automation_package(
    project_dir: str, package_name: str
):
    package_dir = os.path.join(
        project_dir, '_automate', f'{util.to_snake_case(package_name)}'
    )
    if os.path.exists(package_dir):
        raise Exception(f'Automation package already exists: {package_dir}')


def validate_inexisting_automation_module(project_dir: str, module_name: str):
    module_file = os.path.join(
        project_dir, '_automate', f'{util.to_snake_case(module_name)}.py'
    )
    if os.path.exists(module_file):
        raise Exception(f'Automation module already exists: {module_file}')


def create_register_task_module(
    upstreams: Optional[List[Task]] = None
) -> Task:
    @python_task(
        name='register-task-module',
        inputs=[project_dir_input, task_name_input],
        upstreams=[] if upstreams is None else upstreams
    )
    async def task(*args: Any, **kwargs: Any):
        task: Task = kwargs.get('_task')
        project_dir = kwargs.get('project_dir')
        validate_existing_project_dir(project_dir)
        task_name = kwargs.get('task_name')
        snake_task_name = util.to_snake_case(task_name)
        task.print_out(f'Register module: _automate.{snake_task_name}')
        await register_module_to_project(
            project_dir=project_dir,
            module_name='.'.join([
                '_automate', util.to_snake_case(snake_task_name)
            ])
        )
    return task


def create_register_app_module(
    module: str, upstreams: Optional[List[Task]] = None
) -> Task:
    @python_task(
        name=f'register-{module}',
        inputs=[project_dir_input, app_name_input],
        upstreams=[] if upstreams is None else upstreams
    )
    async def task(*args: Any, **kwargs: Any):
        task: Task = kwargs.get('_task')
        project_dir = kwargs.get('project_dir')
        validate_existing_project_dir(project_dir)
        app_name = kwargs.get('app_name')
        snake_app_name = util.to_snake_case(app_name)
        task.print_out(f'Register module: _automate.{snake_app_name}.{module}')
        await register_module_to_project(
            project_dir=project_dir,
            module_name='.'.join([
                '_automate', snake_app_name, module
            ]),
            alias=f'{snake_app_name}_{module}'
        )
    return task


async def register_module_to_project(
    project_dir: str, module_name: str, alias: Optional[str] = None
):
    zrb_init_path = os.path.join(project_dir, 'zrb_init.py')
    code = await read_text_file_async(zrb_init_path)
    if alias is None:
        alias = module_name.split('.')[-1]
    code = add_import_module(
        code=code,
        module_path=module_name,
        alias=alias
    )
    code = add_assert_resource(code, alias)
    await write_text_file_async(zrb_init_path, code)
    return True
