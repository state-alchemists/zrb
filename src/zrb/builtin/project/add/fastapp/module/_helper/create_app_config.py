import os

from zrb.helper.file.text import read_text_file_async, write_text_file_async
from zrb.helper.typecheck import typechecked
from zrb.helper.util import to_kebab_case, to_snake_case
from zrb.task.task import Task


@typechecked
async def create_app_config(
    task: Task, project_dir: str, app_name: str, module_name: str
):
    kebab_app_name = to_kebab_case(app_name)
    snake_module_name = to_snake_case(module_name)
    upper_snake_module_name = snake_module_name.upper()
    config_file_path = os.path.join(
        project_dir, "src", kebab_app_name, "src", "config.py"
    )
    config_code = "\n".join(
        [
            f"APP_ENABLE_{upper_snake_module_name}_MODULE = str_to_boolean(os.environ.get(",  # noqa
            f"    'APP_ENABLE_{upper_snake_module_name}_MODULE', 'true'" "))",
        ]
    )
    task.print_out(f"Read config from: {config_file_path}")
    code = await read_text_file_async(config_file_path)
    code += "\n" + config_code
    task.print_out(f"Write config to: {config_file_path}")
    await write_text_file_async(config_file_path, code)
