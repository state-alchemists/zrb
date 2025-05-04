from typing import Any

from zrb.builtin.group import http_group
from zrb.context.any_context import AnyContext
from zrb.input.option_input import OptionInput
from zrb.input.str_input import StrInput
from zrb.task.make_task import make_task


@make_task(
    name="http-request",
    description="🌐 Send HTTP request (Postman-like)",
    group=http_group,
    alias="request",
    input=[
        OptionInput(
            name="method",
            default="GET",
            options=["GET", "POST", "PUT", "DELETE", "PATCH"],
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
            description="Request body (JSON)",
            prompt="Enter body as JSON",
            default="{}",
        ),
        OptionInput(
            name="verify_ssl",
            default="true",
            options=["true", "false"],
            description="Verify SSL certificate",
        ),
    ],
)
def http_request(ctx: AnyContext) -> Any:
    import json

    import requests

    try:
        # Prepare headers
        headers = json.loads(ctx.input.headers)

        # Prepare body
        body = None
        if ctx.input.body != "{}":
            body = json.loads(ctx.input.body)

        # Make request
        verify = ctx.input.verify_ssl.lower() == "true"
        response = requests.request(
            method=ctx.input.method,
            url=ctx.input.url,
            headers=headers,
            json=body,
            verify=verify,
        )

        # Print request/response details
        ctx.print("🌐 Request:")
        ctx.print(f"  Method: {ctx.input.method}")
        ctx.print(f"  URL: {ctx.input.url}")
        ctx.print(f"  Headers: {headers}")
        ctx.print(f"  Body: {body}")
        ctx.print(f"  Verify SSL: {verify}")
        ctx.print("📥 Response:")
        ctx.print(f"  Status: {response.status_code}")
        ctx.print(f"  Headers: {dict(response.headers)}")
        ctx.print(f"  Body: {response.text}")

        return response
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
            options=["GET", "POST", "PUT", "DELETE", "PATCH"],
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
            description="Request body (JSON)",
            prompt="Enter body as JSON",
            default="{}",
        ),
        OptionInput(
            name="verify_ssl",
            default="true",
            options=["true", "false"],
            description="Verify SSL certificate",
        ),
    ],
)
def generate_curl(ctx: AnyContext) -> str:
    import json
    import shlex

    try:
        # Prepare curl command parts
        parts = ["curl"]

        # Add method
        parts.extend(["-X", ctx.input.method])

        # Add headers
        if ctx.input.headers != "{}":
            headers = json.loads(ctx.input.headers)
            for key, value in headers.items():
                parts.extend(["-H", f"{key}: {value}"])

        # Add body
        if ctx.input.body != "{}":
            parts.extend(["--data-raw", shlex.quote(ctx.input.body)])

        # Add SSL verification
        if ctx.input.verify_ssl.lower() == "false":
            parts.append("--insecure")

        # Add URL
        parts.append(shlex.quote(ctx.input.url))

        # Join parts into command string
        curl_command = " ".join(parts)
        ctx.print(f"🔄 Curl command: {curl_command}")
        return curl_command
    except Exception as e:
        ctx.print_err(f"Failed to generate curl command: {e}")
        raise
