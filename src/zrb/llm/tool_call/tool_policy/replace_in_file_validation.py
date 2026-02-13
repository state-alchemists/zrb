import json
import os
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from zrb.llm.tool_call.handler import ToolPolicy, UIProtocol

if TYPE_CHECKING:
    from pydantic_ai import ToolCallPart


async def replace_in_file_validation_policy(
    ui: UIProtocol,
    call: "ToolCallPart",
    next_handler: Callable[[UIProtocol, "ToolCallPart"], Awaitable[Any]],
) -> Any:
    """
    Validates 'Edit' (replace_in_file) tool calls.
    Auto-rejects if:
    1. old_text and new_text are identical.
    2. File does not exist.
    3. old_text is not found in the file.
    """
    from pydantic_ai import ToolDenied

    if call.tool_name != "Edit":
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
    old_text = args.get("old_text")
    new_text = args.get("new_text")

    if path is None or old_text is None or new_text is None:
        return await next_handler(ui, call)

    # 1. Check if identical
    if old_text == new_text:
        return ToolDenied("Old text and new text are identical.")

    abs_path = os.path.abspath(os.path.expanduser(path))

    # 2. Check if file exists
    if not os.path.exists(abs_path):
        return ToolDenied(f"File not found: {path}")

    # 3. Check if old_text is in file
    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()
        if old_text not in content:
            return ToolDenied(
                f"Old text not found in {path}. Please read the file first."
            )
    except Exception as e:
        return ToolDenied(f"Error reading file {path}: {e}")

    return await next_handler(ui, call)
