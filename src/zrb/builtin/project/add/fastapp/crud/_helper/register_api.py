import os

from zrb.helper.codemod.add_import_module import add_import_module
from zrb.helper.codemod.append_code_to_function import append_code_to_function
from zrb.helper.file.text import read_text_file_async, write_text_file_async
from zrb.helper.typecheck import typechecked
from zrb.helper.util import to_snake_case
from zrb.task.task import Task

from ._common import get_app_module_dir


@typechecked
async def register_api(
    task: Task, project_dir: str, app_name: str, module_name: str, entity_name: str
):
    snake_module_name = to_snake_case(module_name)
    snake_entity_name = to_snake_case(entity_name)
    module_api_file_path = os.path.join(
        get_app_module_dir(project_dir, app_name), snake_module_name, "api.py"
    )
    register_function_path = ".".join(
        ["module", snake_module_name, "entity", snake_entity_name, "api"]
    )
    register_function = f"register_{snake_entity_name}_api"
    task.print_out(f"Read code from: {module_api_file_path}")
    code = await read_text_file_async(module_api_file_path)
    task.print_out(
        f'Add import "register_api" as "{register_function}" '
        + f'from "{register_function_path}" to the code'
    )
    code = add_import_module(
        code=code,
        module_path=register_function_path,
        resource="register_api",
        alias=register_function,
    )
    task.print_out(f'Add "{register_function}" call to the code')
    code = append_code_to_function(
        code=code,
        function_name="register_api",
        new_code=f"{register_function}(logger, app, authorizer, rpc_caller, publisher)",  # noqa
    )
    task.print_out(f"Write modified code to: {module_api_file_path}")
    await write_text_file_async(module_api_file_path, code)
