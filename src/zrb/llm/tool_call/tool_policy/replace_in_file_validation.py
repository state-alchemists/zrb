import os
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from zrb.llm.tool_call.args import parse_tool_args
from zrb.util.string.fuzzy_match import find_fuzzy_match

if TYPE_CHECKING:
    from zrb.llm.agent.types import ToolCallPart
    from zrb.llm.ui.any_agent_output import AnyAgentOutput


async def replace_in_file_validation_policy(
    ui: "AnyAgentOutput",
    call: "ToolCallPart",
    next_handler: Callable[["AnyAgentOutput", "ToolCallPart"], Awaitable[Any]],
) -> Any:
    """Deny an `Edit` call that is a no-op, targets a missing file, or whose old_text is absent."""
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import ToolDenied

    if call.tool_name != "Edit":
        return await next_handler(ui, call)

    args = parse_tool_args(call)
    if args is None:
        return await next_handler(ui, call)

    path = args.get("path")
    old_text = args.get("old_text")
    new_text = args.get("new_text")

    if path is None or old_text is None or new_text is None:
        return await next_handler(ui, call)

    if old_text == new_text:
        return ToolDenied(
            "Old text and new text are identical. "
            "[SYSTEM SUGGESTION]: no edit is needed here — old_text and "
            "new_text must differ."
        )

    abs_path = os.path.abspath(os.path.expanduser(path))

    if not os.path.exists(abs_path):
        return ToolDenied(
            f"File not found: {path} (resolved to {abs_path}). "
            "[SYSTEM SUGGESTION]: a relative path resolves against the current "
            "directory, not the project root. Use List to confirm the path."
        )

    # Accept fuzzy matches too, as the Edit tool does.
    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()
        if old_text not in content and find_fuzzy_match(content, old_text) is None:
            return ToolDenied(
                f"Old text not found in {path}. Please read the file first. "
                "[SYSTEM SUGGESTION]: Read the file to get its exact current "
                "content, then retry with old_text copied from that content."
            )
    except Exception as e:
        return ToolDenied(f"Error reading file {path}: {e}")

    return await next_handler(ui, call)
