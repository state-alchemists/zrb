import asyncio
import os
from typing import TYPE_CHECKING

from zrb.llm.tool_call.args import parse_tool_args
from zrb.llm.tool_call.argument_formatter.util import (
    format_diff,
    render_indented_diff,
)

if TYPE_CHECKING:
    from zrb.llm.agent.types import ToolCallPart
    from zrb.llm.ui.any_agent_output import AnyAgentOutput


async def replace_in_file_formatter(
    ui: "AnyAgentOutput",
    call: "ToolCallPart",
    args_section: str,
) -> str | None:
    """Show a git-style diff for an `Edit` tool call."""
    if call.tool_name != "Edit":
        return None

    try:
        args = parse_tool_args(call)
        if args is None:
            return None

        path = args.get("path")
        old_text = args.get("old_text")
        new_text = args.get("new_text")
        count = args.get("count", -1)

        if not path or old_text is None or new_text is None:
            return None

        # Blocking IO/CPU; inline it would freeze the TUI event loop.
        return await asyncio.to_thread(
            _format_replace, path, old_text, new_text, count, ui
        )

    except Exception:
        return None


def _format_replace(path, old_text, new_text, count, ui) -> str | None:
    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        return None

    with open(abs_path, "r", encoding="utf-8") as f:
        content = f.read()

    if old_text not in content:
        return None

    new_content = content.replace(old_text, new_text, count)
    if content == new_content:
        return None

    diff_md = format_diff(content, new_content, path)
    if not diff_md:
        return None

    formatted_diff = render_indented_diff(diff_md)

    return f"       📄 File: {path}\n{formatted_diff}\n"
