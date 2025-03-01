import os

from my_app_name._zrb.config import ACTIVATE_VENV_SCRIPT, APP_DIR
from my_app_name._zrb.entity.add_entity_util import (
    get_add_permission_migration_script,
    get_auth_migration_version_dir,
    get_existing_auth_migration_file_names,
    get_existing_auth_migration_xcom_key,
    get_remove_permission_migration_script,
    is_gateway_navigation_config_file,
    is_in_app_schema_dir,
    is_in_module_entity_dir,
    is_in_module_entity_test_dir,
    is_module_api_client_file,
    is_module_client_file,
    is_module_direct_client_file,
    is_module_gateway_subroute_file,
    is_module_gateway_subroute_view_file,
    is_module_migration_metadata_file,
    is_module_route_file,
    update_api_client_file,
    update_client_file,
    update_direct_client_file,
    update_gateway_navigation_config_file,
    update_gateway_subroute_file,
    update_migration_metadata_file,
    update_route_file,
)
from my_app_name._zrb.format_task import format_my_app_name_code
from my_app_name._zrb.group import app_create_group
from my_app_name._zrb.input import (
    existing_module_input,
    new_entity_column_input,
    new_entity_input,
    plural_entity_input,
)
from my_app_name._zrb.util import (
    cd_module_script,
    get_existing_module_names,
    get_existing_schema_names,
    set_create_migration_db_url_env,
    set_env,
)
from my_app_name._zrb.venv_task import prepare_venv

from zrb import (
    AnyContext,
    Cmd,
    CmdTask,
    ContentTransformer,
    EnvFile,
    Scaffolder,
    Task,
    Xcom,
    make_task,
)
from zrb.util.codemod.modify_function import replace_function_code
from zrb.util.file import read_file, write_file
from zrb.util.string.conversion import to_snake_case


@make_task(
    name="validate-add-my-app-name-entity",
    input=[
        existing_module_input,
        new_entity_input,
        plural_entity_input,
        new_entity_column_input,
    ],
    retries=0,
)
async def validate_add_my_app_name_entity(ctx: AnyContext):
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
        "my-module": "{to_kebab_case(ctx.input.module)}",
        "my_entity": "{to_snake_case(ctx.input.entity)}",
        "my-entity": "{to_kebab_case(ctx.input.entity)}",
    },
    transform_content=[
        # Schema tranformation (my_app_name/schema/snake_entity_name)
        ContentTransformer(
            name="transform-schema-file",
            match=is_in_app_schema_dir,
            transform={
                "MyEntity": "{to_pascal_case(ctx.input.entity)}",
                "my_entities": "{to_snake_case(ctx.input.plural)}",
                "my_column": "{to_snake_case(ctx.input.column)}",
            },
        ),
        # Common module's entity transformation
        # (my_app_name/module/snake_module_name/service/snake_entity_name)
        ContentTransformer(
            name="transform-module-entity-dir",
            match=is_in_module_entity_dir,
            transform={
                "my_module": "{to_snake_case(ctx.input.module)}",
                "MyEntity": "{to_pascal_case(ctx.input.entity)}",
                "my_entity": "{to_snake_case(ctx.input.entity)}",
                "my_entities": "{to_snake_case(ctx.input.plural)}",
                "my-entities": "{to_kebab_case(ctx.input.plural)}",
            },
        ),
        # Test transformation (my_app_name/test/my_module/my_entity)
        ContentTransformer(
            name="transform-module-entity-test-dir",
            match=is_in_module_entity_test_dir,
            transform={
                "my_module": "{to_snake_case(ctx.input.module)}",
                "my_entity": "{to_snake_case(ctx.input.entity)}",
                "my-entity": "{to_kebab_case(ctx.input.entity)}",
                "my-entities": "{to_kebab_case(ctx.input.plural)}",
                "my_column": "{to_snake_case(ctx.input.column)}",
            },
        ),
        # Add entity to migration metadata
        # (my_app_name/module/snake_module_name/migration_metadata.py)
        ContentTransformer(
            name="transform-module-migration-metadata",
            match=is_module_migration_metadata_file,
            transform=update_migration_metadata_file,
        ),
        # Update API Client
        # (my_app_name/module/snake_module_name/client/snake_module_name_api_client.py)
        ContentTransformer(
            name="transform-module-api-client",
            match=is_module_api_client_file,
            transform=update_api_client_file,
        ),
        # Update Direct Client
        # (my_app_name/module/snake_module_name/client/snake_module_name_direct_client.py)
        ContentTransformer(
            name="transform-module-direct-client",
            match=is_module_direct_client_file,
            transform=update_direct_client_file,
        ),
        # Update Client
        # (my_app_name/module/snake_module_name/client/snake_module_name_client.py)
        ContentTransformer(
            name="transform-module-any-client",
            match=is_module_client_file,
            transform=update_client_file,
        ),
        # Update module route (my_app_name/module/route.py)
        ContentTransformer(
            name="transform-module-route",
            match=is_module_route_file,
            transform=update_route_file,
        ),
        # Update module gateway subroute
        # (my_app_name/module/gateway/subroute/snake_module_name.py)
        ContentTransformer(
            name="transform-module-gateway-subroute",
            match=is_module_gateway_subroute_file,
            transform=update_gateway_subroute_file,
        ),
        # Update module gateway subroute view
        # (my_app_name/module/gateway/view/content/kebab-module-name/kebab-entity-name.py)
        ContentTransformer(
            name="transform-module-gateway-subroute-view",
            match=is_module_gateway_subroute_view_file,
            transform={
                "My Entity": "{to_human_case(ctx.input.entity).title()}",
                "my-entities": "{to_kebab_case(ctx.input.plural)}",
                "My Column": "{to_human_case(ctx.input.column).title()}",
                "my_column": "{to_snake_case(ctx.input.column)}",
            },
        ),
        # Register entity's page to my_app_name/gateway/config/navigation.py
        ContentTransformer(
            name="transform-gateway-navigation-config",
            match=is_gateway_navigation_config_file,
            transform=update_gateway_navigation_config_file,
        ),
    ],
    retries=0,
    upstream=validate_add_my_app_name_entity,
)

