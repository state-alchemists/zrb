import base64
import binascii

from zrb.builtin.group import base64_group
from zrb.context.any_context import AnyContext
from zrb.input.bool_input import BoolInput
from zrb.input.str_input import StrInput
from zrb.task.make_task import make_task


@make_task(
    name="encode-base64",
    input=[
        StrInput(name="text", description="Text", prompt="Text to encode"),
        BoolInput(
            name="url-safe",
            description="Use URL/filename-safe alphabet (-_ instead of +/)",
            default=False,
            always_prompt=False,
        ),
    ],
    description="🔐 Encode text to base64",
    group=base64_group,
    alias="encode",
)
def encode_base64(ctx: AnyContext) -> str:

    raw = ctx.input.text.encode()
    if ctx.input.url_safe:
        result = base64.urlsafe_b64encode(raw).decode()
    else:
        result = base64.b64encode(raw).decode()
    ctx.print(result)
    return result


@make_task(
    name="decode-base64",
    input=[
        StrInput(name="text", description="Text", prompt="Text to decode"),
        BoolInput(
            name="url-safe",
            description="Use URL/filename-safe alphabet (-_ instead of +/)",
            default=False,
            always_prompt=False,
        ),
    ],
    description="🔓 Decode base64 text",
    retries=0,
    group=base64_group,
    alias="decode",
)
def decode_base64(ctx: AnyContext) -> str:

    raw = ctx.input.text.encode()
    try:
        if ctx.input.url_safe:
            decoded = base64.urlsafe_b64decode(raw)
        else:
            decoded = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        message = (
            f"Invalid base64 input '{ctx.input.text}'. "
            f"If it uses the URL-safe alphabet (-_), pass --url-safe."
        )
        ctx.print_err(f"❌ {message}")
        raise ValueError(message) from None
    try:
        result = decoded.decode()
    except UnicodeDecodeError:
        message = "Decoded bytes are not valid UTF-8 text (the data is binary)."
        ctx.print_err(f"❌ {message}")
        raise ValueError(message) from None
    ctx.print(result)
    return result


@make_task(
    name="validate-base64",
    input=[
        StrInput(
            name="text",
            description="Text to validate",
            prompt="Enter text to validate as base64",
        ),
        BoolInput(
            name="url-safe",
            description="Use URL/filename-safe alphabet (-_ instead of +/)",
            default=False,
            always_prompt=False,
        ),
    ],
    description="✅ Validate base64 text",
    group=base64_group,
    alias="validate",
)
def validate_base64(ctx: AnyContext) -> bool:

    raw = ctx.input.text.encode()
    # Normalize the URL-safe alphabet to the standard one so `validate=True`
    # can strictly reject non-alphabet characters either way.
    if ctx.input.url_safe:
        raw = raw.translate(bytes.maketrans(b"-_", b"+/"))
    try:
        # `validate=True` rejects non-alphabet characters. We check that the
        # input is well-formed base64 — NOT that it decodes to UTF-8 text, so
        # base64 of binary data (images, gzipped blobs) validates correctly.
        base64.b64decode(raw, validate=True)
        ctx.print("Valid base64")
        return True
    except (binascii.Error, ValueError):
        ctx.print("Invalid base64")
        return False
