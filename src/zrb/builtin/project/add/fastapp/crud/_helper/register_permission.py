import os

from zrb.helper.codemod.append_code_to_function import append_code_to_function
from zrb.helper.file.text import read_text_file_async, write_text_file_async
from zrb.helper.typecheck import typechecked
from zrb.helper.util import to_kebab_case, to_snake_case
from zrb.task.task import Task


@typechecked
async def register_permission(
    task: Task, project_dir: str, app_name: str, module_name: str, entity_name: str
):
    kebab_app_name = to_kebab_case(app_name)
    snake_module_name = to_snake_case(module_name)
    snake_entity_name = to_snake_case(entity_name)
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
