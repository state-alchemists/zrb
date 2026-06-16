import json
from urllib.parse import parse_qs, quote, unquote, urlparse

from zrb.builtin.group import url_group
from zrb.context.any_context import AnyContext
from zrb.input.str_input import StrInput
from zrb.task.make_task import make_task


@make_task(
    name="encode-url",
    description="🔐 Percent-encode text for safe use in a URL",
    input=StrInput(name="text", description="Text", prompt="Text to encode"),
    group=url_group,
    alias="encode",
)
def encode_url(ctx: AnyContext) -> str:

    result = quote(ctx.input.text, safe="")
    ctx.print(result)
    return result


@make_task(
    name="decode-url",
    description="🔓 Decode percent-encoded URL text",
    input=StrInput(name="text", description="Text", prompt="Text to decode"),
    group=url_group,
    alias="decode",
)
def decode_url(ctx: AnyContext) -> str:

    result = unquote(ctx.input.text)
    ctx.print(result)
    return result


@make_task(
    name="parse-url",
    description="🔎 Parse a URL into its components (as JSON)",
    input=StrInput(name="url", description="URL", prompt="URL to parse"),
    retries=0,
    group=url_group,
    alias="parse",
)
def parse_url(ctx: AnyContext) -> str:

    parts = urlparse(ctx.input.url)
    try:
        port = parts.port
    except ValueError:
        message = (
            f"Invalid URL '{ctx.input.url}': the port is not a number. "
            f"Expected something like 'https://host:8443/path'."
        )
        ctx.print_err(f"❌ {message}")
        raise ValueError(message) from None
    # parse_qs returns list values; flatten single-value params for readability.
    raw_query = parse_qs(parts.query)
    query = {k: v[0] if len(v) == 1 else v for k, v in raw_query.items()}
    parsed = {
        "scheme": parts.scheme,
        "username": parts.username,
        "password": parts.password,
        "hostname": parts.hostname,
        "port": port,
        "path": parts.path,
        "query": query,
        "fragment": parts.fragment,
    }
    result = json.dumps(parsed, indent=2)
    ctx.print(result)
    return result
