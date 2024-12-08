import os
from fastapp._zrb.group import app_create_group
from fastapp._zrb.helper import (
    get_existing_module_names, get_existing_schema_names
)
from fastapp._zrb.input import (
    existing_module_input,
    new_entity_input,
    new_entity_column_input,
    plural_entity_input
)
from fastapp._zrb.config import APP_DIR
from zrb.util.string.conversion import to_snake_case, to_kebab_case

from zrb import AnyContext, Scaffolder, Task, make_task


@make_task(
    name="validate-create-fastapp-entity",
    input=[
        existing_module_input,
        new_entity_input,
        plural_entity_input,
        new_entity_column_input,
    ],
    retries=0,
)
def validate_create_fastapp_entity(ctx: AnyContext):
    module_name = to_snake_case(ctx.input.module)
    if module_name not in get_existing_module_names():
        raise ValueError(f"Module not exist: {module_name}")
    schema_name = to_snake_case(ctx.input.entity)
    if schema_name in get_existing_schema_names():
        raise ValueError(f"Schema already exists: {schema_name}")


scaffold_fastapp_schema = Scaffolder(
    name="scaffold-fastapp-schema",
    input=[
        existing_module_input,
        new_entity_input,
        new_entity_column_input,
    ],
    source_path=os.path.join(os.path.dirname(__file__), "schema.template.py"),
    render_source_path=False,
    destination_path=lambda ctx: os.path.join(
        APP_DIR, "schema", f"{to_snake_case(ctx.input.entity)}.py",
    ),
    transform_content={
        "MyEntity": "{to_pascal_case(ctx.input.entity)}",
        "my_column": "{to_snake_case(ctx.input.column)}",
    },
    retries=0,
    upstream=validate_create_fastapp_entity,
)

scaffold_fastapp_module_entity = Scaffolder(
    name="scaffold-fastapp-schema",
    input=[
        existing_module_input,
        new_entity_input,
        plural_entity_input,
    ],
    source_path=os.path.join(os.path.dirname(__file__), "module_template"),
    render_source_path=False,
    destination_path=lambda ctx: os.path.join(
        APP_DIR, "module", f"{to_snake_case(ctx.input.module)}",
    ),
    transform_content={
        "my_module": "{to_snake_case(ctx.input.module)}",
        "MyEntity": "{to_pascal_case(ctx.input.entity)}",
        "my_entity": "{to_snake_case(ctx.input.entity)}",
        "my_entities": "{to_snake_case(ctx.input.plural)}",
        "my-entities": "{to_kebab_case(ctx.input.plural)}",
    },
    retries=0,
    upstream=validate_create_fastapp_entity,
 
)

create_fastapp_entity = app_create_group.add_task(
    Task(
        name="create-fastapp-entity",
        description="🏗️ Create new entity on a module",
        successor="",
    ),
    alias="entity",
)
create_fastapp_entity << [
    scaffold_fastapp_schema,
    scaffold_fastapp_module_entity,
]
