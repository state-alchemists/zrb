from zrb.builtin.group import base64_group
from zrb.context.any_context import AnyContext
from zrb.input.str_input import StrInput
from zrb.task.make_task import make_task


@make_task(
    name="encode-base64",
    input=StrInput(name="text", description="Text", prompt="Text to encode"),
    description="🔐 Encode text to base64",
    group=base64_group,
    alias="encode",
)
def encode_base64(ctx: AnyContext) -> str:
    import base64

    result = base64.b64encode(ctx.input.text.encode()).decode()
    ctx.print(result)
    return result


@make_task(
    name="decode-base64",
    input=StrInput(name="text", description="Text", prompt="Text to encode"),
    description="🔓 Decode base64 text",
    group=base64_group,
    alias="decode",
)
def decode_base64(ctx: AnyContext) -> str:
    import base64

    result = base64.b64decode(ctx.input.text.encode()).decode()
    ctx.print(result)
    return result


@make_task(
    name="validate-base64",
    input=StrInput(
        name="text",
        description="Text to validate",
        prompt="Enter text to validate as base64",
    ),
    description="✅ Validate base64 text",
    group=base64_group,
    alias="validate",
)
def validate_base64(ctx: AnyContext) -> bool:
    import base64
    import binascii

    try:
        base64.b64decode(ctx.input.text.encode()).decode()
        ctx.print("Valid base64")
        return True
    except (binascii.Error, UnicodeDecodeError):
        ctx.print("Invalid base64")
        return False
