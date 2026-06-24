from zrb.builtin.group import hex_group
from zrb.context.any_context import AnyContext
from zrb.input.str_input import StrInput
from zrb.task.make_task import make_task


@make_task(
    name="encode-hex",
    description="🔐 Encode text to hexadecimal",
    input=StrInput(name="text", description="Text", prompt="Text to encode"),
    group=hex_group,
    alias="encode",
)
def encode_hex(ctx: AnyContext) -> str:

    result = ctx.input.text.encode().hex()
    ctx.print(result)
    return result


@make_task(
    name="decode-hex",
    description="🔓 Decode hexadecimal to text",
    input=StrInput(name="hex", description="Hex string", prompt="Hex to decode"),
    retries=0,
    group=hex_group,
    alias="decode",
)
def decode_hex(ctx: AnyContext) -> str:

    # Tolerate spaces and a leading 0x so pasted hex dumps work.
    cleaned = ctx.input.hex.replace(" ", "").removeprefix("0x")
    try:
        raw = bytes.fromhex(cleaned)
    except ValueError:
        message = (
            f"Invalid hex string '{ctx.input.hex}': expected an even number of "
            f"hex digits (0-9, a-f), e.g. '68656c6c6f'."
        )
        ctx.print_err(f"❌ {message}")
        raise ValueError(message) from None
    try:
        result = raw.decode()
    except UnicodeDecodeError:
        message = (
            "Decoded bytes are not valid UTF-8 text. Use `zrb hex dump` to inspect "
            "binary data instead."
        )
        ctx.print_err(f"❌ {message}")
        raise ValueError(message) from None
    ctx.print(result)
    return result


@make_task(
    name="dump-hex",
    description="🧱 Produce a hexdump (offset + hex + ASCII) of text",
    input=StrInput(name="text", description="Text", prompt="Text to dump"),
    group=hex_group,
    alias="dump",
)
def dump_hex(ctx: AnyContext) -> str:

    data = ctx.input.text.encode()
    lines = []
    for offset in range(0, len(data), 16):
        chunk = data[offset : offset + 16]
        hex_part = " ".join(f"{b:02x}" for b in chunk).ljust(47)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{offset:08x}  {hex_part}  {ascii_part}")
    result = "\n".join(lines)
    ctx.print(result)
    return result
