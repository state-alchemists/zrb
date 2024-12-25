import os

from my_app_name._zrb.config import APP_DIR

from zrb.context.any_context import AnyContext
from zrb.util.codemod.append_code_to_class import append_code_to_class
from zrb.util.codemod.append_code_to_function import append_code_to_function
from zrb.util.codemod.prepend_code_to_module import prepend_code_to_module
from zrb.util.codemod.prepend_parent_to_class import prepend_parent_class
from zrb.util.file import read_file, write_file
from zrb.util.string.conversion import to_pascal_case, to_snake_case


def is_in_app_schema_dir(ctx: AnyContext, file_path: str) -> bool:
    return file_path.startswith(
        os.path.join(APP_DIR, "schema", to_snake_case(ctx.input.entity))
    )


def is_in_module_entity_dir(ctx: AnyContext, file_path: str) -> bool:
    return file_path.startswith(
        os.path.join(
            APP_DIR,
            "module",
            to_snake_case(ctx.input.module),
            "service",
            to_snake_case(ctx.input.entity),
        )
    )


def is_module_route_file(ctx: AnyContext, file_path: str) -> bool:
    module_route_file = os.path.join(
        APP_DIR,
        "module",
        to_snake_case(ctx.input.module),
        "route.py",
    )
    return file_path == module_route_file


def is_module_migration_metadata_file(ctx: AnyContext, file_path: str) -> bool:
    module_migration_metadata_file = os.path.join(
        APP_DIR,
        "module",
        to_snake_case(ctx.input.module),
        "migration_metadata.py",
    )
    return file_path == module_migration_metadata_file


def is_module_any_client_file(ctx: AnyContext, file_path: str) -> bool:
    module_any_client_file = os.path.join(
        APP_DIR,
        "module",
        to_snake_case(ctx.input.module),
        "client",
        "any_client.py",
    )
    return file_path == module_any_client_file


def is_module_api_client_file(ctx: AnyContext, file_path: str) -> bool:
    module_api_client_file = os.path.join(
        APP_DIR,
        "module",
        to_snake_case(ctx.input.module),
        "client",
        "api_client.py",
    )
    return file_path == module_api_client_file


def is_module_direct_client_file(ctx: AnyContext, file_path: str) -> bool:
    module_direct_client_file = os.path.join(
        APP_DIR,
        "module",
        to_snake_case(ctx.input.module),
        "client",
        "direct_client.py",
    )
    return file_path == module_direct_client_file


def update_migration_metadata(ctx: AnyContext, migration_metadata_file_path: str):
    app_name = os.path.basename(APP_DIR)
    existing_migration_metadata_code = read_file(migration_metadata_file_path)
    write_file(
        file_path=migration_metadata_file_path,
        content=[
            _get_import_schema_code(
                existing_migration_metadata_code, app_name, ctx.input.entity
            ),
            existing_migration_metadata_code.strip(),
            _get_entity_metadata_assignment_code(
                existing_migration_metadata_code, ctx.input.entity
            ),
        ],
    )


def _get_import_schema_code(
    existing_code: str, app_name: str, entity_name: str
) -> str | None:
    snake_entity_name = to_snake_case(entity_name)
    pascal_entity_name = to_pascal_case(entity_name)
    import_module_path = f"{app_name}.schema.{snake_entity_name}"
    import_schema_code = f"from {import_module_path} import {pascal_entity_name}"
    if import_schema_code in existing_code:
        return None
    return import_schema_code


def _get_entity_metadata_assignment_code(
    existing_code: str, entity_name: str
) -> str | None:
    pascal_entity_name = to_pascal_case(entity_name)
    entity_metadata_assignment_code = "\n".join(
        [
            f"{pascal_entity_name}.metadata = metadata",
            f"{pascal_entity_name}.__table__.tometadata(metadata)",
        ]
    )
    if entity_metadata_assignment_code in existing_code:
        return None
    return entity_metadata_assignment_code


def update_any_client(ctx: AnyContext, any_client_file_path: str):
    existing_any_client_code = read_file(any_client_file_path)
    app_name = os.path.basename(APP_DIR)
    snake_entity_name = to_snake_case(ctx.input.entity)
    snake_plural_entity_name = to_snake_case(ctx.input.plural)
    pascal_entity_name = to_pascal_case(ctx.input.entity)
    any_client_method = read_file(
        file_path=os.path.join(
            os.path.dirname(__file__), "template", "any_client_method.py"
        ),
        replace_map={
            "my_entity": snake_entity_name,
            "my_entities": snake_plural_entity_name,
            "MyEntity": pascal_entity_name,
        },
    )
    new_code = append_code_to_class(
        existing_any_client_code, "AnyClient", any_client_method
    )
    write_file(
        file_path=any_client_file_path,
        content=[
            f"from {app_name}.schema.{snake_entity_name}.{snake_entity_name} import (",
            f"    {pascal_entity_name}CreateWithAudit, {pascal_entity_name}Response, {pascal_entity_name}UpdateWithAudit",  # noqa
            ")",
            new_code.strip(),
        ],
    )


def update_api_client(ctx: AnyContext, api_client_file_path: str):
    existing_api_client_code = read_file(api_client_file_path)
    upper_snake_module_name = to_snake_case(ctx.input.module).upper()
    app_name = os.path.basename(APP_DIR)
    snake_entity_name = to_snake_case(ctx.input.entity)
    snake_module_name = to_snake_case(ctx.input.module)
    write_file(
        file_path=api_client_file_path,
        content=[
            f"from {app_name}.module.{snake_module_name}.service.{snake_entity_name}.{snake_entity_name}_service import {snake_entity_name}_service",  # noqa
            prepend_code_to_module(
                prepend_parent_class(
                    existing_api_client_code, "APIClient", "user_api_client"
                ),
                f"user_api_client = user_service.as_api_client(base_url=APP_{upper_snake_module_name}_BASE_URL)",  # noqa
            ),
        ],
    )


def update_direct_client(ctx: AnyContext, direct_client_file_path: str):
    existing_direct_client_code = read_file(direct_client_file_path)
    app_name = os.path.basename(APP_DIR)
    snake_entity_name = to_snake_case(ctx.input.entity)
    snake_module_name = to_snake_case(ctx.input.module)
    write_file(
        file_path=direct_client_file_path,
        content=[
            f"from {app_name}.module.{snake_module_name}.service.{snake_entity_name}.{snake_entity_name}_service import {snake_entity_name}_service",  # noqa
            prepend_code_to_module(
                prepend_parent_class(
                    existing_direct_client_code, "DirectClient", "user_direct_client"
                ),
                "user_direct_client = user_service.as_direct_client()",
            ).strip(),
        ],
    )


def update_route(ctx: AnyContext, route_file_path: str):
    existing_route_code = read_file(route_file_path)
    entity_name = to_snake_case(ctx.input.entity)
    app_name = os.path.basename(APP_DIR)
    module_name = to_snake_case(ctx.input.module)
    write_file(
        file_path=route_file_path,
        content=[
            f"from {app_name}.module.{module_name}.service.{entity_name}.{entity_name}_service import {entity_name}_service",  # noqa
            append_code_to_function(
                existing_route_code,
                "serve_route",
                f"{entity_name}_service.serve_route(app)",
            ),
        ],
    )
