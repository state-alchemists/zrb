import os

from zrb.helper.string.parse_replacement import parse_replacement
from zrb.helper.util import to_kebab_case, to_snake_case


def replace_marker(text: str, marker: str, code: str) -> str:
    return parse_replacement(text, {marker: "\n".join([code, marker])})


def get_app_frontend_routes_dir(project_dir: str, app_name: str) -> str:
    return os.path.join(
        get_app_dir(project_dir, app_name), "src", "frontend", "src", "routes"
    )


def get_app_dir(project_dir: str, app_name: str) -> str:
    kebab_app_name = to_kebab_case(app_name)
    return os.path.join(project_dir, "src", kebab_app_name)


def get_sqlalchemy_column_type(column_type: str) -> str:
    default_value = "String"
    type_map = {
        "string": default_value,
        "text": "Text",
        "boolean": "Boolean",
        "integer": "Integer",
        "float": "Float",
        "double": "Double",
        "date": "Date",
        "datetime": "DateTime",
        "time": "Time",
    }
    column_type = column_type.lower()
    return type_map.get(column_type.lower(), default_value)


def get_python_column_type(column_type: str) -> str:
    default_value = "str"
    type_map = {
        "string": default_value,
        "text": "str",
        "boolean": "bool",
        "integer": "int",
        "float": "float",
        "double": "double",
        "date": "date",
        "datetime": "datetime",
        "time": "time",
    }
    return type_map.get(column_type.lower(), default_value)


def get_python_value_for_testing(column_type: str) -> str:
    default_value = '"A string"'
    type_map = {
        "string": default_value,
        "text": '"A text"',
        "boolean": "True",
        "integer": "42",
        "float": "3.14",
        "double": "3.14",
        "date": "date(2024, 8, 10)",
        "datetime": "datetime(2024, 8, 10, 14, 30)",
        "time": "time(14, 30)",
    }
    return type_map.get(column_type.lower(), default_value)


def get_default_js_value(column_type: str) -> str:
    default_value = '""'
    type_map = {
        "string": default_value,
        "text": '""',
        "boolean": "true",
        "integer": "0",
        "float": "0.0",
        "double": "0.0",
        "date": "new Date()",
        "datetime": "new Date()",
        "time": "new Date().toLocaleTimeString('en-US', { hour12: false })",
    }
    return type_map.get(column_type.lower(), default_value)


def get_html_input(column_type: str, column_name: str, column_caption: str) -> str:
    snake_column_name = to_snake_case(column_name)
    kebab_column_name = to_kebab_case(column_name)
    default_value = f'<input type="text" class="input w-full" id="{kebab_column_name}" placeholder="{column_caption}" bind:value="{{row.{snake_column_name}}}" />'  # noqa
    type_map = {
        "string": default_value,
        "text": f'<textarea class="textarea w-full" id="{kebab_column_name}" placeholder="{column_caption}" bind:value="{{row.{snake_column_name}}}"></textarea>',  # noqa
        "boolean": f'<input type="checkbox" class="checkbox" id="{kebab_column_name}" bind:checked="{{row.{snake_column_name}}}" />',  # noqa
        "integer": f'<input type="number" class="input w-full" id="{kebab_column_name}" placeholder="{column_caption}" bind:value="{{row.{snake_column_name}}}" />',  # noqa
        "float": f'<input type="number" step="0.01" class="input w-full" id="{kebab_column_name}" placeholder="{column_caption}" bind:value="{{row.{snake_column_name}}}" />',  # noqa
        "double": f'<input type="number" step="0.01" class="input w-full" id="{kebab_column_name}" placeholder="{column_caption}" bind:value="{{row.{snake_column_name}}}" />',  # noqa
        "date": f'<input type="date" class="input w-full" id="{kebab_column_name}" placeholder="{column_caption}" bind:value="{{row.{snake_column_name}}}" />',  # noqa
        "datetime": f'<input type="datetime-local" class="input w-full" id="{kebab_column_name}" placeholder="{column_caption}" bind:value="{{row.{snake_column_name}}}" />',  # noqa
        "time": f'<input type="time" class="input w-full" id="{kebab_column_name}" placeholder="{column_caption}" bind:value="{{row.{snake_column_name}}}" />',  # noqa
    }
    return type_map.get(column_type.lower(), default_value)
