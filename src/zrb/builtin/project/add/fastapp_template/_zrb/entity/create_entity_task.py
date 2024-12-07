from fastapp_template._zrb.group import app_create_group
from fastapp_template._zrb.helper import (
    get_existing_module_names, get_existing_schema_names
)
from fastapp_template._zrb.input import existing_module_input, new_entity_input
from zrb.util.string.conversion import to_snake_case, to_kebab_case

from zrb import AnyContext, Task, make_task


@make_task(
    name="validate-create-my-app-name-module",
    input=[
        existing_module_input,
        new_entity_input,
    ],
    retries=0,
)
def validate_create_my_app_name_module(ctx: AnyContext):
    module_name = to_snake_case(ctx.input.module)
    if module_name not in get_existing_module_names():
        raise ValueError(f"Module not exist: {module_name}")
    schema_name = to_snake_case(ctx.input.entity)
    if schema_name in get_existing_schema_names():
        raise ValueError(f"Schema already exists: {schema_name}")


create_entity = app_create_group.add_task(
    Task(
        name="create-my-app-name-entity", description="🏗️ Create new entity on a module"
    ),
    alias="entity",
)
