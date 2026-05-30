import re
from typing import Any

# Safe builtins for template expression evaluation.
# Dangerous builtins (__import__, open, eval, exec, compile, getattr, type, etc.)
# are intentionally excluded to prevent RCE and sandbox escape.
_SAFE_BUILTINS: dict[str, Any] = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "isinstance": isinstance,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "range": range,
    "reversed": reversed,
    "round": round,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}


def fstring_format(template: str, data: dict[str, Any]) -> str:
    """
    Format a string template using f-string-like syntax with data from a dictionary.

    Expressions within curly braces `{}` are evaluated using the provided data.
    Templates are authored by developers (not end-user input), so ``eval`` with a
    restricted builtins whitelist is acceptable for this use case.

    Only safe builtins (type conversions, math utilities, iteration helpers) are
    available. Dangerous functions like __import__, open, eval, and exec are blocked.

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
    eval_globals: dict[str, Any] = {"__builtins__": _SAFE_BUILTINS}

    def eval_expr(match: re.Match) -> str:
        expr = match.group(1)
        try:
            return str(eval(expr, eval_globals, data))
        except Exception as e:
            raise ValueError(f"Error evaluating expression '{expr}': {e}")

    rendered = re.sub(r"\{([^{}]+)\}", eval_expr, template)

    # Step 3: Restore escaped braces
    return rendered.replace("\u0000", "{").replace("\u0001", "}")
