import os

from my_app_name._zrb.config import APP_DIR
from my_app_name._zrb.format_task import format_my_app_name_code
from my_app_name._zrb.group import app_create_group
from my_app_name._zrb.input import new_module_input
from my_app_name._zrb.module.add_module_util import (
    is_app_config_file,
    is_app_main_file,
    is_app_zrb_config_file,
    is_app_zrb_task_file,
    is_gateway_module_subroute_file,
    is_gateway_navigation_config_file,
    is_gateway_route_file,
    is_in_module_dir,
    update_app_config_file,
    update_app_main_file,
    update_app_zrb_config_file,
    update_app_zrb_task_file,
    update_gateway_navigation_config_file,
    update_gateway_route_file,
)
from my_app_name._zrb.util import get_existing_module_names

from zrb import AnyContext, ContentTransformer, Scaffolder, Task, make_task


@make_task(
    name="validate-add-my-app-name-module",
    input=new_module_input,
    retries=0,
)
async def validate_add_my_app_name_module(ctx: AnyContext):
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
        # Common transformation (my_app_name/module/snake_module_name)
        ContentTransformer(
            name="transform-module-dir",
            match=is_in_module_dir,
            transform={
                "MY_MODULE": "{to_snake_case(ctx.input.module).upper()}",
                "my_module": "{to_snake_case(ctx.input.module)}",
                "MyModule": "{to_pascal_case(ctx.input.module)}",
            },
        ),
        # Gateway's module subroute (my_app_name/module/gateway/subroute/snake_module_name.py)
        ContentTransformer(
            name="transform-gateway-subroute",
            match=is_gateway_module_subroute_file,
            transform={
                "my_module": "{to_snake_case(ctx.input.module)}",
            },
        ),
        # Register module config to my_app_name/config.py
        ContentTransformer(
            name="transform-app-config",
            match=is_app_config_file,
            transform=update_app_config_file,
        ),
        # Register module route to my_app_name/main.py
        ContentTransformer(
            name="transform-app-main",
            match=is_app_main_file,
            transform=update_app_main_file,
        ),
        # Register module's tasks to my_app_name/_zrb/task.py
        ContentTransformer(
            name="transform-zrb-task",
            match=is_app_zrb_task_file,
            transform=update_app_zrb_task_file,
        ),
        # Register module's base url to my_app_name/_zrb/config.py
        ContentTransformer(
            name="transform-zrb-config",
            match=is_app_zrb_config_file,
            transform=update_app_zrb_config_file,
        ),
        # Register module's subroute to my_app_name/gateway/route.py
        ContentTransformer(
            name="transform-gateway-route",
            match=is_gateway_route_file,
            transform=update_gateway_route_file,
        ),
        # Register module's page to my_app_name/gateway/config/navigation.py
        ContentTransformer(
            name="transform-gateway-navigation-config",
            match=is_gateway_navigation_config_file,
            transform=update_gateway_navigation_config_file,
        ),
    ],
    retries=0,
    upstream=validate_add_my_app_name_module,
)

add_my_app_name_module = app_create_group.add_task(
    Task(
        name="add-my-app-name-module",
        description="🧩 Create new module on My App Name",
        upstream=scaffold_my_app_name_module,
        successor=format_my_app_name_code,
        retries=0,
    ),
    alias="module",
)
