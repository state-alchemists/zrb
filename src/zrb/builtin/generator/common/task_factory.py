import os

from zrb.builtin.generator.common.helper import (
    register_module_to_project,
    validate_existing_project_dir,
)
from zrb.builtin.generator.common.task_input import project_dir_input
from zrb.helper.codemod.add_import_module import add_import_module
from zrb.helper.codemod.add_upstream_to_task import add_upstream_to_task
from zrb.helper.file.text import read_text_file_async, write_text_file_async
from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Any, List, Optional
from zrb.task.any_task import AnyTask
from zrb.task.decorator import python_task
from zrb.task.task import Task
from zrb.task_input.any_input import AnyInput


@typechecked
def create_register_module(
    module_path: str,
    inputs: Optional[List[AnyInput]] = None,
    upstreams: Optional[List[AnyTask]] = None,
    alias: Optional[str] = None,
) -> Task:
    @python_task(
        name="register-module",
        inputs=[project_dir_input] + inputs if inputs is not None else [],
        upstreams=upstreams if upstreams is not None else [],
    )
    async def register_module(*args: Any, **kwargs: Any):
        task: Task = kwargs.get("_task")
        project_dir = kwargs.get("project_dir")
        validate_existing_project_dir(project_dir)
        rendered_module_path = task.render_str(module_path)
        rendered_alias: Optional[str] = None
        if alias is not None:
            rendered_alias = task.render_str(alias)
        task.print_out(
            f"Register module: {rendered_module_path}" + f" as {rendered_alias}"
            if rendered_alias is not None
            else ""
        )
        await register_module_to_project(
            project_dir=project_dir,
            module_path=rendered_module_path,
            alias=rendered_alias,
        )

    return register_module


@typechecked
def create_add_upstream(
    task_file_name: str,
    task_name: str,
    upstream_module: str,
    upstream_task_var: str,
    inputs: Optional[List[AnyInput]] = None,
    upstreams: Optional[List[AnyTask]] = None,
) -> Task:
    @python_task(
        name="register-upstream",
        inputs=[project_dir_input] + inputs if inputs is not None else [],
        upstreams=upstreams if upstreams is not None else [],
    )
    async def register_upstream(*args: Any, **kwargs: Any):
        task: Task = kwargs.get("_task")
        project_dir = kwargs.get("project_dir", ".")
        rendered_task_file_name = task.render_str(task_file_name)
        rendered_task_name = task.render_str(task_name)
        rendered_upstream_module_path = task.render_str(upstream_module)
        rendered_upstream_task_var = task.render_str(upstream_task_var)
        if not os.path.isabs(rendered_task_file_name):
            rendered_task_file_name = os.path.join(project_dir, rendered_task_file_name)
        code = await read_text_file_async(rendered_task_file_name)
        code = add_import_module(
            code=code,
            module_path=rendered_upstream_module_path,
            resource=rendered_upstream_task_var,
        )
        code = add_upstream_to_task(
            code, rendered_task_name, rendered_upstream_task_var
        )
        await write_text_file_async(rendered_task_file_name, code)

    return register_upstream
