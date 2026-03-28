import json
import os
from typing import TYPE_CHECKING

from zrb.llm.tool_call.argument_formatter.util import format_diff
from zrb.llm.tool_call.ui_protocol import UIProtocol
from zrb.util.cli.markdown import render_markdown

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
    import logging
    import sys
    logger = logging.getLogger(__name__)

    print(f"[write_file_formatter] CALLED! tool_name='{call.tool_name}'", file=sys.stderr)

    logger.warning(f"[write_file_formatter] call.tool_name='{call.tool_name}'")
    if call.tool_name != "Write":
        logger.warning(f"[write_file_formatter] Tool name mismatch, returning None")
        return None

    try:
        args = call.args
        logger.warning(f"[write_file_formatter] args type: {type(args)}, args: {args}")
        if isinstance(args, str):
            args = json.loads(args)
            logger.warning(f"[write_file_formatter] Parsed JSON args: {args}")

        path = args.get("path")
        content = args.get("content")
        mode = args.get("mode", "w")

        logger.warning(f"[write_file_formatter] path={path}, content_len={len(content) if content else 0}, mode={mode}")

        if not path or content is None:
            logger.warning(f"[write_file_formatter] Missing path or content, returning None")
            return None

        result = _format_single_write(path, content, mode, ui)
        logger.warning(f"[write_file_formatter] Returning: {result[:200] if result else None}...")
        return result

    except Exception as e:
        import traceback
        logger.error(f"[write_file_formatter] Exception: {e}")
        traceback.print_exc()
        return None


async def write_files_formatter(
    ui: UIProtocol,
    call: "ToolCallPart",
    args_section: str,
) -> str | None:
    """
    Shows a diff or content for write_files tool call.
    """
    if call.tool_name != "WriteMany":
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
            formatted = _format_single_write(path, content, mode, ui)
            if formatted:
                results.append(formatted)

        if not results:
            return None

        return "\n".join(results)

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
        except Exception:
            pass

    final_new_content = new_content
    if mode == "a":
        final_new_content = old_content + new_content

    diff_md = format_diff(old_content, final_new_content, path, ui=ui)
    if not diff_md:
        return f"       📄 File: {path} (No changes)\n"

    indent = " " * 7
    # Use width=None to let Rich handle markdown rendering without interfering
    # with the already-wrapped diff formatting from util.py
    formatted_diff = render_markdown(diff_md, width=None)
    formatted_diff = "\n".join(
        [f"{indent}{line}" for line in formatted_diff.splitlines()]
    )

    if mode == "a":
        return f"       📝 Appending to: {path}\n{formatted_diff}\n"
    elif file_exists:
        return f"       📄 Overwriting: {path}\n{formatted_diff}\n"
    else:
        return f"       🆕 New File: {path}\n{formatted_diff}\n"
