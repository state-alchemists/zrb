import os

from my_app_name._zrb.config import APP_DIR

from zrb.context.any_context import AnyContext
from zrb.util.codemod.modify_class import append_code_to_class
from zrb.util.codemod.modify_class_parent import prepend_parent_class
from zrb.util.codemod.modify_function import append_code_to_function
from zrb.util.codemod.modify_module import prepend_code_to_module
from zrb.util.file import read_file, write_file
from zrb.util.string.conversion import (
    to_human_case,
    to_kebab_case,
    to_pascal_case,
    to_snake_case,
)


def is_gateway_navigation_config_file(ctx: AnyContext, file_path: str) -> bool:
    return file_path == os.path.abspath(
        os.path.join(APP_DIR, "module", "gateway", "config", "navigation.py")
    )


def get_add_permission_migration_script(ctx: AnyContext) -> str:
    kebab_entity_name = to_kebab_case(ctx.input.entity)
    return "\n".join(
        [
            "op.bulk_insert(",
            '    metadata.tables["permissions"],',
            "    [",
            f'        {{"name": "{kebab_entity_name}:create", "description": "create {kebab_entity_name}"}},',  # noqa
            f'        {{"name": "{kebab_entity_name}:read", "description": "read {kebab_entity_name}"}},',  # noqa
            f'        {{"name": "{kebab_entity_name}:update", "description": "update {kebab_entity_name}"}},',  # noqa
            f'        {{"name": "{kebab_entity_name}:delete", "description": "delete {kebab_entity_name}"}},',  # noqa
            "    ]",
            ")",
        ]
    )


def get_remove_permission_migration_script(ctx: AnyContext) -> str:
    kebab_entity_name = to_kebab_case(ctx.input.entity)
    return "\n".join(
        [
            "op.execute(",
            '    sa.delete(metadata.tables["permissions"])',
            '    .where(metadata.tables["permissions"].c.name.in_(',
            f'        "{kebab_entity_name}:create",',
            f'        "{kebab_entity_name}:read",',
            f'        "{kebab_entity_name}:update",',
            f'        "{kebab_entity_name}:delete",',
            "    ))",
            ")",
        ]
    )


def get_auth_migration_version_dir() -> str:
    return os.path.join(APP_DIR, "module", "auth", "migration", "versions")


def get_existing_auth_migration_file_names() -> list[str]:
    migration_version_dir = get_auth_migration_version_dir()
    return [
        file_name
        for file_name in os.listdir(migration_version_dir)
        if file_name.endswith(".py")
    ]


def get_existing_auth_migration_xcom_key(ctx: AnyContext) -> str:
    snake_entity_name = to_snake_case(ctx.input.entity)
    return f"existing_my_app_name_auth_{snake_entity_name}_migration"


def is_in_app_schema_dir(ctx: AnyContext, file_path: str) -> bool:
    return file_path.startswith(
        os.path.abspath(
            os.path.join(APP_DIR, "schema", to_snake_case(ctx.input.entity))
        )
    )


def is_in_module_entity_test_dir(ctx: AnyContext, file_path: str) -> bool:
    return file_path.startswith(
        os.path.abspath(
            os.path.join(
                APP_DIR,
                "test",
                to_snake_case(ctx.input.module),
                to_snake_case(ctx.input.entity),
            )
        )
    )


def is_in_module_entity_dir(ctx: AnyContext, file_path: str) -> bool:
    return file_path.startswith(
        os.path.abspath(
            os.path.join(
                APP_DIR,
                "module",
                to_snake_case(ctx.input.module),
                "service",
                to_snake_case(ctx.input.entity),
            )
        )
    )


def is_module_route_file(ctx: AnyContext, file_path: str) -> bool:
    module_route_file = os.path.abspath(
        os.path.join(
            APP_DIR,
            "module",
            to_snake_case(ctx.input.module),
            "route.py",
        )
    )
    return file_path == module_route_file


