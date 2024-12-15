import os

from my_app_name._zrb.config import APP_DIR
from my_app_name._zrb.format_task import format_my_app_name_code
from my_app_name._zrb.group import app_create_group
from my_app_name._zrb.input import (
    existing_module_input,
    new_entity_column_input,
    new_entity_input,
    plural_entity_input,
)
from my_app_name._zrb.util import get_existing_module_names, get_existing_schema_names

from zrb import AnyContext, ContentTransformer, Scaffolder, Task, make_task
from zrb.util.codemod.append_code_to_class import append_code_to_class
from zrb.util.codemod.append_code_to_function import append_code_to_function
from zrb.util.codemod.prepend_code_to_module import prepend_code_to_module
from zrb.util.codemod.prepend_parent_to_class import prepend_parent_class
from zrb.util.file import read_file, write_file
from zrb.util.string.conversion import to_pascal_case, to_snake_case


@make_task(
    name="validate-create-my-app-name-entity",
    input=[
        existing_module_input,
        new_entity_input,
        plural_entity_input,
        new_entity_column_input,
    ],
    retries=0,
)
async def validate_create_my_app_name_entity(ctx: AnyContext):
    module_name = to_snake_case(ctx.input.module)
    if module_name not in get_existing_module_names():
        raise ValueError(f"Module not exist: {module_name}")
    schema_name = to_snake_case(ctx.input.entity)
    if schema_name in get_existing_schema_names():
        raise ValueError(f"Schema already exists: {schema_name}")


scaffold_my_app_name_entity = Scaffolder(
    name="scaffold-my-app-name-entity",
    input=[
        existing_module_input,
        new_entity_input,
        plural_entity_input,
        new_entity_column_input,
    ],
    source_path=os.path.join(os.path.dirname(__file__), "template", "app_template"),
    render_source_path=False,
    destination_path=APP_DIR,
    transform_path={
        "my_module": "{to_snake_case(ctx.input.module)}",
        "my_entity": "{to_snake_case(ctx.input.entity)}",
    },
    transform_content=[
        # Schema tranformation (my_app_name/schema/snake_entity_name)
        ContentTransformer(
            match=lambda ctx, file_path: file_path.startswith(
                os.path.join(APP_DIR, "schema", to_snake_case(ctx.input.entity))
            ),
            transform={
                "MyEntity": "{to_pascal_case(ctx.input.entity)}",
                "my_column": "{to_snake_case(ctx.input.column)}",
            },
        ),
        # Common module's entity transformation (my_app_name/module/snake_module_name/service/snake_entity_name)
        ContentTransformer(
            match=lambda ctx, file_path: file_path.startswith(
                os.path.join(
                    APP_DIR,
                    "module",
                    to_snake_case(ctx.input.module),
                    "service",
                    to_snake_case(ctx.input.entity),
                )
            ),
            transform={
                "my_module": "{to_snake_case(ctx.input.module)}",
                "MyEntity": "{to_pascal_case(ctx.input.entity)}",
                "my_entity": "{to_snake_case(ctx.input.entity)}",
                "my_entities": "{to_snake_case(ctx.input.plural)}",
                "my-entities": "{to_kebab_case(ctx.input.plural)}",
            },
        ),
    ],
    retries=0,
    upstream=validate_create_my_app_name_entity,
)


@make_task(
    name="register-my-app-name-migration",
    input=[existing_module_input, new_entity_input],
    retries=0,
    upstream=validate_create_my_app_name_entity,
)
async def register_my_app_name_migration(ctx: AnyContext):
    migration_metadata_file_path = os.path.join(
        APP_DIR, "module", to_snake_case(ctx.input.module), "migration_metadata.py"
    )
    app_name = os.path.basename(APP_DIR)
    file_content = read_file(migration_metadata_file_path)
    snake_entity_name = to_snake_case(ctx.input.entity)
    pascal_entity_name = to_pascal_case(ctx.input.entity)
    new_file_content_list = (
        [f"from {app_name}.schema.{snake_entity_name} import {pascal_entity_name}"]
        + file_content.strip()
        + [
            f"{pascal_entity_name}.metadata = metadata",
            f"{pascal_entity_name}.__table__.tometadata(metadata)",
            "",
        ]
    )
    write_file(migration_metadata_file_path, "\n".join(new_file_content_list))


