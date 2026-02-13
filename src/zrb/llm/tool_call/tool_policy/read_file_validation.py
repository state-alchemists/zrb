import json
import os
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from zrb.llm.tool_call.handler import ToolPolicy, UIProtocol

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
    from pydantic_ai import ToolDenied

    if call.tool_name != "Read":
        return await next_handler(ui, call)

    # Parse arguments
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
            return ToolDenied(f"File not found: {path}")

    return await next_handler(ui, call)
