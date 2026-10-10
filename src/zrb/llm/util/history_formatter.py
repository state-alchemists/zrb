"""Utility for formatting pydantic-ai conversation history into human-readable text."""

import json
from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.tool_call.args import parse_tool_args_value
from zrb.llm.util.tool_args import is_empty_tool_args, truncate_tool_args_values
from zrb.util.truncate import truncate_display

if TYPE_CHECKING:
    from zrb.llm.agent.types import ModelMessage


def extract_last_response_text(messages: "Sequence[ModelMessage]") -> str:
    """Return the text of the most recent assistant response with any text,
    or ``""``. Recovers the last response for export after a session load."""
    for msg in reversed(messages):
        if getattr(msg, "kind", None) != "response":
            continue
        parts = getattr(msg, "parts", [])
        texts = [
            str(getattr(p, "content", ""))
            for p in parts
            if getattr(p, "part_kind", None) == "text"
        ]
        text = "\n".join(t for t in texts if t)
        if text.strip():
            return text
    return ""


def extract_user_message_texts(messages: "Sequence[ModelMessage]") -> list[str]:
    """Return the user-prompt texts of *messages*, newest first.

    Feeds Up-arrow recall for a loaded conversation; only ``user-prompt``
    parts count.
    """
    texts: list[str] = []
    for msg in messages:
        if getattr(msg, "kind", None) != "request":
            continue
        for part in getattr(msg, "parts", []) or []:
            if getattr(part, "part_kind", None) != "user-prompt":
                continue
            content = getattr(part, "content", "") or ""
            content = _strip_live_context(content)
            text = _render_user_content(content, full=True)
            if text.strip():
                texts.append(text)
    texts.reverse()
    return texts


def _strip_live_context(content):
    """Strip a trailing ``<live-context>`` block off a user-prompt content value.

    History persists the block inline (a string suffix, or a trailing string
    item of a multimodal prompt); recall must not show it as typed text.
    """
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.prompt.live_context import split_live_context

    if isinstance(content, str):
        return split_live_context(content)[0]
    if isinstance(content, Sequence):
        items = list(content)
        if items and isinstance(items[-1], str):
            message, live_context = split_live_context(items[-1])
            if live_context is not None:
                if message.strip():
                    items[-1] = message
                else:
                    items.pop()
        return items
    return content


def format_history_as_text(
    messages: "Sequence[ModelMessage]",
    max_length: int | None = None,
    *,
    full: bool = False,
) -> str:
    """Format pydantic-ai conversation history as human-readable text.

    Mimics the streaming style:
    - User messages: 💬 {time} >> {content}
    - Assistant text: 🤖 {time} >> {content}
    - Tool calls: 🧰 {tool_call_id} | {tool_name} {args}
    - Tool returns: 🔠 {tool_call_id} | Return {content}

    Args:
        messages: List of ModelMessage (ModelRequest or ModelResponse)
        max_length: Maximum length of output text (truncated if exceeded).
                    Defaults to CFG.LLM_HISTORY_MAX_DISPLAY_CHARS. Ignored
                    when ``full`` is True.
        full: When True, apply no truncation at all (for export).
    """
    if max_length is None:
        max_length = CFG.LLM_HISTORY_MAX_DISPLAY_CHARS
    if not messages:
        return "📭 Empty conversation history."

    lines = []
    pending_tool_calls: dict[str, str] = {}

    for msg in messages:
        kind = getattr(msg, "kind", "unknown")

        if kind == "request":
            lines.extend(_format_request(msg, pending_tool_calls, full))
        elif kind == "response":
            lines.extend(_format_response(msg, pending_tool_calls, full))

    result = "\n".join(lines)
    if not full and len(result) > max_length:
        truncate_msg = (
            f"\n... (truncated, showing {max_length} of {len(result)} characters)"
        )
        result = result[:max_length] + truncate_msg

    return result


