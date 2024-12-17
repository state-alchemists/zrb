import os

from my_app_name._zrb.config import APP_DIR
from my_app_name._zrb.entity.add_entity_util import (
    is_in_app_schema_dir,
    is_in_module_entity_dir,
    is_module_any_client_file,
    is_module_api_client_file,
    is_module_direct_client_file,
    is_module_migration_metadata_file,
    is_module_route_file,
    update_any_client,
    update_api_client,
    update_direct_client,
    update_migration_metadata,
    update_route,
)
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
from zrb.util.string.conversion import to_snake_case


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
            match=is_in_app_schema_dir,
            transform={
                "MyEntity": "{to_pascal_case(ctx.input.entity)}",
                "my_column": "{to_snake_case(ctx.input.column)}",
            },
        ),
        # Common module's entity transformation
        # (my_app_name/module/snake_module_name/service/snake_entity_name)
        ContentTransformer(
            match=is_in_module_entity_dir,
            transform={
                "my_module": "{to_snake_case(ctx.input.module)}",
                "MyEntity": "{to_pascal_case(ctx.input.entity)}",
                "my_entity": "{to_snake_case(ctx.input.entity)}",
                "my_entities": "{to_snake_case(ctx.input.plural)}",
                "my-entities": "{to_kebab_case(ctx.input.plural)}",
            },
        ),
        # Add entity to migration metadata
        # (my_app_name/module/snake_module_name/migration_metadata.py)
        ContentTransformer(
            match=is_module_migration_metadata_file,
            transform=update_migration_metadata,
        ),
        # Update API Client (my_app_name/module/snake_module_name/client/api_client.py)
        ContentTransformer(
            match=is_module_api_client_file,
            transform=update_api_client,
        ),
        # Update Direct Client (my_app_name/module/snake_module_name/client/direct_client.py)
        ContentTransformer(
            match=is_module_direct_client_file,
            transform=update_direct_client,
        ),
        # Update Any Client (my_app_name/module/snake_module_name/client/any_client.py)
        ContentTransformer(
            match=is_module_any_client_file,
            transform=update_any_client,
        ),
        # Update module route (my_app_name/module/route.py)
        ContentTransformer(
            match=is_module_route_file,
            transform=update_route,
        ),
        # TODO: Register gateway route
    ],
    retries=0,
    upstream=validate_create_my_app_name_entity,
)

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
