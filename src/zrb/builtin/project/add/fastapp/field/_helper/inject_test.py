import os

from zrb.helper.codemod.add_key_value_to_dict import add_key_value_to_dict
from zrb.helper.file.text import read_text_file_async, write_text_file_async
from zrb.helper.typecheck import typechecked
from zrb.helper.util import to_snake_case
from zrb.task.task import Task

from ._common import get_app_dir, get_python_value_for_testing


@typechecked
async def inject_test(
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
    snake_column_name = to_snake_case(column_name)
    test_file_path = os.path.join(
        get_app_dir(project_dir, app_name),
        "test",
        snake_module_name,
        f"test_{snake_entity_name}.py",
    )
    task.print_out(f"Read code from: {test_file_path}")
    code = await read_text_file_async(test_file_path)
    task.print_out(f'Add column "{snake_column_name}" to the test')
    dict_names = [
        "inserted_success_data",
        "to_be_updated_success_data",
        "updated_success_data",
        "to_be_deleted_success_data",
    ]
    default_python_value = get_python_value_for_testing(column_type)
    for dict_name in dict_names:
        code = add_key_value_to_dict(
            code=code,
            dict_name=dict_name,
            key=f"'{snake_column_name}'",
            value=default_python_value,
        )
    task.print_out(f"Write modified code to: {test_file_path}")
    await write_text_file_async(test_file_path, code)
