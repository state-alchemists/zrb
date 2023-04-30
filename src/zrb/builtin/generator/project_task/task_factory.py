from typing import Any, List, Optional
from .._common.input import project_dir_input, app_name_input
from ....task.decorator import python_task
from ....task.task import Task
from ....helper import util
from ....helper.codemod.add_import_module import add_import_module
from ....helper.codemod.add_upstream_to_task import add_upstream_to_task
from ....helper.codemod.add_assert_resource import add_assert_resource
from ....helper.file.copy_tree import copy_tree
from ....helper.file.text import read_text_file_async, write_text_file_async
import os

current_dir = os.path.dirname(__file__)


def create_add_project_automation_task(
    upstreams: Optional[List[Task]] = None
) -> Task:
    @python_task(
        name='add-project-automation',
        inputs=[project_dir_input],
        upstreams=[] if upstreams is None else upstreams
    )
    async def _task(*args: Any, **kwargs: Any):
        task: Task = kwargs.get('_task')
        project_dir = kwargs.get('project_dir', '.')
        task.print_out('Create project automation modules if not exist')
        await _add_project_automation(project_dir)
    return _task


async def _add_project_automation(project_dir: str):
    if os.path.exists(os.path.join(project_dir, '_automate', '_project')):
        return
    await copy_tree(
        src=os.path.join(current_dir, 'template'),
        dst=project_dir
    )
    project_task_module_path = '_automate._project'
    zrb_init_path = os.path.join(project_dir, 'zrb_init.py')
    code = await read_text_file_async(zrb_init_path)
    import_alias = project_task_module_path.split('.')[-1]
    code = add_import_module(
        code=code,
        module_path=project_task_module_path,
        alias=import_alias
    )
    code = add_assert_resource(code, import_alias)
    await write_text_file_async(zrb_init_path, code)


def create_register_app_task(
    task_name: str,
    project_automation_file_name: str,
    project_automation_task_name: str,
    app_automation_file_name: str,
    app_automation_task_var_name_tpl: str,
    upstreams: Optional[List[Task]] = None,
):
    @python_task(
        name=task_name,
        inputs=[project_dir_input, app_name_input],
        upstreams=[] if upstreams is None else upstreams
    )
    async def _task(*args: Any, **kwargs: Any):
        task: Task = kwargs.get('_task')
        project_dir = kwargs.get('project_dir', '.')
        app_name = kwargs.get('app_name')
        snake_app_name = util.to_snake_case(app_name)
        abs_app_automation_file_name = os.path.join(
            project_dir, '_automate', snake_app_name, app_automation_file_name
        )
        app_automation_task_var_name = app_automation_task_var_name_tpl.format(
            snake_app_name=snake_app_name
        )
        project_automation_dir = os.path.join(
            project_dir, '_automate', '_project'
        )
        project_automation_path = os.path.join(
            project_automation_dir, f'{project_automation_file_name}'
        )
        upstream_task_rel_file_path = os.path.relpath(
            abs_app_automation_file_name, project_automation_path
        )
        # normalize `..` parts
        upstream_module_parts = [
            part if part != '..' else ''
            for part in upstream_task_rel_file_path.split(os.path.sep)
        ]
        # remove .py extenstion
        last_part = upstream_module_parts[-1]
        upstream_module_parts[-1] = os.path.splitext(last_part)[0]
        # turn into module path
        upstream_module_path = '.'.join(upstream_module_parts)
        task.print_out(
            f'Add {app_automation_task_var_name} to project automation'
        )
        code = await read_text_file_async(project_automation_path)
        code = add_import_module(
            code=code,
            module_path=upstream_module_path,
            resource=app_automation_task_var_name
        )
        code = add_upstream_to_task(
            code, project_automation_task_name, app_automation_task_var_name
        )
        await write_text_file_async(project_automation_path, code)
    return _task
