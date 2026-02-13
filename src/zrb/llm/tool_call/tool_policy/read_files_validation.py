import json
import os
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from zrb.llm.tool_call.handler import ToolPolicy, UIProtocol

if TYPE_CHECKING:
    from pydantic_ai import ToolCallPart


async def read_files_validation_policy(
    ui: UIProtocol,
    call: "ToolCallPart",
    next_handler: Callable[[UIProtocol, "ToolCallPart"], Awaitable[Any]],
) -> Any:
    """
    Validates 'ReadMany' (read_files) tool calls.
    Rejected if NONE of the files exist.
    """
    from pydantic_ai import ToolDenied

    if call.tool_name != "ReadMany":
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

    paths = args.get("paths")
    if isinstance(paths, list) and len(paths) > 0:
        existing_count = 0
        for path in paths:
            abs_path = os.path.abspath(os.path.expanduser(str(path)))
            if os.path.exists(abs_path):
                existing_count += 1

        if existing_count == 0:
            return ToolDenied(f"None of the files were found: {', '.join(paths)}")

    return await next_handler(ui, call)
