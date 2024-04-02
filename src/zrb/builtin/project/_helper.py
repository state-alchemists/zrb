import os

from zrb.builtin.project._input import project_dir_input
from zrb.helper import util
from zrb.helper.accessories.color import colored
from zrb.helper.codemod.add_assert_resource import add_assert_resource
from zrb.helper.codemod.add_import_module import add_import_module
from zrb.helper.file.text import read_text_file_async, write_text_file_async
from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Any, List, Optional
from zrb.task.any_task import AnyTask
from zrb.task.decorator import python_task
from zrb.task.task import Task
from zrb.task_input.any_input import AnyInput


@typechecked
def validate_existing_project_dir(project_dir: str):
    if not os.path.isfile(os.path.join(project_dir, "zrb_init.py")):
        raise Exception(f"Not a project: {project_dir}")


@typechecked
def validate_inexisting_automation(project_dir: str, automation_name: str):
    validate_inexisting_automation_package(project_dir, automation_name)
    validate_inexisting_automation_module(project_dir, automation_name)


@typechecked
def validate_inexisting_automation_package(project_dir: str, package_name: str):
    package_dir = os.path.join(
        project_dir, "_automate", f"{util.to_snake_case(package_name)}"
    )
    if os.path.exists(package_dir):
        raise Exception(f"Automation package already exists: {package_dir}")


@typechecked
def validate_inexisting_automation_module(project_dir: str, module_name: str):
    module_file = os.path.join(
        project_dir, "_automate", f"{util.to_snake_case(module_name)}.py"
    )
    if os.path.exists(module_file):
        raise Exception(f"Automation module already exists: {module_file}")


@typechecked
async def register_module_to_project(
    project_dir: str, module_path: str, alias: Optional[str] = None
):
    zrb_init_path = os.path.join(project_dir, "zrb_init.py")
    code = await read_text_file_async(zrb_init_path)
    if alias is None:
        alias = module_path.split(".")[-1]
    code = add_import_module(code=code, module_path=module_path, alias=alias)
    code = add_assert_resource(code, alias)
    await write_text_file_async(zrb_init_path, code)
    return True


@typechecked
def create_register_module(
    module_path: str,
    inputs: Optional[List[AnyInput]] = None,
    upstreams: Optional[List[AnyTask]] = None,
    alias: Optional[str] = None,
    task_name: str = "register-module",
) -> Task:
    @python_task(
        name=task_name,
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
        module_import_label = _get_module_import_label(
            module_path=rendered_module_path, alias=rendered_alias
        )
        task.print_out(colored(module_import_label, color="yellow"))
        await register_module_to_project(
            project_dir=project_dir,
            module_path=rendered_module_path,
            alias=rendered_alias,
        )

    return register_module


def _get_module_import_label(module_path: str, alias: Optional[str]):
    if alias == "" or alias is None:
        return module_path
    return f"{module_path} as {alias}"
