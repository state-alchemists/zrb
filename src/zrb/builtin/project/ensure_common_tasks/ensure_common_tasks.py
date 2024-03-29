import os

from zrb.builtin.project._input import project_dir_input
from zrb.helper.codemod.add_assert_resource import add_assert_resource
from zrb.helper.codemod.add_import_module import add_import_module
from zrb.helper.file.copy_tree import copy_tree
from zrb.helper.file.text import read_text_file_async, write_text_file_async
from zrb.helper.typing import Any
from zrb.task.decorator import python_task
from zrb.task.task import Task

CURRENT_DIR = os.path.dirname(__file__)


@python_task(
    name="ensure-common-tasks",
    inputs=[project_dir_input],
)
async def ensure_common_tasks(*args: Any, **kwargs: Any):
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