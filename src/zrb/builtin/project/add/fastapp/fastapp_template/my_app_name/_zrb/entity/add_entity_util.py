import os

from my_app_name._zrb.config import APP_DIR

from zrb.context.any_context import AnyContext
from zrb.util.codemod.append_key_to_dict import append_key_to_dict
from zrb.util.file import read_file, write_file
from zrb.util.string.conversion import to_kebab_case, to_pascal_case, to_snake_case


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
