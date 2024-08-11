import os

from zrb.helper.file.text import read_text_file_async, write_text_file_async
from zrb.helper.typecheck import typechecked
from zrb.helper.util import to_capitalized_human_readable, to_kebab_case, to_snake_case
from zrb.task.task import Task

from ._common import get_app_frontend_routes_dir, replace_marker


@typechecked
async def inject_list_page(
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
    column_caption = to_capitalized_human_readable(column_name)
    file_path = os.path.join(
        get_app_frontend_routes_dir(project_dir, app_name),
        kebab_module_name,
        kebab_entity_name,
        "+page.svelte",
    )
    task.print_out(f"Read HTML from: {file_path}")
    html_content = await read_text_file_async(file_path)
    # process header
    task.print_out("Add column header to table")
    html_content = replace_marker(
        html_content,
        marker="<!-- DON'T DELETE: insert new column header here-->",
        code=f"<th>{column_caption}</th>",
    )
    # process column
    task.print_out("Add column to table")
    html_content = replace_marker(
        html_content,
        marker="<!-- DON'T DELETE: insert new column here-->",
        code=f"<td>{{row.{snake_column_name}}}</td>",
    )
    task.print_out(f"Write modified HTML to: {file_path}")
    await write_text_file_async(file_path, html_content)
