import os

from zrb.builtin.generator.common.task_factory import create_add_upstream
from zrb.builtin.generator.common.task_input import project_dir_input
from zrb.helper.codemod.add_assert_resource import add_assert_resource
from zrb.helper.codemod.add_import_module import add_import_module
from zrb.helper.file.copy_tree import copy_tree
from zrb.helper.file.text import read_text_file_async, write_text_file_async
from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Any, List, Optional
from zrb.task.any_task import AnyTask
from zrb.task.decorator import python_task
from zrb.task.task import Task
from zrb.task_input.any_input import AnyInput

CURRENT_DIR = os.path.dirname(__file__)


@typechecked
def create_ensure_project_tasks(upstreams: Optional[List[AnyTask]] = None) -> Task:
    """
    Create a task to ensure there are project tasks under `_automate/_project`
    """

    @python_task(
        name="ensure-project-tasks",
        inputs=[project_dir_input],
        upstreams=[] if upstreams is None else upstreams,
    )
    async def _task(*args: Any, **kwargs: Any):
        task: Task = kwargs.get("_task")
        project_dir = kwargs.get("project_dir", ".")
        task.print_out("Create project tasks if not exist")
        if os.path.exists(os.path.join(project_dir, "_automate", "_project")):
            return
        await copy_tree(
            src=os.path.join(CURRENT_DIR, "template"),
            dst=project_dir,
            excludes=["*/__pycache__"],
        )
        project_task_module_path = "_automate._project"
        zrb_init_path = os.path.join(project_dir, "zrb_init.py")
        code = await read_text_file_async(zrb_init_path)
        import_alias = project_task_module_path.split(".")[-1]
        code = add_import_module(
            code=code, module_path=project_task_module_path, alias=import_alias
        )
        code = add_assert_resource(code, import_alias)
        await write_text_file_async(zrb_init_path, code)

    return _task


@typechecked
def create_add_build_images_upstream(
    upstream_module: str,
    upstream_task_var: str,
    inputs: Optional[List[AnyInput]] = None,
    upstreams: Optional[List[AnyTask]] = None,
) -> Task:
    return create_add_upstream(
        task_file_name=_get_project_task_file("build_project_images.py"),
        task_name="build-images",
        upstream_module=upstream_module,
        upstream_task_var=upstream_task_var,
        inputs=inputs,
        upstreams=upstreams,
    )


@typechecked
def create_add_deploy_upstream(
    upstream_module: str,
    upstream_task_var: str,
    inputs: Optional[List[AnyInput]] = None,
    upstreams: Optional[List[AnyTask]] = None,
) -> Task:
    return create_add_upstream(
        task_file_name=_get_project_task_file("deploy_project.py"),
        task_name="deploy",
        upstream_module=upstream_module,
        upstream_task_var=upstream_task_var,
        inputs=inputs,
        upstreams=upstreams,
    )


@typechecked
def create_add_destroy_upstream(
    upstream_module: str,
    upstream_task_var: str,
    inputs: Optional[List[AnyInput]] = None,
    upstreams: Optional[List[AnyTask]] = None,
) -> Task:
    return create_add_upstream(
        task_file_name=_get_project_task_file("destroy_project.py"),
        task_name="destroy",
        upstream_module=upstream_module,
        upstream_task_var=upstream_task_var,
        inputs=inputs,
        upstreams=upstreams,
    )


@typechecked
def create_add_push_images_upstream(
    upstream_module: str,
    upstream_task_var: str,
    inputs: Optional[List[AnyInput]] = None,
    upstreams: Optional[List[AnyTask]] = None,
) -> Task:
    return create_add_upstream(
        task_file_name=_get_project_task_file("push_project_images.py"),
        task_name="push-images",
        upstream_module=upstream_module,
        upstream_task_var=upstream_task_var,
        inputs=inputs,
        upstreams=upstreams,
    )


@typechecked
def create_add_remove_containers_upstream(
    upstream_module: str,
    upstream_task_var: str,
    inputs: Optional[List[AnyInput]] = None,
    upstreams: Optional[List[AnyTask]] = None,
) -> Task:
    return create_add_upstream(
        task_file_name=_get_project_task_file("remove_project_containers.py"),
        task_name="remove-containers",
        upstream_module=upstream_module,
        upstream_task_var=upstream_task_var,
        inputs=inputs,
        upstreams=upstreams,
    )


@typechecked
def create_add_start_containers_upstream(
    upstream_module: str,
    upstream_task_var: str,
    inputs: Optional[List[AnyInput]] = None,
    upstreams: Optional[List[AnyTask]] = None,
) -> Task:
    return create_add_upstream(
        task_file_name=_get_project_task_file("start_project_containers.py"),
        task_name="start-containers",
        upstream_module=upstream_module,
        upstream_task_var=upstream_task_var,
        inputs=inputs,
        upstreams=upstreams,
    )


@typechecked
def create_add_start_upstream(
    upstream_module: str,
    upstream_task_var: str,
    inputs: Optional[List[AnyInput]] = None,
    upstreams: Optional[List[AnyTask]] = None,
) -> Task:
    return create_add_upstream(
        task_file_name=_get_project_task_file("start_project.py"),
        task_name="start",
        upstream_module=upstream_module,
        upstream_task_var=upstream_task_var,
        inputs=inputs,
        upstreams=upstreams,
    )


@typechecked
def create_add_stop_containers_upstream(
    upstream_module: str,
    upstream_task_var: str,
    inputs: Optional[List[AnyInput]] = None,
    upstreams: Optional[List[AnyTask]] = None,
) -> Task:
    return create_add_upstream(
        task_file_name=_get_project_task_file("stop_project_containers.py"),
        task_name="stop-containers",
        upstream_module=upstream_module,
        upstream_task_var=upstream_task_var,
        inputs=inputs,
        upstreams=upstreams,
    )


@typechecked
def _get_project_task_file(task_file_name: str) -> str:
    return os.path.join("_automate", "_project", task_file_name)
