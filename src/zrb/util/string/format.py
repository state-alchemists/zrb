from typing import Any


def fstring_format(template: str, data: dict[str, Any]) -> str:
    # Escape any backslashes and quotes in the template
    escaped_template = template.replace("\\", "\\\\").replace('"', '\\"')
    # Construct the f-string expression
    f_string_expr = f'f"{escaped_template}"'
    # Safely evaluate the template as a Python expression
    try:
        return eval(f_string_expr, {}, data)
    except Exception as e:
        raise ValueError(f"Failed to parse template: {template}: {e}")