def is_module_migration_metadata_file(ctx: AnyContext, file_path: str) -> bool:
    module_migration_metadata_file = os.path.abspath(
        os.path.join(
            APP_DIR,
            "module",
            to_snake_case(ctx.input.module),
            "migration_metadata.py",
        )
    )
    return file_path == module_migration_metadata_file


def is_module_client_file(ctx: AnyContext, file_path: str) -> bool:
    module_any_client_file = os.path.abspath(
        os.path.join(
            APP_DIR,
            "module",
            to_snake_case(ctx.input.module),
            "client",
            f"{to_snake_case(ctx.input.module)}_client.py",
        )
    )
    return file_path == module_any_client_file


def is_module_api_client_file(ctx: AnyContext, file_path: str) -> bool:
    module_api_client_file = os.path.abspath(
        os.path.join(
            APP_DIR,
            "module",
            to_snake_case(ctx.input.module),
            "client",
            f"{to_snake_case(ctx.input.module)}_api_client.py",
        )
    )
    return file_path == module_api_client_file


def is_module_direct_client_file(ctx: AnyContext, file_path: str) -> bool:
    module_direct_client_file = os.path.abspath(
        os.path.join(
            APP_DIR,
            "module",
            to_snake_case(ctx.input.module),
            "client",
            f"{to_snake_case(ctx.input.module)}_direct_client.py",
        )
    )
    return file_path == module_direct_client_file


def is_module_gateway_subroute_file(ctx: AnyContext, file_path: str) -> bool:
    module_gateway_subroute_file = os.path.abspath(
        os.path.join(
            APP_DIR,
            "module",
            "gateway",
            "subroute",
            f"{to_snake_case(ctx.input.module)}.py",
        )
    )
    return file_path == module_gateway_subroute_file


def is_module_gateway_subroute_view_file(ctx: AnyContext, file_path: str) -> bool:
    module_gateway_subroute_file = os.path.abspath(
        os.path.join(
            APP_DIR,
            "module",
            "gateway",
            "view",
            "content",
            f"{to_kebab_case(ctx.input.module)}",
            f"{to_kebab_case(ctx.input.entity)}.html",
        )
    )
    return file_path == module_gateway_subroute_file


def update_migration_metadata_file(ctx: AnyContext, migration_metadata_file_path: str):
    app_name = os.path.basename(APP_DIR)
    existing_migration_metadata_code = read_file(migration_metadata_file_path)
    write_file(
        file_path=migration_metadata_file_path,
        content=[
            _get_migration_import_schema_code(
                existing_migration_metadata_code, app_name, ctx.input.entity
            ),
            existing_migration_metadata_code.strip(),
            _get_migration_entity_metadata_assignment_code(
                existing_migration_metadata_code, ctx.input.entity
            ),
        ],
    )


def _get_migration_import_schema_code(
    existing_code: str, app_name: str, entity_name: str
) -> str | None:
    snake_entity_name = to_snake_case(entity_name)
    pascal_entity_name = to_pascal_case(entity_name)
    import_module_path = f"{app_name}.schema.{snake_entity_name}"
    import_schema_code = f"from {import_module_path} import {pascal_entity_name}"
    if import_schema_code in existing_code:
        return None
    return import_schema_code


