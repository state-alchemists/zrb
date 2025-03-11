import os
import re
import textwrap

from bs4 import BeautifulSoup, Tag, formatter
from my_app_name._zrb.config import APP_DIR

from zrb.context.any_context import AnyContext
from zrb.util.codemod.modify_class_property import append_property_to_class
from zrb.util.file import read_file, write_file
from zrb.util.string.conversion import (
    to_human_case,
    to_kebab_case,
    to_pascal_case,
    to_snake_case,
)


def update_my_app_name_schema(ctx: AnyContext):
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


def update_my_app_name_ui(ctx: AnyContext):
    kebab_module_name = to_kebab_case(ctx.input.module)
    kebab_entity_name = to_kebab_case(ctx.input.entity)
    snake_column_name = to_snake_case(ctx.input.column)
    human_column_name = to_human_case(ctx.input.column).title()
    column_type = ctx.input.type
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
    # Forms
    new_code = _add_input_to_form(
        new_code,
        form_id="crud-create-form",
        column_label=human_column_name,
        column_name=snake_column_name,
        column_type=column_type,
    )
    new_code = _add_input_to_form(
        new_code,
        form_id="crud-update-form",
        column_label=human_column_name,
        column_name=snake_column_name,
        column_type=column_type,
    )
    new_code = _add_input_to_form(
        new_code,
        form_id="crud-delete-form",
        column_label=human_column_name,
        column_name=snake_column_name,
        column_type=column_type,
    )
    # JS Function
    new_code = _alter_js_function_returned_array(
        new_code,
        js_function_name="getRowComponents",
        js_array_name="rowComponents",
        js_new_value=f"`<td>${{row.{snake_column_name}}}</td>`",
    )
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


def _add_input_to_form(
    html_str: str, form_id: str, column_label: str, column_name: str, column_type: str
) -> str:
    soup = BeautifulSoup(html_str, "html.parser")
    # Find the form by id.
    form = soup.find("form", id=form_id)
    if not form:
        return html_str  # Return unchanged if no matching form is found.
    # Create a new label element with the provided column label.
    new_label = soup.new_tag("label")
    new_label.append(f"{column_label}: ")
    # Create a new input element with the provided column name.
    new_input = _get_html_input(soup, column_name, column_type)
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


def _get_html_input(soup: BeautifulSoup, column_name: str, column_type: str) -> Tag:
    # Map your custom types to HTML input types.
    type_mapping = {
        "str": "text",
        "int": "number",
        "float": "number",
        "bool": "checkbox",
        "datetime": "datetime-local",
        "date": "date",
    }
    # Get the corresponding HTML input type; default to "text" if not found.
    html_input_type = type_mapping.get(column_type, "text")
    # Create the new input tag with the appropriate attributes.
    new_input = soup.new_tag(
        "input",
        attrs={"type": html_input_type, "name": column_name, "required": "required"},
    )
    return new_input


def _infer_html_indent_width(html_str: str) -> int:
    """
    Infer the indentation width (number of spaces) from the HTML string.
    It looks for the first non-empty line that starts with whitespace
    followed by '<' and returns the number of leading spaces.
    If none is found, defaults to 2.
    """
    for line in textwrap.dedent(html_str).splitlines():
        stripped = line.lstrip()
        if stripped.startswith("<") and line != stripped:
            return len(line) - len(stripped)
    return 2


def _alter_js_function_returned_array(
    html_str: str, js_function_name: str, js_array_name: str, js_new_value: str
) -> str:
    """
    Inserts a new push into the specified JavaScript function.

    It finds the function definition with the given js_function_name,
    then looks for the first return statement inside the function body,
    and inserts a new line that pushes js_new_value into js_arr_name.

    Parameters:
        html_str (str): The HTML containing the JavaScript.
        js_function_name (str): The name of the JavaScript function to modify.
        js_arr_name (str): The name of the array inside that function.
        js_new_value (str): The new value to push. (Pass the JS literal as a string,
                            e.g. "`<td>NEW</td>`" or '"<td>NEW</td>"'.)

    Returns:
        str: The modified HTML.
    """
    # This pattern finds:
    #  1. The function signature and opening brace.
    #  2. All content (non-greedily) until we hit a newline containing a return statement.
    #  3. Captures the newline and leading whitespace (indent) of the return statement.
    #  4. Captures the rest of the return line.
    pattern = (
        r"("
        + re.escape(js_function_name)
        + r"\s*\([^)]*\)\s*\{)"  # group1: function header
        r"([\s\S]*?)"  # group2: code before return
        r"(\n(\s*)return\s+[^;]+;)"  # group3: newline+return line, group4: indent
    )

    def replacer(match):
        header = match.group(1)
        before_return = match.group(2)
        return_line = match.group(3)
        indent = match.group(4)
        # Create the new push statement. We add a newline plus the same indent.
        # The resulting line will be, e.g.,
        # "        rowComponents.push(`<td>NEW</td>`);"
        injection = f"\n{indent}{js_array_name}.push({js_new_value});"
        return header + before_return + injection + return_line

    # Use re.sub to replace only the first occurrence of the function
    new_html, count = re.subn(
        pattern, replacer, html_str, count=1, flags=re.MULTILINE | re.DOTALL
    )
    return new_html


def update_my_app_name_test_create(ctx: AnyContext):
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


def update_my_app_name_test_read(ctx: AnyContext):
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


def update_my_app_name_test_update(ctx: AnyContext):
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


def update_my_app_name_test_delete(ctx: AnyContext):
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