create_my_app_name_entity_migration = CmdTask(
    name="create-my-app-name-entity-migration",
    input=[
        existing_module_input,
        new_entity_input,
    ],
    env=EnvFile(path=os.path.join(APP_DIR, "template.env")),
    cwd=APP_DIR,
    cmd=[
        ACTIVATE_VENV_SCRIPT,
        Cmd(lambda ctx: set_create_migration_db_url_env(ctx.input.module)),
        Cmd(lambda ctx: set_env("MY_APP_NAME_MODULES", ctx.input.module)),
        Cmd(lambda ctx: cd_module_script(ctx.input.module)),
        "alembic upgrade head",
        Cmd(
            'alembic revision --autogenerate -m "create_{to_snake_case(ctx.input.entity)}_table"',  # noqa
        ),
    ],
    render_cmd=False,
    retries=0,
    upstream=[
        prepare_venv,
        scaffold_my_app_name_entity,
    ],
)


@make_task(
    name="inspect-my-app-name-auth-migration",
    input=new_entity_input,
    retries=0,
    upstream=scaffold_my_app_name_entity,
)
def inspect_my_app_name_auth_migration(ctx: AnyContext):
    """Getting existing migration files in auth module"""
    migration_file_names = get_existing_auth_migration_file_names()
    xcom_key = get_existing_auth_migration_xcom_key(ctx)
    if xcom_key not in ctx.xcom:
        ctx.xcom[xcom_key] = Xcom([])
    ctx.xcom[xcom_key].push(migration_file_names)


create_my_app_name_entity_permission = CmdTask(
    name="create-my-app-name-entity-permission",
    input=[
        new_entity_input,
    ],
    env=EnvFile(path=os.path.join(APP_DIR, "template.env")),
    cwd=APP_DIR,
    cmd=[
        ACTIVATE_VENV_SCRIPT,
        Cmd(lambda ctx: set_create_migration_db_url_env("auth")),
        Cmd(lambda ctx: set_env("MY_APP_NAME_MODULES", "auth")),
        Cmd(lambda ctx: cd_module_script("auth")),
        "alembic upgrade head",
        Cmd(
            'alembic revision --autogenerate -m "create_{to_snake_case(ctx.input.entity)}_permission"',  # noqa
        ),
    ],
    render_cmd=False,
    retries=0,
    upstream=[
        prepare_venv,
        inspect_my_app_name_auth_migration,
    ],
)


@make_task(
    name="update-my-app-name-entity-permission",
    input=new_entity_input,
    retries=0,
    upstream=create_my_app_name_entity_permission,
)
def update_my_app_name_entity_permission(ctx: AnyContext):
    xcom_key = get_existing_auth_migration_xcom_key(ctx)
    existing_migration_file_names = ctx.xcom[xcom_key].pop()
    current_migration_file_names = get_existing_auth_migration_file_names()
    new_migration_file_names = [
        file_name
        for file_name in current_migration_file_names
        if file_name not in existing_migration_file_names
    ]
    if len(new_migration_file_names) == 0:
        raise Exception("No migration file created")
    new_migration_file_path = os.path.join(
        get_auth_migration_version_dir(), new_migration_file_names[0]
    )
    new_migration_code = read_file(
        new_migration_file_path,
        {
            "from alembic import op": "\n".join(
                [
                    "from alembic import op",
                    "from module.auth.migration_metadata import metadata",
                ]
            ),
        },
    )
    new_migration_code = replace_function_code(
        new_migration_code, "upgrade", get_add_permission_migration_script(ctx)
    )
    new_migration_code = replace_function_code(
        new_migration_code, "downgrade", get_remove_permission_migration_script(ctx)
    )
    write_file(new_migration_file_path, new_migration_code)


add_my_app_name_entity = app_create_group.add_task(
    Task(
        name="add-my-app-name-entity",
        description="📦 Create new entity on a module",
        upstream=[
            create_my_app_name_entity_migration,
            update_my_app_name_entity_permission,
        ],
        successor=format_my_app_name_code,
        retries=0,
    ),
    alias="entity",
)
