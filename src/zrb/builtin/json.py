import json
import re

from zrb.builtin.group import json_group
from zrb.context.any_context import AnyContext
from zrb.input.int_input import IntInput
from zrb.input.str_input import StrInput
from zrb.task.make_task import make_task


def _parse_json(ctx: AnyContext, text: str) -> object:
    """Parse JSON, raising a clear error that pinpoints the syntax problem."""
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        message = f"Invalid JSON at line {e.lineno} column {e.colno}: {e.msg}."
        ctx.print_err(f"❌ {message}")
        raise ValueError(message) from None


@make_task(
    name="format-json",
    description="✨ Pretty-print (indent) JSON",
    input=[
        StrInput(name="json", description="JSON text", prompt="JSON to format"),
        IntInput(
            name="indent",
            description="Indent size",
            prompt="Indent",
            default=2,
            always_prompt=False,
        ),
    ],
    retries=0,
    group=json_group,
    alias="format",
)
def format_json(ctx: AnyContext) -> str:

    result = json.dumps(
        _parse_json(ctx, ctx.input.json), indent=ctx.input.indent, ensure_ascii=False
    )
    ctx.print(result)
    return result


@make_task(
    name="minify-json",
    description="🗜️ Minify JSON (strip whitespace)",
    input=StrInput(name="json", description="JSON text", prompt="JSON to minify"),
    retries=0,
    group=json_group,
    alias="minify",
)
def minify_json(ctx: AnyContext) -> str:

    result = json.dumps(
        _parse_json(ctx, ctx.input.json), separators=(",", ":"), ensure_ascii=False
    )
    ctx.print(result)
    return result


@make_task(
    name="validate-json",
    description="✅ Validate JSON",
    input=StrInput(name="json", description="JSON text", prompt="JSON to validate"),
    retries=0,
    group=json_group,
    alias="validate",
)
def validate_json(ctx: AnyContext) -> bool:

    try:
        json.loads(ctx.input.json)
        ctx.print("Valid JSON")
        return True
    except json.JSONDecodeError as e:
        ctx.print(f"Invalid JSON at line {e.lineno} column {e.colno}: {e.msg}")
        return False


@make_task(
    name="get-json",
    description="🔎 Extract a value from JSON by dotted path (e.g. user.roles[0])",
    input=[
        StrInput(name="json", description="JSON text", prompt="JSON"),
        StrInput(
            name="path",
            description="Dotted path, e.g. 'a.b[0].c' (empty returns the root)",
            prompt="Path",
            default="",
        ),
    ],
    retries=0,
    group=json_group,
    alias="get",
)
def get_json(ctx: AnyContext) -> str:

    current = _parse_json(ctx, ctx.input.json)
    path = ctx.input.path
    traversed = ""
    # Split "a.b[0].c" into navigable tokens: keys (str) and indices (int).
    for token in re.findall(r"[^.\[\]]+|\[\d+\]", path):
        is_index = token.startswith("[") and token.endswith("]")
        try:
            if is_index:
                if not isinstance(current, (list, tuple)):
                    raise TypeError
                current = current[int(token[1:-1])]
            else:
                if not isinstance(current, dict):
                    raise TypeError
                current = current[token]
        except (KeyError, IndexError, TypeError):
            location = f"'{traversed}'" if traversed else "the root"
            message = (
                f"Path '{path}' not found: cannot resolve '{token}' on {location} "
                f"(value is {type(current).__name__})."
            )
            ctx.print_err(f"❌ {message}")
            raise ValueError(message) from None
        traversed = f"{traversed}{token}" if is_index else f"{traversed}.{token}"
        traversed = traversed.lstrip(".")
    result = current if isinstance(current, str) else json.dumps(current, indent=2)
    ctx.print(result)
    return result


@make_task(
    name="json-to-yaml",
    description="🔄 Convert JSON to YAML",
    input=StrInput(name="json", description="JSON text", prompt="JSON"),
    retries=0,
    group=json_group,
    alias="to-yaml",
)
def json_to_yaml(ctx: AnyContext) -> str:

    # lazy: heavy third-party
    import yaml

    result = yaml.safe_dump(_parse_json(ctx, ctx.input.json), sort_keys=False).rstrip(
        "\n"
    )
    ctx.print(result)
    return result


@make_task(
    name="yaml-to-json",
    description="🔄 Convert YAML to JSON",
    input=[
        StrInput(name="yaml", description="YAML text", prompt="YAML"),
        IntInput(
            name="indent",
            description="Indent size",
            prompt="Indent",
            default=2,
            always_prompt=False,
        ),
    ],
    retries=0,
    group=json_group,
    alias="from-yaml",
)
def yaml_to_json(ctx: AnyContext) -> str:

    # lazy: heavy third-party
    import yaml

    try:
        data = yaml.safe_load(ctx.input.yaml)
    except yaml.YAMLError as e:
        message = f"Invalid YAML: {e}"
        ctx.print_err(f"❌ {message}")
        raise ValueError(message) from None
    result = json.dumps(data, indent=ctx.input.indent, ensure_ascii=False)
    ctx.print(result)
    return result
