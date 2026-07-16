import asyncio
import json
import os
from typing import TYPE_CHECKING

from zrb.llm.tool_call.argument_formatter.util import format_diff
from zrb.llm.tool_call.ui_protocol import UIProtocol
from zrb.util.cli.markdown import render_markdown
from zrb.util.cli.terminal import get_terminal_size

if TYPE_CHECKING:
    from pydantic_ai import ToolCallPart


async def replace_in_file_formatter(
    ui: UIProtocol,
    call: "ToolCallPart",
    args_section: str,
) -> str | None:
    """
    Shows a git diff like UI for replace_in_file tool call.
    """
    if call.tool_name != "Edit":
        return None

    try:
        args = call.args
        if isinstance(args, str):
            args = json.loads(args)
        if not isinstance(args, dict):
            return None

        path = args.get("path")
        old_text = args.get("old_text")
        new_text = args.get("new_text")
        count = args.get("count", -1)

        if not path or old_text is None or new_text is None:
            return None

        # Offload: file read + difflib + Rich markdown render is pure blocking
        # CPU/IO. On the TUI it runs on prompt_toolkit's event loop before the
        # approval prompt appears, so leaving it inline freezes keystrokes.
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

    diff_md = format_diff(content, new_content, path, ui=ui)
    if not diff_md:
        return None

    indent = " " * 7
    # Render at the real terminal width. width=None makes Rich fall back to 80
    # when stdout is a capture pipe (see get_terminal_size note), which re-wraps
    # the already-wide diff lines from util.py.
    formatted_diff = render_markdown(diff_md, width=get_terminal_size().columns)
    formatted_diff = "\n".join(
        [f"{indent}{line}" for line in formatted_diff.splitlines()]
    )

    return f"       📄 File: {path}\n{formatted_diff}\n"
