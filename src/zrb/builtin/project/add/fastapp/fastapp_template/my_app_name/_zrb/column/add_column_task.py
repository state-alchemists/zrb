import os

from my_app_name._zrb.config import APP_DIR
from my_app_name._zrb.format_task import format_my_app_name_code
from my_app_name._zrb.group import app_create_group
from my_app_name._zrb.input import (
    existing_entity_input,
    new_column_input,
    new_column_type_input,
)
from my_app_name._zrb.util import get_existing_schema_names

from zrb import AnyContext, Task, make_task
from zrb.util.codemod.prepend_property_to_class import prepend_property_to_class
from zrb.util.file import read_file, write_file
from zrb.util.string.conversion import to_pascal_case, to_snake_case


@make_task(
    name="validate-add-my-app-name-column",
    input=existing_entity_input,
    retries=0,
)
async def validate_add_my_app_name_column(ctx: AnyContext):
    schema_name = ctx.input.entity
    if schema_name not in get_existing_schema_names():
        raise ValueError(f"Schema not exist: {schema_name}")


@make_task(
    name="update-my-app-name-schema",
    input=[
        existing_entity_input,
        new_column_input,
        new_column_type_input,
    ],
    retries=0,
    upstream=validate_add_my_app_name_column,
)
def update_my_app_name_schema(ctx: AnyContext):
    snake_entity_name = to_snake_case(ctx.input.entity)
    pascal_entity_name = to_pascal_case(ctx.input.entity)
    schema_file_path = os.path.join(APP_DIR, "schema", f"{snake_entity_name}.py")
    existing_code = read_file(schema_file_path)
    snake_column_name = to_snake_case(ctx.input.column)
    column_type = ctx.input.type
    # Base
    new_code = prepend_property_to_class(
        original_code=existing_code,
        class_name=f"{pascal_entity_name}Base",
        property_name=snake_column_name,
        annotation=column_type,
        default_value=_get_default_value(column_type),
    )
    # Update
    new_code = prepend_property_to_class(
        original_code=new_code,
        class_name=f"{pascal_entity_name}Update",
        property_name=snake_column_name,
        annotation=f"{column_type} | None",
        default_value="None",
    )
    # Table
    new_code = prepend_property_to_class(
        original_code=new_code,
        class_name=f"{pascal_entity_name}",
        property_name=snake_column_name,
        annotation=f"{column_type} | None",
        default_value="Field(index=False)",
    )
    write_file(schema_file_path, new_code)


add_my_app_name_column = app_create_group.add_task(
    Task(
        name="add-my-app-name-column",
        description="📊 Create new column on an entity",
        upstream=update_my_app_name_schema,
        successor=format_my_app_name_code,
        retries=0,
    ),
    alias="column",
)


def _get_default_value(data_type: str) -> str:
    if data_type == "str":
        return '""'
    if data_type in ("int", "float"):
        return "0"
    if data_type == "bool":
        return "True"
    return "None"
