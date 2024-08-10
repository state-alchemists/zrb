import os

from zrb.helper.file.text import read_text_file_async, write_text_file_async
from zrb.helper.typecheck import typechecked
from zrb.helper.util import to_capitalized_human_readable, to_kebab_case, to_snake_case
from zrb.task.task import Task

from ._common import get_app_frontend_routes_dir, replace_marker


@typechecked
async def inject_delete_page(
    task: Task,
    project_dir: str,
    app_name: str,
    module_name: str,
    entity_name: str,
    column_name: str,
):
    kebab_module_name = to_kebab_case(module_name)
    kebab_entity_name = to_kebab_case(entity_name)
    snake_column_name = to_snake_case(column_name)
    kebab_column_name = to_kebab_case(column_name)
    column_caption = to_capitalized_human_readable(column_name)
    file_path = os.path.join(
        get_app_frontend_routes_dir(project_dir, app_name),
        kebab_module_name,
        kebab_entity_name,
        "delete",
        "[id]",
        "+page.svelte",
    )
    task.print_out(f"Read HTML from: {file_path}")
    html_content = await read_text_file_async(file_path)
    task.print_out("Add field to delete page")
    html_content = replace_marker(
        html_content,
        marker="<!-- DON'T DELETE: insert new field here-->",
        code="\n".join(
            [
                '<div class="mb-4">',
                f'    <label class="block text-gray-700 font-bold mb-2" for="{kebab_column_name}">{column_caption}</label>',  # noqa
                f'    <span id="{kebab_column_name}">{{row.{snake_column_name}}}</span>',
                "</div>",
            ]
        ),
    )
    task.print_out(f"Write modified HTML to: {file_path}")
    await write_text_file_async(file_path, html_content)
