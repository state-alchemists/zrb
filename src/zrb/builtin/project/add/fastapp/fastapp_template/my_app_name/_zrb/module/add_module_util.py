import os

from my_app_name._zrb.config import APP_DIR
from my_app_name._zrb.util import get_existing_module_names

from zrb.context.any_context import AnyContext
from zrb.util.codemod.modify_dict import append_key_to_dict
from zrb.util.codemod.modify_function import append_code_to_function
from zrb.util.file import read_file, write_file
from zrb.util.string.conversion import (
    to_human_case,
    to_kebab_case,
    to_pascal_case,
    to_snake_case,
)


def is_app_config_file(ctx: AnyContext, file_path: str) -> bool:
    return file_path == os.path.abspath(os.path.join(APP_DIR, "config.py"))


def is_app_main_file(ctx: AnyContext, file_path: str) -> bool:
    return file_path == os.path.abspath(os.path.join(APP_DIR, "main.py"))


def is_gateway_route_file(ctx: AnyContext, file_path: str) -> bool:
    return file_path == os.path.abspath(
        os.path.join(APP_DIR, "module", "gateway", "route.py")
    )


def is_gateway_navigation_config_file(ctx: AnyContext, file_path: str) -> bool:
    return file_path == os.path.abspath(
        os.path.join(APP_DIR, "module", "gateway", "config", "navigation.py")
    )


def is_app_zrb_task_file(ctx: AnyContext, file_path: str) -> bool:
    return file_path == os.path.abspath(os.path.join(APP_DIR, "_zrb", "task.py"))


def is_app_zrb_config_file(ctx: AnyContext, file_path: str) -> bool:
    return file_path == os.path.abspath(os.path.join(APP_DIR, "_zrb", "config.py"))


def is_in_module_dir(ctx: AnyContext, file_path: str) -> bool:
    return file_path.startswith(
        os.path.abspath(
            os.path.join(APP_DIR, "module", to_snake_case(ctx.input.module))
        )
    )


def is_gateway_module_subroute_file(ctx: AnyContext, file_path: str) -> bool:
    module_subroute_file_name = f"{to_snake_case(ctx.input.module)}.py"
    return file_path == os.path.abspath(
        os.path.join(
            APP_DIR, "module", "gateway", "subroute", module_subroute_file_name
        )
    )


def update_app_zrb_config_file(ctx: AnyContext, zrb_config_file_path: str):
    existing_zrb_config_code = read_file(zrb_config_file_path)
    module_name = ctx.input.module
    upper_snake_module_name = to_snake_case(module_name).upper()
    existing_module_names = get_existing_module_names()
    module_port = 3001 + len(
        [
            existing_module_name
            for existing_module_name in existing_module_names
            if existing_module_name != to_snake_case(module_name)
        ]
    )
    write_file(
        file_path=zrb_config_file_path,
        content=append_key_to_dict(
            original_code=existing_zrb_config_code,
            dictionary_name="MICROSERVICES_ENV_VARS",
            new_key=f"MY_APP_NAME_{upper_snake_module_name}_BASE_URL",
            new_value=f"http://localhost:{module_port}",
        ),
    )


def update_app_zrb_task_file(ctx: AnyContext, zrb_task_file_path: str):
    existing_zrb_task_code = read_file(zrb_task_file_path)
    write_file(
        file_path=zrb_task_file_path,
        content=[
            existing_zrb_task_code.strip(),
            "",
            _get_task_definition_code(existing_zrb_task_code, ctx.input.module),
        ],
    )


def _get_task_definition_code(existing_code: str, module_name: str) -> str | None:
    existing_module_names = get_existing_module_names()
    module_port = 3001 + len(
        [
            existing_module_name
            for existing_module_name in existing_module_names
            if existing_module_name != to_snake_case(module_name)
        ]
    )
    snake_module_name = to_snake_case(module_name)
    kebab_module_name = to_kebab_case(module_name)
    pascal_module_name = to_pascal_case(module_name)
    task_definition_code = read_file(
        file_path=os.path.join(
            os.path.dirname(__file__), "template", "module_task_definition.py"
        ),
        replace_map={
            "my_module": snake_module_name,
            "my-module": kebab_module_name,
            "My Module": pascal_module_name,
            "3000": f"{module_port}",
        },
    ).strip()
    if task_definition_code in existing_code:
        return None
    return task_definition_code


