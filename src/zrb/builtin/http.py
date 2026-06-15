import json
import shlex
from typing import Any

from zrb.builtin.group import http_group
from zrb.context.any_context import AnyContext
from zrb.input.bool_input import BoolInput
from zrb.input.int_input import IntInput
from zrb.input.option_input import OptionInput
from zrb.input.str_input import StrInput
from zrb.task.make_task import make_task

_request_inputs = [
    OptionInput(
        name="method",
        default="GET",
        options=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
        prompt="HTTP method",
    ),
    StrInput(name="url", description="Target URL", prompt="Enter request URL"),
    StrInput(
        name="params",
        description="Query parameters (JSON)",
        prompt="Enter query params as JSON",
        default="{}",
    ),
    StrInput(
        name="headers",
        description="Request headers (JSON)",
        prompt="Enter headers as JSON",
        default="{}",
    ),
    OptionInput(
        name="body-format",
        description="How to encode the body: json, form, or raw",
        prompt="Body format",
        default="json",
        options=["json", "form", "raw"],
    ),
    StrInput(
        name="body",
        description="Request body (JSON for json/form, plain text for raw)",
        prompt="Enter body",
        default="",
    ),
    IntInput(
        name="timeout",
        description="Request timeout in seconds",
        prompt="Timeout (seconds)",
        default=30,
    ),
    BoolInput(
        name="verify-ssl",
        default=True,
        description="Verify SSL certificate",
    ),
]


@make_task(
    name="http-request",
    description="🌐 Send HTTP request (Postman-like)",
    group=http_group,
    alias="request",
    input=_request_inputs,
)
def http_request(ctx: AnyContext) -> str:

    # lazy: heavy third-party
    import requests

    try:
        params = json.loads(ctx.input.params)
        headers = json.loads(ctx.input.headers)
        kwargs: dict[str, Any] = {
            "method": ctx.input.method,
            "url": ctx.input.url,
            "params": params,
            "headers": headers,
            "verify": ctx.input.verify_ssl,
            "timeout": ctx.input.timeout,
        }
        # Encode the body according to the selected format.
        body = ctx.input.body
        if body != "":
            if ctx.input.body_format == "json":
                kwargs["json"] = json.loads(body)
            elif ctx.input.body_format == "form":
                kwargs["data"] = json.loads(body)
            else:
                kwargs["data"] = body
        response = requests.request(**kwargs)
        # Decorations go to stderr (ctx.print); only the body is returned so
        # `zrb http request ... | jq` receives a clean payload on stdout.
        ctx.print("🌐 Request:")
        ctx.print(f"  Method: {ctx.input.method}")
        ctx.print(f"  URL: {response.url}")
        ctx.print(f"  Headers: {headers}")
        ctx.print(f"  Body format: {ctx.input.body_format}")
        ctx.print(f"  Verify SSL: {ctx.input.verify_ssl}")
        ctx.print("📥 Response:")
        ctx.print(f"  Status: {response.status_code} {response.reason}")
        ctx.print(f"  Headers: {dict(response.headers)}")
        # The body goes to stdout; surface non-2xx statuses prominently on stderr
        # so failures aren't silent when the body is piped elsewhere.
        if response.status_code >= 400:
            ctx.print_err(
                f"⚠️ Server returned an error status: "
                f"{response.status_code} {response.reason}"
            )
        return response.text
    except Exception as e:
        ctx.print_err(f"HTTP request failed: {e}")
        raise


@make_task(
    name="generate-curl",
    description="🔄 Generate curl command",
    group=http_group,
    alias="curl",
    input=[
        OptionInput(
            name="method",
            default="GET",
            options=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
            prompt="HTTP method",
        ),
        StrInput(name="url", description="Target URL", prompt="Enter request URL"),
        StrInput(
            name="headers",
            description="Request headers (JSON)",
            prompt="Enter headers as JSON",
            default="{}",
        ),
        StrInput(
            name="body",
            description="Request body (raw)",
            prompt="Enter body",
            default="",
        ),
        BoolInput(
            name="verify-ssl",
            default=True,
            description="Verify SSL certificate",
        ),
    ],
)
def generate_curl(ctx: AnyContext) -> str:

    try:
        parts = ["curl", "-X", ctx.input.method]
        if ctx.input.headers != "{}":
            headers = json.loads(ctx.input.headers)
            for key, value in headers.items():
                parts.extend(["-H", shlex.quote(f"{key}: {value}")])
        if ctx.input.body != "":
            parts.extend(["--data-raw", shlex.quote(ctx.input.body)])
        if not ctx.input.verify_ssl:
            parts.append("--insecure")
        parts.append(shlex.quote(ctx.input.url))
        curl_command = " ".join(parts)
        ctx.print(f"🔄 Curl command: {curl_command}")
        return curl_command
    except Exception as e:
        ctx.print_err(f"Failed to generate curl command: {e}")
        raise
