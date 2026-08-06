import json
import os
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from zrb.llm.tool_call.handler import UIProtocol

if TYPE_CHECKING:
    from pydantic_ai import ToolCallPart


async def read_file_validation_policy(
    ui: UIProtocol,
    call: "ToolCallPart",
    next_handler: Callable[[UIProtocol, "ToolCallPart"], Awaitable[Any]],
) -> Any:
    """
    Validates 'Read' (read_file) tool calls.
    Rejected if the file does not exist.
    """
    # lazy: heavy third-party
    from pydantic_ai import ToolDenied

    if call.tool_name != "Read":
        return await next_handler(ui, call)

    args = call.args
    try:
        if isinstance(args, str):
            args = json.loads(args)
    except (json.JSONDecodeError, ValueError):
        return await next_handler(ui, call)

    if not isinstance(args, dict):
        return await next_handler(ui, call)

    path = args.get("path")
    if path:
        abs_path = os.path.abspath(os.path.expanduser(str(path)))
        if not os.path.exists(abs_path):
            return ToolDenied(
                f"File not found: {path} (resolved to {abs_path}). "
                "[SYSTEM SUGGESTION]: a relative path resolves against the "
                "current directory, not the project root. Use List to see "
                "what is actually there before guessing another path."
            )

    return await next_handler(ui, call)
