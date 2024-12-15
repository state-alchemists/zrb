import os
import re

from my_app_name._zrb.config import APP_DIR
from my_app_name._zrb.group import app_create_group
from my_app_name._zrb.input import new_module_input
from my_app_name._zrb.module.add_module_util import (
    update_app_config_file,
    update_app_main_file,
    update_app_zrb_config_file,
    update_app_zrb_task_file,
)
from my_app_name._zrb.util import get_existing_module_names

from zrb import AnyContext, ContentTransformer, Scaffolder, Task, make_task
from zrb.util.string.conversion import to_snake_case


@make_task(
    name="validate-create-my-app-name-module",
    input=new_module_input,
    retries=0,
)
async def validate_create_my_app_name_module(ctx: AnyContext):
    if ctx.input.module in get_existing_module_names():
        raise ValueError(f"Module already exists: {ctx.input.module}")


scaffold_my_app_name_module = Scaffolder(
    name="scaffold-my-app-name-module",
    input=new_module_input,
    source_path=os.path.join(os.path.dirname(__file__), "template", "app_template"),
    render_source_path=False,
    destination_path=APP_DIR,
    transform_path={
        "my_module": "{to_snake_case(ctx.input.module)}",
    },
    transform_content=[
        # Common transformation
        ContentTransformer(
            match=lambda ctx, file_path: file_path.startswith(
                os.path.join(APP_DIR, "module", to_snake_case(ctx.input.module))
            ),
            transform={
                "MY_MODULE": "{to_snake_case(ctx.input.module).upper()}",
                "my_module": "{to_snake_case(ctx.input.module)}",
            },
        ),
        # Register module config to my_app_name/config.py
        ContentTransformer(
            match=lambda _, file_path: file_path == os.path.join(APP_DIR, "config.py"),
            transform=update_app_config_file,
        ),
        # Register module route to my_app_name/main.py
        ContentTransformer(
            match=lambda _, file_path: file_path == os.path.join(APP_DIR, "main.py"),
            transform=update_app_main_file,
        ),
        # Register module's tasks to my_app_name/_zrb/task.py
        ContentTransformer(
            match=lambda _, file_path: file_path
            == os.path.join(APP_DIR, "_zrb", "task.py"),
            transform=update_app_zrb_task_file,
        ),
        # Register module's base url to my_app_name/_zrb/config.py
        ContentTransformer(
            match=lambda _, file_path: file_path
            == os.path.join(APP_DIR, "_zrb", "config.py"),
            transform=update_app_zrb_config_file,
        ),
    ],
    retries=0,
    upstream=validate_create_my_app_name_module,
)

add_my_app_name_module = app_create_group.add_task(
    Task(
        name="add-my-app-name-module",
        description="🧩 Create new module on My App Name",
        upstream=scaffold_my_app_name_module,
        retries=0,
    ),
    alias="module",
)
