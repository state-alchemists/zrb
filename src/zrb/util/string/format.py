import ast
from collections.abc import Callable
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
    A doubled brace is a literal one (`{{` → `{`, `}}` → `}`), so `{{{x}}}`
    renders `{` + the value of `x` + `}`.

    **The template is the trust boundary, not ``data``.** Values in ``data`` are
    only bound as names, so untrusted values are harmless — but the template
    itself is executed, so it must always come from developer-authored code
    (task definitions, input defaults) and never from end-user, LLM, or
    request-supplied strings.

    Only safe builtins are available, and dunder names are rejected, which
    blocks the class-hierarchy escape (``().__class__.__bases__...``).

    Raises:
        ValueError: If an expression in the template fails to evaluate, uses a
            dunder name, or the template is invalid.
    """
    eval_globals: dict[str, Any] = {"__builtins__": _SAFE_BUILTINS}

    def eval_expr(expr: str) -> str:
        try:
            return str(eval(_compile_expression(expr), eval_globals, data))
        except Exception as e:
            raise ValueError(f"Error evaluating expression '{expr}': {e}")

    return _render_template(template, eval_expr)


def _render_template(template: str, eval_expr: Callable[[str], str]) -> str:
    """Walk *template* once, unescaping `{{`/`}}` and evaluating `{...}`.

    A single pass is what makes `{{{x}}}` work: the first two braces are an
    escaped `{`, the last two an escaped `}`, and the expression between them is
    evaluated. Parking each escape as a sentinel first turned that template into
    one expression whose text ended in the sentinel, which raised.
    """
    rendered: list[str] = []
    index = 0
    length = len(template)
    while index < length:
        char = template[index]
        if char == "{" and template.startswith("{{", index):
            rendered.append("{")
            index += 2
            continue
        if char == "}" and template.startswith("}}", index):
            rendered.append("}")
            index += 2
            continue
        if char == "{":
            close = template.find("}", index + 1)
            expression = template[index + 1 : close] if close != -1 else ""
            # `{}` and an unclosed `{` stay literal, as do nested braces: an
            # expression is a single brace-free span, the same rule the regex
            # this replaced enforced.
            if close != -1 and expression and "{" not in expression:
                rendered.append(eval_expr(expression))
                index = close + 1
                continue
        rendered.append(char)
        index += 1
    return "".join(rendered)


def _compile_expression(expr: str) -> Any:
    """Parse and compile a template expression, rejecting dunder access.

    Dunders are the only route back to the real builtins; single-underscore
    names stay allowed.
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
