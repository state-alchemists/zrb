from __future__ import annotations

import difflib
import json
import os
from typing import TYPE_CHECKING

from zrb.llm.tool_call.ui_protocol import UIProtocol
from zrb.util.cli.markdown import render_markdown

if TYPE_CHECKING:
    from pydantic_ai import ToolCallPart


async def write_file_formatter(
    ui: UIProtocol,
    call: ToolCallPart,
    args_section: str,
) -> str | None:
    """
    Shows a diff or content for write_file tool call.
    """
    if call.tool_name != "write_file":
        return None

    try:
        args = call.args
        if isinstance(args, str):
            args = json.loads(args)

        path = args.get("path")
        content = args.get("content")
        mode = args.get("mode", "w")

        if not path or content is None:
            return None

        return _format_single_write(path, content, mode)

    except Exception:
        return None


async def write_files_formatter(
    ui: UIProtocol,
    call: ToolCallPart,
    args_section: str,
) -> str | None:
    """
    Shows a diff or content for write_files tool call.
    """
    if call.tool_name != "write_files":
        return None

    try:
        args = call.args
        if isinstance(args, str):
            args = json.loads(args)

        files = args.get("files", [])
        if not files:
            return None

        results = []
        for file_info in files:
            path = file_info.get("path")
            content = file_info.get("content")
            mode = file_info.get("mode", "w")
            if not path or content is None:
                continue
            formatted = _format_single_write(path, content, mode)
            if formatted:
                results.append(formatted)

        if not results:
            return None

        return "\n".join(results)

    except Exception:
        return None


def _format_single_write(path: str, new_content: str, mode: str) -> str | None:
    abs_path = os.path.abspath(os.path.expanduser(path))
    old_content = ""
    file_exists = os.path.exists(abs_path)

    if file_exists:
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                old_content = f.read()
        except Exception:
            pass

    if mode == "a":
        # For append, we just show what is being appended
        indent = " " * 7
        width = _get_width(indent)
        # We might want to show it as a diff addition
        diff_str = "".join(
            difflib.unified_diff(
                [],
                new_content.splitlines(keepends=True),
                fromfile=path,
                tofile=path,
            )
        )
        # unified_diff adds header which we might want to clean up or keep
        # Let's just show it as a code block with 'diff' if it looks better
        formatted_content = render_markdown(f"```diff\n{diff_str}\n```", width=width)
        formatted_content = "\n".join(
            [f"{indent}{line}" for line in formatted_content.splitlines()]
        )
        return f"       📝 Appending to: {path}\n{formatted_content}\n"

    # For mode 'w'
    if file_exists:
        diff = difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=path,
            tofile=path,
        )
        diff_str = "".join(diff)
        if not diff_str:
            return f"       📄 File: {path} (No changes)\n"

        indent = " " * 7
        width = _get_width(indent)
        formatted_diff = render_markdown(f"```diff\n{diff_str}\n```", width=width)
        formatted_diff = "\n".join(
            [f"{indent}{line}" for line in formatted_diff.splitlines()]
        )
        return f"       📄 Overwriting: {path}\n{formatted_diff}\n"
    else:
        # New file
        indent = " " * 7
        width = _get_width(indent)
        # Show as additions in diff
        diff_str = "".join(
            difflib.unified_diff(
                [],
                new_content.splitlines(keepends=True),
                fromfile="/dev/null",
                tofile=path,
            )
        )
        formatted_diff = render_markdown(f"```diff\n{diff_str}\n```", width=width)
        formatted_diff = "\n".join(
            [f"{indent}{line}" for line in formatted_diff.splitlines()]
        )
        return f"       🆕 New File: {path}\n{formatted_diff}\n"


def _get_width(indent: str) -> int | None:
    try:
        return os.get_terminal_size().columns - len(indent) - 1
    except Exception:
        return None