def _format_request(
    msg, pending_tool_calls: dict[str, str], full: bool = False
) -> list[str]:
    """Format a ModelRequest message; tool returns render first."""
    lines = []
    timestamp = format_timestamp(getattr(msg, "timestamp", None))

    user_prompt_parts = []
    tool_return_parts = []
    system_prompt_parts = []
    retry_parts = []

    parts = getattr(msg, "parts", [])
    for part in parts:
        part_kind = getattr(part, "part_kind", None)
        if part_kind == "user-prompt":
            user_prompt_parts.append(part)
        elif part_kind == "tool-return":
            tool_return_parts.append(part)
        elif part_kind == "system-prompt":
            system_prompt_parts.append(part)
        elif part_kind == "retry-prompt":
            retry_parts.append(part)

    for part in tool_return_parts:
        lines.extend(_format_tool_return(part, pending_tool_calls, full))

    for part in user_prompt_parts:
        content = getattr(part, "content", "")
        ts_display = f"{timestamp} " if timestamp else ""
        text = _render_user_content(content, full)
        lines.append(f"💬 {ts_display}>> {text}")

    indent_max = None if full else 50

    for part in system_prompt_parts:
        content = getattr(part, "content", "")
        dynamic_ref = getattr(part, "dynamic_ref", None)
        lines.append("📋 System Prompt:")
        if dynamic_ref:
            lines.append(f"  Ref: {dynamic_ref}")
        lines.extend(indent_lines(str(content), 2, max_lines=indent_max))

    for part in retry_parts:
        content = getattr(part, "content", "")
        tool_name = getattr(part, "tool_name", None)
        lines.append("🔄 Retry Prompt:")
        if tool_name:
            lines.append(f"  Tool: {tool_name}")
        lines.extend(indent_lines(str(content), 2, max_lines=indent_max))

    return lines


def _render_user_content(content, full: bool = False) -> str:
    """Render a UserPromptPart's content, which may be plain text or a
    multimodal sequence (text interleaved with image/audio/video/document
    attachments)."""
    if isinstance(content, str):
        return content if full else truncate(content, 500)
    if isinstance(content, Sequence):
        rendered = " ".join(format_multimodal_item(item) for item in content)
        return rendered if full else truncate(rendered, 500)
    return str(content) if full else truncate(str(content), 500)


def format_multimodal_item(item) -> str:
    """Render one item of a multimodal ``UserPromptPart.content`` sequence.

    Shared with ``llm/summarizer/message_converter.py``.
    """
    if isinstance(item, str):
        return item
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import (
        AudioUrl,
        BinaryContent,
        DocumentUrl,
        ImageUrl,
        VideoUrl,
    )

    if isinstance(item, ImageUrl):
        return f"[Image URL: {item.url}]"
    if isinstance(item, AudioUrl):
        return f"[Audio URL: {item.url}]"
    if isinstance(item, VideoUrl):
        return f"[Video URL: {item.url}]"
    if isinstance(item, DocumentUrl):
        return f"[Document URL: {item.url}]"
    if isinstance(item, BinaryContent):
        media_type = getattr(item, "media_type", "unknown")
        return f"[Binary Content: {media_type}]"
    return f"[Unknown User Content: {type(item).__name__}]"


def _format_response(
    msg, pending_tool_calls: dict[str, str], full: bool = False
) -> list[str]:
    """Format a ModelResponse: thinking, then text, then tool calls."""
    lines = []
    timestamp = format_timestamp(getattr(msg, "timestamp", None))
    model_name = getattr(msg, "model_name", None)

    ts_display = f"{timestamp} " if timestamp else ""
    lines.append(f"🤖 {ts_display}>>")

    parts = getattr(msg, "parts", [])

    thinking_parts = [p for p in parts if getattr(p, "part_kind", None) == "thinking"]
    for part in thinking_parts:
        content = getattr(part, "content", "")
        lines.append("  💭 Thinking:")
        lines.extend(indent_lines(str(content), 4, max_lines=None if full else 10))

    text_parts = [p for p in parts if getattr(p, "part_kind", None) == "text"]
    for part in text_parts:
        content = getattr(part, "content", "")
        lines.extend(indent_lines(str(content), 2, max_lines=None if full else 50))

    tool_call_parts = [p for p in parts if getattr(p, "part_kind", None) == "tool-call"]
    for part in tool_call_parts:
        lines.extend(_format_tool_call(part, pending_tool_calls, full))

    if model_name:
        lines.append(f"  🎯 Model: {model_name}")

    return lines