def update_app_main_file(ctx: AnyContext, app_main_file_path: str):
    existing_app_main_code = read_file(app_main_file_path)
    write_file(
        file_path=app_main_file_path,
        content=[
            _get_import_module_route_code(existing_app_main_code, ctx.input.module),
            existing_app_main_code,
            "",
            _get_assert_module_route_code(existing_app_main_code, ctx.input.module),
        ],
    )


def _get_import_module_route_code(existing_code: str, module_name: str) -> str | None:
    snake_module_name = to_snake_case(module_name)
    import_module_path = f"my_app_name.module.{snake_module_name}"
    import_route_code = (
        f"from {import_module_path} import route as {snake_module_name}_route"
    )
    if import_route_code in existing_code:
        return None
    return import_route_code


def _get_assert_module_route_code(existing_code: str, module_name: str) -> str | None:
    snake_module_name = to_snake_case(module_name)
    assert_route_code = f"assert {snake_module_name}_route"
    return assert_route_code if assert_route_code not in existing_code else None


def update_app_config_file(ctx: AnyContext, module_config_path: str):
    existing_config_code = read_file(module_config_path)
    write_file(
        module_config_path,
        [
            existing_config_code.strip(),
            _get_new_module_config_code(existing_config_code, ctx.input.module),
        ],
    )


def _get_new_module_config_code(existing_code: str, module_name: str) -> str | None:
    existing_module_names = get_existing_module_names()
    module_port = 3000 + len(
        [
            existing_module_name
            for existing_module_name in existing_module_names
            if existing_module_name != to_snake_case(module_name)
        ]
    )
    module_base_url = f"http://localhost:{module_port}"
    upper_snake_module_name = to_snake_case(module_name).upper()
    config_name = f"APP_{upper_snake_module_name}_BASE_URL"
    env_name = f"MY_APP_NAME_{upper_snake_module_name}_BASE_URL"
    config_code = f'{config_name} = os.getenv("{env_name}", "{module_base_url}")'
    if config_code in existing_code:
        return None
    return config_code


def update_gateway_route_file(ctx: AnyContext, gateway_route_file_path: str):
    existing_gateway_route_code = read_file(gateway_route_file_path)
    snake_module_name = to_snake_case(ctx.input.module)
    write_file(
        file_path=gateway_route_file_path,
        content=[
            _get_module_subroute_import(existing_gateway_route_code, ctx.input.module),
            append_code_to_function(
                original_code=existing_gateway_route_code,
                function_name="serve_route",
                new_code="\n".join(
                    [
                        f"# Serve {snake_module_name} route",
                        f"serve_{snake_module_name}_route(app)",
                    ]
                ),
            ),
        ],
    )


def _get_module_subroute_import(existing_code: str, module_name: str) -> str | None:
    snake_module_name = to_snake_case(module_name)
    import_module_path = f"my_app_name.module.gateway.subroute.{snake_module_name}"
    import_code = f"from {import_module_path} import serve_{snake_module_name}_route"
    if import_code in existing_code:
        return None
    return import_code


def update_gateway_navigation_config_file(
    ctx: AnyContext, gateway_navigation_config_file_path: str
):
    existing_gateway_navigation_config_code = read_file(
        gateway_navigation_config_file_path
    )
    snake_module_name = to_snake_case(ctx.input.module)
    kebab_module_name = to_kebab_case(ctx.input.module)
    human_module_name = to_human_case(ctx.input.module)
    new_navigation_config_code = read_file(
        file_path=os.path.join(
            os.path.dirname(__file__), "template", "navigation_config_file.py"
        ),
        replace_map={
            "my_module": snake_module_name,
            "my-module": kebab_module_name,
            "My Module": human_module_name.title(),
        },
    ).strip()
    write_file(
        file_path=gateway_navigation_config_file_path,
        content=[
            existing_gateway_navigation_config_code,
            new_navigation_config_code,
        ],
    )
