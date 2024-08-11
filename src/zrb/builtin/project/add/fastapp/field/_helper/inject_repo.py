import os

from zrb.helper.codemod.add_property_to_class import add_property_to_class
from zrb.helper.file.text import read_text_file_async, write_text_file_async
from zrb.helper.typecheck import typechecked
from zrb.helper.util import to_pascal_case, to_snake_case
from zrb.task.task import Task

from ._common import get_app_dir, get_sqlalchemy_column_type


@typechecked
async def inject_repo(
    task: Task,
    project_dir: str,
    app_name: str,
    module_name: str,
    entity_name: str,
    column_name: str,
    column_type: str,
):
    snake_module_name = to_snake_case(module_name)
    snake_entity_name = to_snake_case(entity_name)
    pascal_entity_name = to_pascal_case(entity_name)
    snake_column_name = to_snake_case(column_name)
    repo_file_path = os.path.join(
        get_app_dir(project_dir, app_name),
        "src",
        "module",
        snake_module_name,
        "entity",
        snake_entity_name,
        "repo.py",
    )
    task.print_out(f"Read code from: {repo_file_path}")
    code = await read_text_file_async(repo_file_path)
    task.print_out(f'Add column "{snake_column_name}" to the repo')
    sqlalchemy_column_type = get_sqlalchemy_column_type(column_type)
    code = add_property_to_class(
        code=code,
        class_name=f"DBEntity{pascal_entity_name}",
        property_name=snake_column_name,
        property_type="Column",
        property_value=f"Column({sqlalchemy_column_type})",
    )
    task.print_out(f"Write modified code to: {repo_file_path}")
    await write_text_file_async(repo_file_path, code)
