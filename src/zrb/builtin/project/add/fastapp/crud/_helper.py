import os

from zrb.helper.codemod.add_import_module import add_import_module
from zrb.helper.codemod.append_code_to_function import append_code_to_function
from zrb.helper.file.text import read_text_file_async, write_text_file_async
from zrb.helper.typecheck import typechecked
from zrb.task.task import Task


@typechecked
async def register_api(
    task: Task,
    project_dir: str,
    kebab_app_name: str,
    snake_module_name: str,
    snake_entity_name: str,
):
    module_api_file_path = os.path.join(
        project_dir, "src", kebab_app_name, "src", "module", snake_module_name, "api.py"
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


@typechecked
async def register_rpc(
    task: Task,
    project_dir: str,
    kebab_app_name: str,
    snake_module_name: str,
    snake_entity_name: str,
):
    module_rpc_file_path = os.path.join(
        project_dir, "src", kebab_app_name, "src", "module", snake_module_name, "rpc.py"
    )
    register_function_path = ".".join(
        ["module", snake_module_name, "entity", snake_entity_name, "rpc"]
    )
    register_function = f"register_{snake_entity_name}_rpc"
    task.print_out(f"Read code from: {module_rpc_file_path}")
    code = await read_text_file_async(module_rpc_file_path)
    task.print_out(
        f'Add import "register_rpc" as "{register_function}" '
        + f'from "{register_function_path}" to the code'
    )
    code = add_import_module(
        code=code,
        module_path=register_function_path,
        resource="register_rpc",
        alias=register_function,
    )
    task.print_out(f'Add "{register_function}" call to the code')
    code = append_code_to_function(
        code=code,
        function_name="register_rpc",
        new_code=f"{register_function}(logger, rpc_server, rpc_caller, publisher)",  # noqa
    )
    task.print_out(f"Write modified code to: {module_rpc_file_path}")
    await write_text_file_async(module_rpc_file_path, code)


@typechecked
async def register_permission(
    task: Task,
    project_dir: str,
    kebab_app_name: str,
    snake_module_name: str,
    snake_entity_name: str,
):
    module_register_permission_file_path = os.path.join(
        project_dir,
        "src",
        kebab_app_name,
        "src",
        "module",
        "auth",
        "register_permission.py",
    )
    task.print_out(f"Read code from: {module_register_permission_file_path}")
    code = await read_text_file_async(module_register_permission_file_path)
    code = append_code_to_function(
        code=code,
        function_name="register_permission",
        new_code="\n".join(
            [
                "await ensure_entity_permission(",
                f"    module_name='{snake_module_name}', entity_name='{snake_entity_name}'",  # noqa
                ")",
            ]
        ),
    )
    task.print_out(
        f'Add "ensure_entity_permission" call for {snake_entity_name} ' + "to the code"
    )
    task.print_out(f"Write modified code to: {module_register_permission_file_path}")
    await write_text_file_async(module_register_permission_file_path, code)
