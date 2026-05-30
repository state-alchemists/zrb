import hashlib
import re

from zrb.builtin.group import md5_group
from zrb.context.any_context import AnyContext
from zrb.input.str_input import StrInput
from zrb.task.make_task import make_task


@make_task(
    name="hash-md5",
    input=StrInput(name="text", description="Text", prompt="Text to encode"),
    description="🧩 Hash text to md5",
    group=md5_group,
    alias="hash",
)
def hash_md5(ctx: AnyContext) -> str:

    result = hashlib.md5(ctx.input.text.encode()).hexdigest()
    ctx.print(result)
    return result


@make_task(
    name="sum-md5",
    input=StrInput(name="file", description="File name", prompt="File name"),
    description="➕ Get md5 checksum of a file",
    group=md5_group,
    alias="sum",
)
def sum_md5(ctx: AnyContext) -> str:

    with open(ctx.input.file, mode="rb") as file:
        content = file.read()
    result = hashlib.md5(content).hexdigest()
    ctx.print(result)
    return result


@make_task(
    name="validate-md5",
    input=StrInput(
        name="hash",
        description="Hash to validate",
        prompt="Enter hash to validate as MD5",
    ),
    description="✅ Validate MD5 hash",
    group=md5_group,
    alias="validate",
)
def validate_md5(ctx: AnyContext) -> bool:

    pattern = r"^[a-f0-9]{32}$"
    is_valid = bool(re.fullmatch(pattern, ctx.input.hash))
    if is_valid:
        ctx.print("Valid MD5 hash")
    else:
        ctx.print("Invalid MD5 hash")
    return is_valid
