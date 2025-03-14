import os

from my_app_name._zrb.column.add_column_util import (
    update_my_app_name_schema,
    update_my_app_name_test_create,
    update_my_app_name_test_delete,
    update_my_app_name_test_read,
    update_my_app_name_test_update,
    update_my_app_name_ui,
)
from my_app_name._zrb.config import ACTIVATE_VENV_SCRIPT, APP_DIR
from my_app_name._zrb.format_task import format_my_app_name_code
from my_app_name._zrb.group import app_create_group
from my_app_name._zrb.input import (
    existing_entity_input,
    existing_module_input,
    new_column_input,
    new_column_type_input,
)
from my_app_name._zrb.util import (
    cd_module_script,
    get_existing_module_names,
    get_existing_schema_names,
    set_create_migration_db_url_env,
    set_env,
)
from my_app_name._zrb.venv_task import prepare_venv

from zrb import AnyContext, Cmd, CmdTask, EnvFile, Task, make_task


@make_task(
    name="validate-add-my-app-name-column",
    input=[
        existing_module_input,
        existing_entity_input,
    ],
    retries=0,
)
async def validate_add_my_app_name_column(ctx: AnyContext):
    module_name = ctx.input.module
    if module_name not in get_existing_module_names():
        raise ValueError(f"Module not exist: {module_name}")
    schema_name = ctx.input.entity
    if schema_name not in get_existing_schema_names():
        raise ValueError(f"Schema not exist: {schema_name}")


update_my_app_name_schema_task = Task(
    name="update-my-app-name-schema",
    input=[
        existing_module_input,
        existing_entity_input,
        new_column_input,
        new_column_type_input,
    ],
    action=update_my_app_name_schema,
    retries=0,
    upstream=validate_add_my_app_name_column,
)

update_my_app_name_ui_task = Task(
    name="update-my-app-name-ui",
    input=[
        existing_module_input,
        existing_entity_input,
        new_column_input,
        new_column_type_input,
    ],
    action=update_my_app_name_ui,
    retries=0,
    upstream=validate_add_my_app_name_column,
)

update_my_app_name_test_create_task = Task(
    name="update-my-app-name-test-create",
    input=[
        existing_module_input,
        existing_entity_input,
        new_column_input,
        new_column_type_input,
    ],
    action=update_my_app_name_test_create,
    retries=0,
    upstream=validate_add_my_app_name_column,
)

update_my_app_name_test_read_task = Task(
    name="update-my-app-name-test-read",
    input=[
        existing_module_input,
        existing_entity_input,
        new_column_input,
        new_column_type_input,
    ],
    action=update_my_app_name_test_read,
    retries=0,
    upstream=validate_add_my_app_name_column,
)

update_my_app_name_test_update_task = Task(
    name="update-my-app-name-test-update",
    input=[
        existing_module_input,
        existing_entity_input,
        new_column_input,
        new_column_type_input,
    ],
    action=update_my_app_name_test_update,
    retries=0,
    upstream=validate_add_my_app_name_column,
)

update_my_app_name_test_delete_task = Task(
    name="update-my-app-name-test-delete",
    input=[
        existing_module_input,
        existing_entity_input,
        new_column_input,
        new_column_type_input,
    ],
    action=update_my_app_name_test_delete,
    retries=0,
    upstream=validate_add_my_app_name_column,
)


create_my_app_name_entity_migration = CmdTask(
    name="create-my-app-name-entity-migration",
    input=[
        existing_module_input,
        existing_entity_input,
        new_column_input,
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
            'alembic revision --autogenerate -m "create_{to_snake_case(ctx.input.entity)}_{to_snake_case(ctx.input.column)}_column"',  # noqa
        ),
    ],
    render_cmd=False,
    retries=0,
    upstream=[
        prepare_venv,
        update_my_app_name_schema_task,
    ],
)


add_my_app_name_column = app_create_group.add_task(
    Task(
        name="add-my-app-name-column",
        description="📊 Create new column on an entity",
        upstream=[
            update_my_app_name_schema_task,
            update_my_app_name_ui_task,
            update_my_app_name_test_create_task,
            update_my_app_name_test_read_task,
            update_my_app_name_test_update_task,
            update_my_app_name_test_delete_task,
            create_my_app_name_entity_migration,
        ],
        successor=format_my_app_name_code,
        retries=0,
    ),
    alias="column",
)
