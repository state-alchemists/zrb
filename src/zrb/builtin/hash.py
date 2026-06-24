import hashlib
import hmac

from zrb.builtin.group import hash_group
from zrb.context.any_context import AnyContext
from zrb.input.option_input import OptionInput
from zrb.input.str_input import StrInput
from zrb.task.make_task import make_task

_ALGORITHMS = ["sha256", "sha1", "sha224", "sha384", "sha512", "md5"]


@make_task(
    name="hash-text",
    description="🧩 Hash text (sha256 by default)",
    input=[
        StrInput(name="text", description="Text", prompt="Text to hash"),
        OptionInput(
            name="algorithm",
            description="Hash algorithm",
            prompt="Algorithm",
            default="sha256",
            options=_ALGORITHMS,
            always_prompt=False,
        ),
    ],
    group=hash_group,
    alias="hash",
)
def hash_text(ctx: AnyContext) -> str:

    result = hashlib.new(ctx.input.algorithm, ctx.input.text.encode()).hexdigest()
    ctx.print(result)
    return result


@make_task(
    name="hash-file",
    description="➕ Get hash checksum of a file (sha256 by default)",
    input=[
        StrInput(name="file", description="File name", prompt="File name"),
        OptionInput(
            name="algorithm",
            description="Hash algorithm",
            prompt="Algorithm",
            default="sha256",
            options=_ALGORITHMS,
            always_prompt=False,
        ),
    ],
    retries=0,
    group=hash_group,
    alias="sum",
)
def hash_file(ctx: AnyContext) -> str:

    digest = hashlib.new(ctx.input.algorithm)
    try:
        with open(ctx.input.file, mode="rb") as file:
            for chunk in iter(lambda: file.read(8192), b""):
                digest.update(chunk)
    except FileNotFoundError:
        message = f"File not found: '{ctx.input.file}'."
        ctx.print_err(f"❌ {message}")
        raise ValueError(message) from None
    except OSError as e:
        message = f"Cannot read file '{ctx.input.file}': {e.strerror or e}."
        ctx.print_err(f"❌ {message}")
        raise ValueError(message) from None
    result = digest.hexdigest()
    ctx.print(result)
    return result


@make_task(
    name="hash-hmac",
    description="🔑 Compute an HMAC of text with a secret key",
    input=[
        StrInput(name="key", description="Secret key", prompt="Secret key"),
        StrInput(name="text", description="Text", prompt="Text to authenticate"),
        OptionInput(
            name="algorithm",
            description="Hash algorithm",
            prompt="Algorithm",
            default="sha256",
            options=_ALGORITHMS,
            always_prompt=False,
        ),
    ],
    group=hash_group,
    alias="hmac",
)
def hash_hmac(ctx: AnyContext) -> str:

    result = hmac.new(
        ctx.input.key.encode(),
        ctx.input.text.encode(),
        ctx.input.algorithm,
    ).hexdigest()
    ctx.print(result)
    return result
