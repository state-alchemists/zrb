import os

from zrb.helper.file.text import append_text_file_async
from zrb.helper.typecheck import typechecked
from zrb.helper.util import to_kebab_case, to_snake_case
from zrb.task.task import Task


@typechecked
async def append_all_enabled_env(
    task: Task, project_dir: str, app_name: str, module_name: str
):
    kebab_app_name = to_kebab_case(app_name)
    snake_module_name = to_snake_case(module_name)
    upper_snake_module_name = snake_module_name.upper()
    all_enabled_env_path = os.path.join(
        project_dir, "src", kebab_app_name, "all-module-enabled.env"
    )
    task.print_out(f"Add new environment to: {all_enabled_env_path}")
    await append_text_file_async(
        all_enabled_env_path, f"APP_ENABLE_{upper_snake_module_name}_MODULE=true"
    )
