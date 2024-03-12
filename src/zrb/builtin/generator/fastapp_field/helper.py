import os
import re

from zrb.helper.codemod.add_key_value_to_dict import add_key_value_to_dict
from zrb.helper.codemod.add_property_to_class import add_property_to_class
from zrb.helper.file.text import read_text_file_async, write_text_file_async
from zrb.helper.typecheck import typechecked
from zrb.task.task import Task


@typechecked
async def add_column_to_insert_page(
    task: Task,
    project_dir: str,
    kebab_app_name: str,
    kebab_module_name: str,
    kebab_entity_name: str,
    kebab_column_name: str,
    snake_column_name: str,
    capitalized_human_readable_column_name: str,
):
    list_page_file_path = os.path.join(
        project_dir,
        "src",
        kebab_app_name,
        "src",
        "frontend",
        "src",
        "routes",
        kebab_module_name,
        kebab_entity_name,
        "new",
        "+page.svelte",
    )
    task.print_out(f"Read HTML from: {list_page_file_path}")
    html_content = await read_text_file_async(list_page_file_path)
    task.print_out("Add default value to insert page")
    default_value_regex = r"(.*)(// DON'T DELETE: set field default value here)"  # noqa
    default_value_subst = "\\n".join([f"\\1row.{snake_column_name} = '';", "\\1\\2"])
    html_content = re.sub(
        default_value_regex, default_value_subst, html_content, 0, re.MULTILINE
    )
    task.print_out("Add field to insert page")
    field_regex = r"(.*)(<!-- DON'T DELETE: insert new field here-->)"
    field_subst = "\\n".join(
        [
            '\\1<div class="mb-4">',
            f'\\1    <label class="block text-gray-700 font-bold mb-2" for="{kebab_column_name}">{capitalized_human_readable_column_name}</label>',  # noqa
            f'\\1    <input type="text" class="input w-full" id="{kebab_column_name}" placeholder="{capitalized_human_readable_column_name}" bind:value='
            + "{row."
            + snake_column_name
            + "} />",  # noqa
            "\\1</div>",
            "\\1\\2",
        ]
    )
    html_content = re.sub(field_regex, field_subst, html_content, 0, re.MULTILINE)
    task.print_out(f"Write modified HTML to: {list_page_file_path}")
    await write_text_file_async(list_page_file_path, html_content)


@typechecked
async def add_column_to_update_page(
    task: Task,
    project_dir: str,
    kebab_app_name: str,
    kebab_module_name: str,
    kebab_entity_name: str,
    kebab_column_name: str,
    snake_column_name: str,
    capitalized_human_readable_column_name: str,
):
    list_page_file_path = os.path.join(
        project_dir,
        "src",
        kebab_app_name,
        "src",
        "frontend",
        "src",
        "routes",
        kebab_module_name,
        kebab_entity_name,
        "update",
        "[id]",
        "+page.svelte",
    )
    task.print_out(f"Read HTML from: {list_page_file_path}")
    html_content = await read_text_file_async(list_page_file_path)
    task.print_out("Add field to update page")
    regex = r"(.*)(<!-- DON'T DELETE: insert new field here-->)"
    subst = "\\n".join(
        [
            '\\1<div class="mb-4">',
            f'\\1    <label class="block text-gray-700 font-bold mb-2" for="{kebab_column_name}">{capitalized_human_readable_column_name}</label>',  # noqa
            f'\\1    <input type="text" class="input w-full" id="{kebab_column_name}" placeholder="{capitalized_human_readable_column_name}" bind:value='
            + "{row."
            + snake_column_name
            + "} />",  # noqa
            "\\1</div>",
            "\\1\\2",
        ]
    )
    html_content = re.sub(regex, subst, html_content, 0, re.MULTILINE)
    task.print_out(f"Write modified HTML to: {list_page_file_path}")
    await write_text_file_async(list_page_file_path, html_content)


@typechecked
async def add_column_to_delete_page(
    task: Task,
    project_dir: str,
    kebab_app_name: str,
    kebab_module_name: str,
    kebab_entity_name: str,
    kebab_column_name: str,
    snake_column_name: str,
    capitalized_human_readable_column_name: str,
):
    list_page_file_path = os.path.join(
        project_dir,
        "src",
        kebab_app_name,
        "src",
        "frontend",
        "src",
        "routes",
        kebab_module_name,
        kebab_entity_name,
        "delete",
        "[id]",
        "+page.svelte",
    )
    task.print_out(f"Read HTML from: {list_page_file_path}")
    html_content = await read_text_file_async(list_page_file_path)
    task.print_out("Add field to delete page")
    regex = r"(.*)(<!-- DON'T DELETE: insert new field here-->)"
    subst = "\\n".join(
        [
            '\\1<div class="mb-4">',
            f'\\1    <label class="block text-gray-700 font-bold mb-2" for="{kebab_column_name}">{capitalized_human_readable_column_name}</label>',  # noqa
            f'\\1    <span id="{kebab_column_name}">'
            + "{row."
            + snake_column_name
            + "}</span>",  # noqa
            "\\1</div>",
            "\\1\\2",
        ]
    )
    html_content = re.sub(regex, subst, html_content, 0, re.MULTILINE)
    task.print_out(f"Write modified HTML to: {list_page_file_path}")
    await write_text_file_async(list_page_file_path, html_content)


