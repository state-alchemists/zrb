import re
from typing import Any


def fstring_format(template: str, data: dict[str, Any]) -> str:
    """
    Format a string template using f-string-like syntax with data from a dictionary.

    Expressions within curly braces `{}` are evaluated using the provided data.

    Args:
        template (str): The string template to format.
        data (dict[str, Any]): The dictionary containing data for expression evaluation.

    Returns:
        str: The formatted string.

    Raises:
        ValueError: If an expression in the template fails to evaluate or the
            template is invalid.
    """

    def replace_expr(match):
        """
        Helper function to evaluate a single expression found in the template.
        """
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