@make_task(
    name="register-my-app-name-api-client",
    input=[existing_module_input, new_entity_input],
    retries=0,
    upstream=validate_create_my_app_name_entity,
)
async def register_my_app_name_api_client(ctx: AnyContext):
    api_client_file_path = os.path.join(
        APP_DIR, "module", to_snake_case(ctx.input.module), "client", "api_client.py"
    )
    file_content = read_file(api_client_file_path)
    upper_snake_module_name = to_snake_case(ctx.input.module).upper()
    new_code = prepend_code_to_module(
        file_content,
        f"user_api_client = user_usecase.as_api_client(base_url=APP_{upper_snake_module_name}_BASE_URL)",  # noqa
    )
    new_code = prepend_parent_class(
        original_code=new_code,
        class_name="APIClient",
        parent_class_name="user_api_client",
    )
    app_name = os.path.basename(APP_DIR)
    snake_entity_name = to_snake_case(ctx.input.entity)
    snake_module_name = to_snake_case(ctx.input.module)
    write_file(
        api_client_file_path,
        [
            f"from {app_name}.module.{snake_module_name}.service.{snake_entity_name}.{snake_entity_name}_usecase import {snake_entity_name}_usecase",  # noqa
            new_code.strip(),
            "",
        ],
    )


@make_task(
    name="register-my-app-name-direct-client",
    input=[existing_module_input, new_entity_input],
    retries=0,
    upstream=validate_create_my_app_name_entity,
)
async def register_my_app_name_direct_client(ctx: AnyContext):
    direct_client_file_path = os.path.join(
        APP_DIR, "module", to_snake_case(ctx.input.module), "client", "direct_client.py"
    )
    file_content = read_file(direct_client_file_path)
    app_name = os.path.basename(APP_DIR)
    snake_entity_name = to_snake_case(ctx.input.entity)
    snake_module_name = to_snake_case(ctx.input.module)
    write_file(
        direct_client_file_path,
        [
            f"from {app_name}.module.{snake_module_name}.service.{snake_entity_name}.{snake_entity_name}_usecase import {snake_entity_name}_usecase",  # noqa
            prepend_code_to_module(
                prepend_parent_class(
                    file_content, "DirectClient", "user_direct_client"
                ),
                "user_direct_client = user_usecase.as_direct_client()",
            ).strip(),
            "",
        ],
    )


@make_task(
    name="register-my-app-name-route",
    input=[existing_module_input, new_entity_input],
    retries=0,
    upstream=validate_create_my_app_name_entity,
)
async def register_my_app_name_route(ctx: AnyContext):
    direct_client_file_path = os.path.join(
        APP_DIR, "module", to_snake_case(ctx.input.module), "route.py"
    )
    file_content = read_file(direct_client_file_path)
    entity_name = to_snake_case(ctx.input.entity)
    new_code = append_code_to_function(
        file_content, "serve_route", f"{entity_name}_usecase.serve_route(app)"
    )
    app_name = os.path.basename(APP_DIR)
    module_name = to_snake_case(ctx.input.module)
    new_file_content_list = [
        f"from {app_name}.module.{module_name}.service.{entity_name}.{entity_name}_usecase import {entity_name}_usecase",  # noqa
        new_code.strip(),
        "",
    ]
    write_file(direct_client_file_path, "\n".join(new_file_content_list))


@make_task(
    name="register-my-app-name-client-method",
    input=[existing_module_input, new_entity_input],
    retries=0,
    upstream=validate_create_my_app_name_entity,
)
async def register_my_app_name_client_method(ctx: AnyContext):
    any_client_file_path = os.path.join(
        APP_DIR, "module", to_snake_case(ctx.input.module), "route.py"
    )
    file_content = read_file(any_client_file_path)
    app_name = os.path.basename(APP_DIR)
    snake_entity_name = to_snake_case(ctx.input.entity)
    pascal_entity_name = to_pascal_case(ctx.input.entity)
    # TODO: Register client methods
    # get methods
    any_client_method_template_path = (
        os.path.join(os.path.dirname(__file__), "any_client_method.template.py"),
    )
    any_client_method_template = read_file(any_client_method_template_path)
    any_client_method = any_client_method_template.replace(
        "my_entity", snake_entity_name
    ).replace("MyEntity", pascal_entity_name)
    new_code = append_code_to_class(file_content, "AnyClient", any_client_method)
    new_file_content_list = [
        f"from {app_name}.schema.{snake_entity_name}.{snake_entity_name} import (",
        f"    {pascal_entity_name}CreateWithAudit, {pascal_entity_name}Response, {pascal_entity_name}UpdateWithAudit",
        ")",
        new_code.strip(),
        "",
    ]
    write_file(any_client_file_path, "\n".join(new_file_content_list))


# TODO: Register gateway route


add_my_app_name_entity = app_create_group.add_task(
    Task(
        name="add-my-app-name-entity",
        description="🏗️ Create new entity on a module",
        upstream=scaffold_my_app_name_entity,
        successor=format_my_app_name_code,
        retries=0,
    ),
    alias="entity",
)
add_my_app_name_entity << [
    register_my_app_name_api_client,
    register_my_app_name_direct_client,
    register_my_app_name_route,
]