@typechecked
async def add_column_to_detail_page(
    task: Task,
    project_dir: str,
    kebab_app_name: str,
    kebab_module_name: str,
    kebab_entity_name: str,
    kebab_column_name: str,
    snake_column_name: str,
    capitalized_human_readable_column_name: str,
):
    list_page_file_path = os.path.join(
        project_dir,
        "src",
        kebab_app_name,
        "src",
        "frontend",
        "src",
        "routes",
        kebab_module_name,
        kebab_entity_name,
        "detail",
        "[id]",
        "+page.svelte",
    )
    task.print_out(f"Read HTML from: {list_page_file_path}")
    html_content = await read_text_file_async(list_page_file_path)
    task.print_out("Add field to detail page")
    regex = r"(.*)(<!-- DON'T DELETE: insert new field here-->)"
    subst = "\\n".join(
        [
            '\\1<div class="mb-4">',
            f'\\1    <label class="block text-gray-700 font-bold mb-2" for="{kebab_column_name}">{capitalized_human_readable_column_name}</label>',  # noqa
            f'\\1    <span id="{kebab_column_name}">'
            + "{row."
            + snake_column_name
            + "}</span>",  # noqa
            "\\1</div>",
            "\\1\\2",
        ]
    )
    html_content = re.sub(regex, subst, html_content, 0, re.MULTILINE)
    task.print_out(f"Write modified HTML to: {list_page_file_path}")
    await write_text_file_async(list_page_file_path, html_content)


@typechecked
async def add_column_to_list_page(
    task: Task,
    project_dir: str,
    kebab_app_name: str,
    kebab_module_name: str,
    kebab_entity_name: str,
    snake_column_name: str,
    capitalized_human_readable_column_name: str,
):
    list_page_file_path = os.path.join(
        project_dir,
        "src",
        kebab_app_name,
        "src",
        "frontend",
        "src",
        "routes",
        kebab_module_name,
        kebab_entity_name,
        "+page.svelte",
    )
    task.print_out(f"Read HTML from: {list_page_file_path}")
    html_content = await read_text_file_async(list_page_file_path)
    # process header
    task.print_out("Add column header to table")
    header_regex = r"(.*)(<!-- DON'T DELETE: insert new column header here-->)"
    header_subst = "\\n".join(
        [f"\\1<th>{capitalized_human_readable_column_name}</th>", "\\1\\2"]
    )
    html_content = re.sub(header_regex, header_subst, html_content, 0, re.MULTILINE)
    # process column
    task.print_out("Add column to table")
    column_regex = r"(.*)(<!-- DON'T DELETE: insert new column here-->)"
    column_subst = "\\n".join(["\\1<td>{row." + snake_column_name + "}</td>", "\\1\\2"])
    html_content = re.sub(column_regex, column_subst, html_content, 0, re.MULTILINE)
    task.print_out(f"Write modified HTML to: {list_page_file_path}")
    await write_text_file_async(list_page_file_path, html_content)


@typechecked
async def add_column_to_test(
    task: Task,
    project_dir: str,
    kebab_app_name: str,
    snake_module_name: str,
    snake_entity_name: str,
    snake_column_name: str,
    column_type: str,
):
    test_file_path = os.path.join(
        project_dir,
        "src",
        kebab_app_name,
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
    for dict_name in dict_names:
        code = add_key_value_to_dict(
            code=code, dict_name=dict_name, key=f"'{snake_column_name}'", value="''"
        )
    task.print_out(f"Write modified code to: {test_file_path}")
    await write_text_file_async(test_file_path, code)


@typechecked
async def add_column_to_schema(
    task: Task,
    project_dir: str,
    kebab_app_name: str,
    snake_module_name: str,
    snake_entity_name: str,
    pascal_entity_name: str,
    snake_column_name: str,
    column_type: str,
):
    schema_file_path = os.path.join(
        project_dir,
        "src",
        kebab_app_name,
        "src",
        "module",
        snake_module_name,
        "schema",
        f"{snake_entity_name}.py",
    )
    task.print_out(f"Read code from: {schema_file_path}")
    code = await read_text_file_async(schema_file_path)
    task.print_out(f'Add column "{snake_column_name}" to the schema')
    code = add_property_to_class(
        code=code,
        class_name=f"{pascal_entity_name}Data",
        property_name=snake_column_name,
        property_type="Optional[str]",
    )
    task.print_out(f"Write modified code to: {schema_file_path}")
    await write_text_file_async(schema_file_path, code)


@typechecked
async def add_column_to_repo(
    task: Task,
    project_dir: str,
    kebab_app_name: str,
    snake_module_name: str,
    snake_entity_name: str,
    pascal_entity_name: str,
    snake_column_name: str,
    column_type: str,
):
    repo_file_path = os.path.join(
        project_dir,
        "src",
        kebab_app_name,
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
    code = add_property_to_class(
        code=code,
        class_name=f"DBEntity{pascal_entity_name}",
        property_name=snake_column_name,
        property_type="Column",
        property_value="Column(String)",
    )
    task.print_out(f"Write modified code to: {repo_file_path}")
    await write_text_file_async(repo_file_path, code)
