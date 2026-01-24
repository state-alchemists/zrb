from __future__ import annotations

import difflib
import json
import os
from typing import TYPE_CHECKING, Any

from zrb.llm.tool_call.ui_protocol import UIProtocol
from zrb.util.cli.markdown import render_markdown

if TYPE_CHECKING:
    from pydantic_ai import ToolCallPart


async def replace_in_file_formatter(
    ui: UIProtocol,
    call: ToolCallPart,
    args_section: str,
) -> str | None:
    """
    Shows a git diff like UI for replace_in_file tool call.
    """
    if call.tool_name != "replace_in_file":
        return None

    try:
        args = call.args
        if isinstance(args, str):
            args = json.loads(args)

        path = args.get("path")
        old_text = args.get("old_text")
        new_text = args.get("new_text")
        count = args.get("count", -1)

        if not path or old_text is None or new_text is None:
            return None

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

        diff = difflib.unified_diff(
            content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=path,
            tofile=path,
        )

        diff_str = "".join(diff)
        indent = " " * 7
        width = None
        try:
            width = os.get_terminal_size().columns - len(indent) - 1
        except Exception:
            pass

        formatted_diff = render_markdown(f"```diff\n{diff_str}\n```", width=width)
        formatted_diff = "\n".join(
            [f"{indent}{line}" for line in formatted_diff.splitlines()]
        )

        return f"       📄 File: {path}\n" f"{formatted_diff}\n"

    except Exception:
        return None
