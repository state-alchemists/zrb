import os
import textwrap

from bs4 import BeautifulSoup, formatter
from my_app_name._zrb.config import APP_DIR

from zrb.context.any_context import AnyContext
from zrb.util.codemod.modify_class import append_code_to_class
from zrb.util.codemod.modify_class_parent import prepend_parent_class
from zrb.util.codemod.modify_class_property import append_property_to_class
from zrb.util.codemod.modify_function import append_code_to_function
from zrb.util.codemod.modify_module import prepend_code_to_module
from zrb.util.file import read_file, write_file
from zrb.util.string.conversion import (
    to_human_case,
    to_kebab_case,
    to_pascal_case,
    to_snake_case,
)


def update_fastapp_schema(ctx: AnyContext):
    snake_entity_name = to_snake_case(ctx.input.entity)
    pascal_entity_name = to_pascal_case(ctx.input.entity)
    snake_column_name = to_snake_case(ctx.input.column)
    column_type = ctx.input.type
    schema_file_path = os.path.join(APP_DIR, "schema", f"{snake_entity_name}.py")
    existing_code = read_file(schema_file_path)
    # Base
    new_code = append_property_to_class(
        original_code=existing_code,
        class_name=f"{pascal_entity_name}Base",
        property_name=snake_column_name,
        annotation=column_type,
        default_value=_get_default_column_value(column_type),
    )
    # Update
    new_code = append_property_to_class(
        original_code=new_code,
        class_name=f"{pascal_entity_name}Update",
        property_name=snake_column_name,
        annotation=f"{column_type} | None",
        default_value="None",
    )
    # Table
    new_code = append_property_to_class(
        original_code=new_code,
        class_name=f"{pascal_entity_name}",
        property_name=snake_column_name,
        annotation=f"{column_type} | None",
        default_value="Field(index=False)",
    )
    write_file(schema_file_path, new_code)


def _get_default_column_value(data_type: str) -> str:
    if data_type == "str":
        return '""'
    if data_type in ("int", "float"):
        return "0"
    if data_type == "bool":
        return "True"
    return "None"


def update_fastapp_ui(ctx: AnyContext):
    kebab_module_name = to_kebab_case(ctx.input.module)
    kebab_entity_name = to_kebab_case(ctx.input.entity)
    human_column_name = to_human_case(ctx.input.column).title()
    subroute_file_path = os.path.join(
        APP_DIR,
        "module",
        "gateway",
        "view",
        "content",
        kebab_module_name,
        f"{kebab_entity_name}.html",
    )
    existing_code = read_file(subroute_file_path)
    # Add table header
    new_code = _add_th_before_last(
        existing_code, table_id="crud-table", th_content=human_column_name
    )
    # TODO: update UI
    write_file(subroute_file_path, new_code)


def _add_th_before_last(html_str, table_id, th_content):
    # Use the html.parser; you might try html5lib if you find that it preserves formatting better.
    soup = BeautifulSoup(html_str, "html.parser")
    # Locate the table with the specified id
    table = soup.find("table", id=table_id)
    if not table:
        # Table not found; return original HTML unchanged.
        return html_str
    # Find the thead element in the table.
    thead = table.find("thead")
    if not thead:
        return html_str
    # For this example, we assume there's a single row (<tr>) in the thead.
    row = thead.find("tr")
    if not row:
        return html_str
    # Find all existing th elements in the row.
    th_elements = row.find_all("th")
    if not th_elements:
        return html_str
    # Create a new th element and set its content.
    new_th = soup.new_tag("th")
    new_th.string = th_content
    # Insert the new th right before the last existing th.
    th_elements[-1].insert_before(new_th)
    # Return the modified HTML as a string.
    return soup.prettify(
        formatter=formatter.HTMLFormatter(indent=_infer_html_indent_width(html_str))
    )


def _add_input_to_form(html_str, form_id, column_label, column_name):
    soup = BeautifulSoup(html_str, "html.parser")
    # Find the form by id.
    form = soup.find("form", id=form_id)
    if not form:
        return html_str  # Return unchanged if no matching form is found.
    # Create a new label element with the provided column label.
    new_label = soup.new_tag("label")
    new_label.append(f"{column_label}: ")
    # Create a new input element with the provided column name.
    new_input = soup.new_tag("input", type="text", name=column_name, required=True)
    new_label.append(new_input)
    # Look for a footer element inside the form.
    footer = form.find("footer")
    if footer:
        # Insert the new label before the footer.
        footer.insert_before(new_label)
    else:
        # If no footer exists, simply append the new label to the form.
        form.append(new_label)
    return soup.prettify(
        formatter=formatter.HTMLFormatter(indent=_infer_html_indent_width(html_str))
    )


def _infer_html_indent_width(html_str):
    """
    Infer the indentation width (number of spaces) from the HTML string.
    It looks for the first non-empty line that starts with whitespace
    followed by '<' and returns the number of leading spaces.
    If none is found, defaults to 2.
    """
    for line in html_str.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("<") and line != stripped:
            return len(line) - len(stripped)
    return 2


def update_fastapp_test_create(ctx: AnyContext):
    snake_module_name = to_snake_case(ctx.input.module)
    snake_entity_name = to_snake_case(ctx.input.entity)
    test_file_path = os.path.join(
        APP_DIR,
        "test",
        snake_module_name,
        snake_entity_name,
        f"test_create_{snake_entity_name}.py",
    )
    existing_code = read_file(test_file_path)
    new_code = existing_code
    # TODO: update test
    write_file(test_file_path, new_code)


def update_fastapp_test_read(ctx: AnyContext):
    snake_module_name = to_snake_case(ctx.input.module)
    snake_entity_name = to_snake_case(ctx.input.entity)
    test_file_path = os.path.join(
        APP_DIR,
        "test",
        snake_module_name,
        snake_entity_name,
        f"test_read_{snake_entity_name}.py",
    )
    existing_code = read_file(test_file_path)
    new_code = existing_code
    # TODO: update test
    write_file(test_file_path, new_code)


def update_fastapp_test_update(ctx: AnyContext):
    snake_module_name = to_snake_case(ctx.input.module)
    snake_entity_name = to_snake_case(ctx.input.entity)
    test_file_path = os.path.join(
        APP_DIR,
        "test",
        snake_module_name,
        snake_entity_name,
        f"test_update_{snake_entity_name}.py",
    )
    existing_code = read_file(test_file_path)
    new_code = existing_code
    # TODO: update test
    write_file(test_file_path, new_code)


def update_fastapp_test_delete(ctx: AnyContext):
    snake_module_name = to_snake_case(ctx.input.module)
    snake_entity_name = to_snake_case(ctx.input.entity)
    test_file_path = os.path.join(
        APP_DIR,
        "test",
        snake_module_name,
        snake_entity_name,
        f"test_delete_{snake_entity_name}.py",
    )
    existing_code = read_file(test_file_path)
    new_code = existing_code
    # TODO: update test
    write_file(test_file_path, new_code)
