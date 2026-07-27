import ast
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

    **The template is the trust boundary, not ``data``.** Values in ``data`` are
    only bound as names, so untrusted values are harmless — but the template
    itself is executed, so it must always come from developer-authored code
    (task definitions, input defaults) and never from end-user, LLM, or
    request-supplied strings.

    Only safe builtins (type conversions, math utilities, iteration helpers) are
    available, and dunder names are rejected before evaluation. Together those
    block the usual sandbox escape, which reaches the real builtins by walking
    the class hierarchy (``().__class__.__bases__[0].__subclasses__()``) — a
    builtins whitelist alone cannot stop it, because plain attribute access is
    not governed by the eval globals.

    Args:
        template (str): The string template to format.
        data (dict[str, Any]): The dictionary containing data for expression evaluation.

    Returns:
        str: The formatted string.

    Raises:
        ValueError: If an expression in the template fails to evaluate, uses a
            dunder name, or the template is invalid.
    """
    # Step 1: Replace escaped braces with unique tokens (temporary)
    template = template.replace("{{", "\u0000").replace("}}", "\u0001")

    # Step 2: Replace real expressions {expr}
    eval_globals: dict[str, Any] = {"__builtins__": _SAFE_BUILTINS}

    def eval_expr(match: re.Match) -> str:
        expr = match.group(1)
        try:
            return str(eval(_compile_expression(expr), eval_globals, data))
        except Exception as e:
            raise ValueError(f"Error evaluating expression '{expr}': {e}")

    rendered = re.sub(r"\{([^{}]+)\}", eval_expr, template)

    # Step 3: Restore escaped braces
    return rendered.replace("\u0000", "{").replace("\u0001", "}")


def _compile_expression(expr: str) -> Any:
    """Parse and compile a template expression, rejecting dunder access.

    Dunder attributes and names are the only route from the restricted builtins
    back to the real ones, so refusing them keeps evaluation inside the
    whitelist. Single-underscore names stay allowed — templates legitimately
    touch private-ish attributes, and those cannot escape on their own.
    """
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            name = node.attr
        elif isinstance(node, ast.Name):
            name = node.id
        else:
            continue
        if name.startswith("__"):
            raise ValueError(f"dunder name '{name}' is not allowed in templates")
    return compile(tree, "<template>", "eval")
