import os

from zrb.helper.codemod.add_import_module import add_import_module
from zrb.helper.codemod.append_code_to_function import append_code_to_function
from zrb.helper.file.text import read_text_file_async, write_text_file_async
from zrb.helper.typecheck import typechecked
from zrb.helper.util import to_kebab_case, to_snake_case
from zrb.task.task import Task


@typechecked
async def register_migration(
    task: Task, project_dir: str, app_name: str, module_name: str
):
    kebab_app_name = to_kebab_case(app_name)
    snake_module_name = to_snake_case(module_name)
    app_migration_file_path = os.path.join(
        project_dir, "src", kebab_app_name, "src", "migrate.py"
    )
    import_module_path = ".".join(["module", snake_module_name, "migrate"])
    function_name = f"migrate_{snake_module_name}"
    task.print_out(f"Read code from: {app_migration_file_path}")
    code = await read_text_file_async(app_migration_file_path)
    task.print_out(
        f'Add import "{function_name}" from "{import_module_path}" to the code'
    )
    code = add_import_module(
        code=code, module_path=import_module_path, resource=function_name
    )
    task.print_out(f'Add "{function_name}" call to the code')
    code = append_code_to_function(
        code=code, function_name="migrate", new_code=f"await {function_name}()"
    )
    task.print_out(f"Write modified code to: {app_migration_file_path}")
    await write_text_file_async(app_migration_file_path, code)