def _get_migration_entity_metadata_assignment_code(
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


def update_client_file(ctx: AnyContext, client_file_path: str):
    existing_client_code = read_file(client_file_path)
    pascal_module_name = to_pascal_case(ctx.input.module)
    snake_entity_name = to_snake_case(ctx.input.entity)
    snake_plural_entity_name = to_snake_case(ctx.input.plural)
    pascal_entity_name = to_pascal_case(ctx.input.entity)
    write_file(
        file_path=client_file_path,
        content=[
            _get_import_schema_for_client_code(
                existing_code=existing_client_code, entity_name=ctx.input.entity
            ),
            append_code_to_class(
                original_code=existing_client_code,
                class_name=f"{pascal_module_name}Client",
                new_code=read_file(
                    file_path=os.path.join(
                        os.path.dirname(__file__), "template", "client_method.py"
                    ),
                    replace_map={
                        "my_entity": snake_entity_name,
                        "my_entities": snake_plural_entity_name,
                        "MyEntity": pascal_entity_name,
                    },
                ),
            ),
        ],
    )


def _get_import_schema_for_client_code(
    existing_code: str, entity_name: str
) -> str | None:
    snake_entity_name = to_snake_case(entity_name)
    pascal_entity_name = to_pascal_case(entity_name)
    schema_import_path = f"my_app_name.schema.{snake_entity_name}"
    new_code = "\n".join(
        [
            f"from {schema_import_path} import (",
            f"   Multiple{pascal_entity_name}Response,",
            f"   {pascal_entity_name}Create,",
            f"   {pascal_entity_name}CreateWithAudit,",
            f"   {pascal_entity_name}Response,",
            f"   {pascal_entity_name}Update,",
            f"   {pascal_entity_name}UpdateWithAudit,",
            ")",
        ]
    )
    if new_code in existing_code:
        return None
    return new_code


def update_api_client_file(ctx: AnyContext, api_client_file_path: str):
    existing_api_client_code = read_file(api_client_file_path)
    upper_snake_module_name = to_snake_case(ctx.input.module).upper()
    app_name = os.path.basename(APP_DIR)
    snake_entity_name = to_snake_case(ctx.input.entity)
    snake_module_name = to_snake_case(ctx.input.module)
    pascal_module_name = to_pascal_case(ctx.input.module)
    write_file(
        file_path=api_client_file_path,
        content=[
            f"from {app_name}.module.{snake_module_name}.service.{snake_entity_name}.{snake_entity_name}_service_factory import {snake_entity_name}_service",  # noqa
            prepend_code_to_module(
                prepend_parent_class(
                    original_code=existing_api_client_code,
                    class_name=f"{pascal_module_name}APIClient",
                    parent_class_name=f"{snake_entity_name}_api_client",
                ),
                f"{snake_entity_name}_api_client = {snake_entity_name}_service.as_api_client(base_url=APP_{upper_snake_module_name}_BASE_URL)",  # noqa
            ),
        ],
    )


def update_direct_client_file(ctx: AnyContext, direct_client_file_path: str):
    existing_direct_client_code = read_file(direct_client_file_path)
    app_name = os.path.basename(APP_DIR)
    snake_entity_name = to_snake_case(ctx.input.entity)
    snake_module_name = to_snake_case(ctx.input.module)
    pascal_module_name = to_pascal_case(ctx.input.module)
    write_file(
        file_path=direct_client_file_path,
        content=[
            f"from {app_name}.module.{snake_module_name}.service.{snake_entity_name}.{snake_entity_name}_service_factory import {snake_entity_name}_service",  # noqa
            prepend_code_to_module(
                prepend_parent_class(
                    original_code=existing_direct_client_code,
                    class_name=f"{pascal_module_name}DirectClient",
                    parent_class_name=f"{snake_entity_name}_direct_client",
                ),
                f"{snake_entity_name}_direct_client = {snake_entity_name}_service.as_direct_client()",  # noqa
            ).strip(),
        ],
    )


def update_route_file(ctx: AnyContext, route_file_path: str):
    existing_route_code = read_file(route_file_path)
    entity_name = to_snake_case(ctx.input.entity)
    app_name = os.path.basename(APP_DIR)
    module_name = to_snake_case(ctx.input.module)
    write_file(
        file_path=route_file_path,
        content=[
            f"from {app_name}.module.{module_name}.service.{entity_name}.{entity_name}_service_factory import {entity_name}_service",  # noqa
            append_code_to_function(
                existing_route_code,
                "serve_route",
                f"{entity_name}_service.serve_route(app)",
            ),
        ],
    )


def update_gateway_subroute_file(ctx: AnyContext, module_gateway_subroute_path: str):
    snake_module_name = to_snake_case(ctx.input.module)
    kebab_module_name = to_kebab_case(ctx.input.module)
    snake_entity_name = to_snake_case(ctx.input.entity)
    kebab_entity_name = to_kebab_case(ctx.input.entity)
    snake_plural_entity_name = to_snake_case(ctx.input.plural)
    kebab_plural_entity_name = to_kebab_case(ctx.input.plural)
    pascal_entity_name = to_pascal_case(ctx.input.entity)
    existing_gateway_subroute_code = read_file(module_gateway_subroute_path)
    write_file(
        file_path=module_gateway_subroute_path,
        content=[
            _get_import_client_for_gateway_subroute_code(
                existing_gateway_subroute_code, module_name=ctx.input.module
            ),
            _get_import_schema_for_gateway_subroute_code(
                existing_gateway_subroute_code, entity_name=ctx.input.entity
            ),
            append_code_to_function(
                original_code=existing_gateway_subroute_code,
                function_name=f"serve_{snake_module_name}_route",
                new_code=read_file(
                    file_path=os.path.join(
                        os.path.dirname(__file__), "template", "gateway_subroute.py"
                    ),
                    replace_map={
                        "my_module": snake_module_name,
                        "my-module": kebab_module_name,
                        "my_entity": snake_entity_name,
                        "my-entity": kebab_entity_name,
                        "my_entities": snake_plural_entity_name,
                        "my-entities": kebab_plural_entity_name,
                        "MyEntity": pascal_entity_name,
                    },
                ),
            ),
        ],
    )


def _get_import_client_for_gateway_subroute_code(
    existing_code: str, module_name: str
) -> str | None:
    snake_module_name = to_snake_case(module_name)
    client_import_path = f"my_app_name.module.{snake_module_name}.client.{snake_module_name}_client_factory"  # noqa
    new_code = f"from {client_import_path} import {snake_module_name}_client"
    if new_code in existing_code:
        return None
    return new_code


def _get_import_schema_for_gateway_subroute_code(
    existing_code: str, entity_name: str
) -> str | None:
    snake_entity_name = to_snake_case(entity_name)
    pascal_entity_name = to_pascal_case(entity_name)
    schema_import_path = f"my_app_name.schema.{snake_entity_name}"
    new_code = "\n".join(
        [
            f"from {schema_import_path} import (",
            f"   Multiple{pascal_entity_name}Response,",
            f"   {pascal_entity_name}Create,",
            f"   {pascal_entity_name}Response,",
            f"   {pascal_entity_name}Update,",
            ")",
        ]
    )
    if new_code in existing_code:
        return None
    return new_code


def update_gateway_navigation_config_file(
    ctx: AnyContext, gateway_navigation_config_file_path: str
):
    existing_gateway_navigation_config_code = read_file(
        gateway_navigation_config_file_path
    )
    snake_module_name = to_snake_case(ctx.input.module)
    kebab_module_name = to_kebab_case(ctx.input.module)
    kebab_entity_name = to_kebab_case(ctx.input.entity)
    human_entity_name = to_human_case(ctx.input.entity)
    kebab_plural_name = to_kebab_case(ctx.input.plural)
    new_navigation_config_code = read_file(
        file_path=os.path.join(
            os.path.dirname(__file__), "template", "navigation_config_file.py"
        ),
        replace_map={
            "my_module": snake_module_name,
            "my-module": kebab_module_name,
            "my-entity": kebab_entity_name,
            "My Entity": human_entity_name.title(),
            "my-entities": kebab_plural_name,
        },
    ).strip()
    write_file(
        file_path=gateway_navigation_config_file_path,
        content=[
            existing_gateway_navigation_config_code,
            new_navigation_config_code,
        ],
    )
