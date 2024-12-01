import re
from typing import Any


def fstring_format(template: str, data: dict[str, Any]) -> str:
    def replace_expr(match):
        expr = match.group(1)
        try:
            result = eval(expr, {}, data)
            return str(result)
        except Exception as e:
            raise ValueError(f"Failed to evaluate expression: {expr}: {e}")

    # Use regex to find and replace all expressions in curly braces
    pattern = r"\{([^}]+)\}"
    try:
        return re.sub(pattern, replace_expr, template)
    except Exception as e:
        raise ValueError(f"Failed to parse template: {template}: {e}")
