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
    # Step 1: Replace escaped braces with unique tokens (temporary)
    template = template.replace("{{", "\u0000").replace("}}", "\u0001")

    # Step 2: Replace real expressions {expr}
    def eval_expr(match: re.Match) -> str:
        expr = match.group(1)
        try:
            return str(eval(expr, {}, data))
        except Exception as e:
            raise ValueError(f"Error evaluating expression '{expr}': {e}")

    rendered = re.sub(r"\{([^{}]+)\}", eval_expr, template)

    # Step 3: Restore escaped braces
    return rendered.replace("\u0000", "{").replace("\u0001", "}")
