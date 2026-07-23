import asyncio
import json
import os
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.tool_call.argument_formatter.util import format_diff
from zrb.llm.tool_call.ui_protocol import UIProtocol
from zrb.util.cli.markdown import render_markdown
from zrb.util.cli.terminal import get_terminal_size

if TYPE_CHECKING:
    from pydantic_ai import ToolCallPart


async def write_file_formatter(
    ui: UIProtocol,
    call: "ToolCallPart",
    args_section: str,
) -> str | None:
    """
    Shows a diff or content for write_file tool call.
    """
    if call.tool_name != "Write":
        return None

    try:
        args = call.args
        if isinstance(args, str):
            args = json.loads(args)
        if not isinstance(args, dict):
            return None

        path = args.get("path")
        content = args.get("content")
        mode = args.get("mode", "w")

        if not path or content is None:
            return None

        # Offload: file read + difflib + Rich markdown render is pure blocking
        # CPU/IO. On the TUI it runs on prompt_toolkit's event loop before the
        # approval prompt appears, so leaving it inline freezes keystrokes.
        return await asyncio.to_thread(_format_single_write, path, content, mode, ui)

    except Exception:
        return None


def _format_single_write(path: str, new_content: str, mode: str, ui) -> str | None:
    abs_path = os.path.abspath(os.path.expanduser(path))
    old_content = ""
    file_exists = os.path.exists(abs_path)

    if file_exists:
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                old_content = f.read()
        except Exception as e:
            CFG.LOGGER.debug(f"Failed to read existing content of {abs_path}: {e}")

    final_new_content = new_content
    if mode == "a":
        final_new_content = old_content + new_content

    diff_md = format_diff(old_content, final_new_content, path, ui=ui)
    if not diff_md:
        return f"       📄 File: {path} (No changes)\n"

    indent = " " * 7
    # Render at the real terminal width. width=None makes Rich fall back to 80
    # when stdout is a capture pipe (see get_terminal_size note), which re-wraps
    # the already-wide diff lines from util.py.
    formatted_diff = render_markdown(diff_md, width=get_terminal_size().columns)
    formatted_diff = "\n".join(
        [f"{indent}{line}" for line in formatted_diff.splitlines()]
    )

    if mode == "a":
        return f"       📝 Appending to: {path}\n{formatted_diff}\n"
    elif file_exists:
        return f"       📄 Overwriting: {path}\n{formatted_diff}\n"
    else:
        return f"       🆕 New File: {path}\n{formatted_diff}\n"
