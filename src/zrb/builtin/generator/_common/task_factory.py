from typing import Any, List, Optional
from ....task.decorator import python_task
from ....task.task import Task
from ....task_input.task_input import Input
from .task_input import project_dir_input
from .helper import validate_existing_project_dir, register_module_to_project


def create_register_module(
    module_path: str,
    inputs: Optional[List[Input]] = None,
    upstreams: Optional[List[Task]] = None,
    alias: Optional[str] = None
) -> Task:
    @python_task(
        name='register-module',
        inputs=[project_dir_input] + inputs if inputs is not None else [],
        upstreams=upstreams if upstreams is not None else []
    )
    async def register_module(*args: Any, **kwargs: Any):
        task: Task = kwargs.get('_task')
        project_dir = kwargs.get('project_dir')
        validate_existing_project_dir(project_dir)
        rendered_module_path = task.render_str(module_path)
        rendered_alias: Optional[str] = None
        if alias is not None:
            rendered_alias = task.render_str(alias)
        task.print_out(
            f'Register module: {rendered_module_path}' +
            f' as {rendered_alias}' if rendered_alias is not None else ''
        )
        await register_module_to_project(
            project_dir=project_dir,
            module_path=rendered_module_path,
            alias=rendered_alias
        )
    return register_module