def _format_tool_call(
    part, pending_tool_calls: dict[str, str], full: bool = False
) -> list[str]:
    """Format a ToolCallPart as ``🧰 {tool_call_id} | {tool_name} {args}``."""
    lines = []
    tool_name = getattr(part, "tool_name", None)
    tool_call_id = getattr(part, "tool_call_id", None)
    args = getattr(part, "args", None)

    if tool_call_id and tool_name:
        pending_tool_calls[tool_call_id] = tool_name

    args_str = format_args(args, full=full)
    id_display = tool_call_id or "?"
    name_display = tool_name or "unknown"

    lines.append(f"  🧰 {id_display} | {name_display} {args_str}")
    return lines


def _format_tool_return(
    part, pending_tool_calls: dict[str, str], full: bool = False
) -> list[str]:
    """Format a ToolReturnPart as ``🔠 {tool_call_id} | {tool_name} {status}``."""
    lines = []
    tool_name = getattr(part, "tool_name", None)
    tool_call_id = getattr(part, "tool_call_id", None)
    content = getattr(part, "content", "")
    outcome = getattr(part, "outcome", "success")

    status_icon = "✅" if str(outcome) == "success" else "❌"

    id_display = tool_call_id or "?"

    if tool_name:
        name_display = tool_name
    elif tool_call_id and tool_call_id in pending_tool_calls:
        name_display = pending_tool_calls[tool_call_id]
    else:
        name_display = "unknown"

    content_str = str(content) if content else ""
    shown = content_str if full else truncate(content_str, 200)

    lines.append(f"  🔠 {id_display} | {name_display} {status_icon}")
    if shown.strip():
        lines.extend(indent_lines(shown, 4, max_lines=None if full else 3))

    return lines


def indent_lines(text: str, indent: int = 2, max_lines: int | None = 50) -> list[str]:
    """Indent each line of *text*, keeping at most *max_lines* (None: all)."""
    indent_str = " " * indent
    lines = []
    text_lines = text.split("\n")

    limit = len(text_lines) if max_lines is None else max_lines
    for line in text_lines[:limit]:
        lines.append(f"{indent_str}{line}")

    if max_lines is not None and len(text_lines) > max_lines:
        remaining = len(text_lines) - max_lines
        lines.append(f"{indent_str}... ({remaining} more lines)")

    return lines


def truncate(text: str, max_length: int | None = None) -> str:
    """Truncate text to max_length with ellipsis."""
    if max_length is None:
        max_length = CFG.LLM_HISTORY_TRUNCATE_LENGTH
    return truncate_display(text, max_length)


def format_args(args, full: bool = False) -> str:
    """Format tool call arguments for display; ``full`` skips truncation."""
    if is_empty_tool_args(args):
        return "{}"
    if isinstance(args, dict):
        # Remove 'dummy' key if present (schema sanitization artifact)
        args_clean = {k: v for k, v in args.items() if k != "dummy"}
        return _dump_truncated(args_clean, full=full)
    if isinstance(args, str):
        parsed = parse_tool_args_value(args)
        if parsed is not None:
            return _dump_truncated(parsed, full=full)
        return args if full else truncate(args, 50)
    return str(args) if full else truncate(str(args), 50)


def _dump_truncated(kwargs: dict, full: bool = False) -> str:
    """Truncate keyword arguments and render as JSON (no truncation when ``full``)."""
    truncated = truncate_tool_args_values(kwargs, full=full)
    try:
        return json.dumps(truncated, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(truncated)


def format_timestamp(timestamp) -> str:
    """Format a datetime or ISO string as ``HH:MM``, or ``""``."""
    if timestamp is None:
        return ""

    try:
        if isinstance(timestamp, str):
            if timestamp.endswith("Z"):
                timestamp = timestamp[:-1] + "+00:00"
            dt = datetime.fromisoformat(timestamp)
        elif isinstance(timestamp, datetime):
            dt = timestamp
        else:
            return ""

        return dt.strftime("%H:%M")
    except (ValueError, TypeError):
        return ""
