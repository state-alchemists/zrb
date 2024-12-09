import os

from fastapp_template._zrb.config import APP_DIR
from fastapp_template._zrb.group import app_create_group
from fastapp_template._zrb.helper import (
    get_existing_module_names,
    get_existing_schema_names,
)
from fastapp_template._zrb.input import (
    existing_module_input,
    new_entity_column_input,
    new_entity_input,
    plural_entity_input,
)

from zrb import AnyContext, Scaffolder, Task, make_task
from zrb.util.codemod.add_code_to_module import add_code_to_module
from zrb.util.codemod.add_parent_to_class import add_parent_to_class
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


scaffold_my_app_name_schema = Scaffolder(
    name="scaffold-my-app-name-schema",
    input=[
        existing_module_input,
        new_entity_input,
        new_entity_column_input,
    ],
    source_path=os.path.join(os.path.dirname(__file__), "schema.template.py"),
    render_source_path=False,
    destination_path=lambda ctx: os.path.join(
        APP_DIR,
        "schema",
        f"{to_snake_case(ctx.input.entity)}.py",
    ),
    transform_content={
        "MyEntity": "{to_pascal_case(ctx.input.entity)}",
        "my_column": "{to_snake_case(ctx.input.column)}",
    },
    retries=0,
    upstream=validate_create_my_app_name_entity,
)

scaffold_my_app_name_module_entity = Scaffolder(
    name="scaffold-my-app-name-schema",
    input=[
        existing_module_input,
        new_entity_input,
        plural_entity_input,
    ],
    source_path=os.path.join(os.path.dirname(__file__), "module_template"),
    render_source_path=False,
    destination_path=lambda ctx: os.path.join(
        APP_DIR,
        "module",
        f"{to_snake_case(ctx.input.module)}",
    ),
    transform_content={
        "my_module": "{to_snake_case(ctx.input.module)}",
        "MyEntity": "{to_pascal_case(ctx.input.entity)}",
        "my_entity": "{to_snake_case(ctx.input.entity)}",
        "my_entities": "{to_snake_case(ctx.input.plural)}",
        "my-entities": "{to_kebab_case(ctx.input.plural)}",
    },
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
    with open(migration_metadata_file_path, "r") as f:
        file_content = f.read()
    entity_name = to_snake_case(ctx.input.entity)
    entity_class = to_pascal_case(ctx.input.entity)
    new_file_content_list = (
        [f"from {app_name}.schema.{entity_name} import {entity_class}"]
        + file_content.strip()
        + [
            f"{entity_class}.metadata = metadata",
            f"{entity_class}.__table__.tometadata(metadata)",
            "",
        ]
    )
    with open(migration_metadata_file_path, "w") as f:
        f.write("\n".join(new_file_content_list))


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
    with open(api_client_file_path, "r") as f:
        file_content = f.read()
    module_config_name = to_snake_case(ctx.input.module).upper()
    new_code = add_code_to_module(
        file_content,
        f"user_api_client = user_usecase.as_api_client(base_url=APP_{module_config_name}_BASE_URL)",  # noqa
    )
    new_code = add_parent_to_class(
        original_code=new_code,
        class_name="APIClient",
        parent_class_name="user_api_client",
    )
    app_name = os.path.basename(APP_DIR)
    entity_name = to_snake_case(ctx.input.entity)
    module_name = to_snake_case(ctx.input.module)
    new_file_content_list = [
        f"from {app_name}.module.{module_name}.service.{entity_name} import {entity_name}_usecase",  # noqa
        new_code.strip(),
        "",
    ]
    with open(api_client_file_path, "w") as f:
        f.write("\n".join(new_file_content_list))


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
    with open(direct_client_file_path, "r") as f:
        file_content = f.read()
    new_code = add_code_to_module(
        file_content, "user_direct_client = user_usecase.as_direct_client()"
    )
    new_code = add_parent_to_class(
        original_code=new_code,
        class_name="DirectClient",
        parent_class_name="user_direct_client",
    )
    app_name = os.path.basename(APP_DIR)
    entity_name = to_snake_case(ctx.input.entity)
    module_name = to_snake_case(ctx.input.module)
    new_file_content_list = [
        f"from {app_name}.module.{module_name}.service.{entity_name} import {entity_name}_usecase",  # noqa
        new_code.strip(),
        "",
    ]
    with open(direct_client_file_path, "w") as f:
        f.write("\n".join(new_file_content_list))


create_my_app_name_entity = app_create_group.add_task(
    Task(
        name="create-my-app-name-entity",
        description="🏗️ Create new entity on a module",
        successor="",
    ),
    alias="entity",
)
create_my_app_name_entity << [
    scaffold_my_app_name_schema,
    scaffold_my_app_name_module_entity,
    register_my_app_name_api_client,
    register_my_app_name_direct_client,
]
