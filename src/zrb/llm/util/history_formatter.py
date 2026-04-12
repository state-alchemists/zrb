"""Utility for formatting pydantic-ai conversation history into human-readable text."""

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic_ai import ModelMessage


def format_history_as_text(
    messages: "list[ModelMessage]", max_length: int | None = None
) -> str:
    """Format pydantic-ai conversation history as human-readable text.

    This mimics the streaming style from ui.py:
    - User messages: 💬 {time} >> {content}
    - Assistant text: 🤖 {time} >> {content}
    - Tool calls: 🧰 {tool_call_id} | {tool_name} {args}
    - Tool returns: 🔠 {tool_call_id} | Return {content}

    Args:
        messages: List of ModelMessage (ModelRequest or ModelResponse)
        max_length: Maximum length of output text (truncated if exceeded).
                    Defaults to CFG.LLM_HISTORY_MAX_DISPLAY_CHARS.

    Returns:
        Human-readable string representation of the conversation
    """
    from zrb.config.config import CFG

    if max_length is None:
        max_length = CFG.LLM_HISTORY_MAX_DISPLAY_CHARS
    if not messages:
        return "📭 Empty conversation history."

    lines = []

    # Track tool call IDs to tool names for matching returns
    pending_tool_calls: dict[str, str] = {}

    for i, msg in enumerate(messages):
        kind = getattr(msg, "kind", "unknown")

        if kind == "request":
            lines.extend(_format_request(msg, i, pending_tool_calls))
        elif kind == "response":
            lines.extend(_format_response(msg, i, pending_tool_calls))

    result = "\n".join(lines)

    # Truncate if too long
    if len(result) > max_length:
        truncate_msg = (
            f"\n... (truncated, showing {max_length} of {len(result)} characters)"
        )
        result = result[:max_length] + truncate_msg

    return result


def _format_request(msg, index: int, pending_tool_calls: dict[str, str]) -> list[str]:
    """Format a ModelRequest message.

    ModelRequest can contain:
    - UserPromptPart: User's input text
    - ToolReturnPart: Results from tool executions
    - RetryPromptPart: Retry prompt on tool failure
    - SystemPromptPart: System instructions
    """
    lines = []
    timestamp = _format_timestamp(getattr(msg, "timestamp", None))

    # Collect parts by type
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

    # Show tool returns first (they're feedback from tool execution)
    for part in tool_return_parts:
        lines.extend(_format_tool_return(part, pending_tool_calls))

    # Show user prompt(s)
    for part in user_prompt_parts:
        content = getattr(part, "content", "")
        ts_display = f"{timestamp} " if timestamp else ""
        lines.append(f"💬 {ts_display}>> {_truncate(str(content), 500)}")

    # System prompts (rarely in history)
    for part in system_prompt_parts:
        content = getattr(part, "content", "")
        dynamic_ref = getattr(part, "dynamic_ref", None)
        lines.append("📋 System Prompt:")
        if dynamic_ref:
            lines.append(f"  Ref: {dynamic_ref}")
        lines.extend(_indent_lines(str(content), 2))

    # Retry prompts
    for part in retry_parts:
        content = getattr(part, "content", "")
        tool_name = getattr(part, "tool_name", None)
        lines.append("🔄 Retry Prompt:")
        if tool_name:
            lines.append(f"  Tool: {tool_name}")
        lines.extend(_indent_lines(str(content), 2))

    return lines


def _format_response(msg, index: int, pending_tool_calls: dict[str, str]) -> list[str]:
    """Format a ModelResponse message.

    ModelResponse can contain:
    - TextPart: Assistant's text response
    - ToolCallPart: Tool calls made by assistant
    - ThinkingPart: Internal reasoning
    """
    lines = []
    timestamp = _format_timestamp(getattr(msg, "timestamp", None))
    model_name = getattr(msg, "model_name", None)

    ts_display = f"{timestamp} " if timestamp else ""
    lines.append(f"🤖 {ts_display}>>")

    parts = getattr(msg, "parts", [])

    # First show thinking (if any)
    thinking_parts = [p for p in parts if getattr(p, "part_kind", None) == "thinking"]
    for part in thinking_parts:
        content = getattr(part, "content", "")
        lines.append("  💭 Thinking:")
        lines.extend(_indent_lines(str(content), 4, max_lines=10))

    # Then show text content
    text_parts = [p for p in parts if getattr(p, "part_kind", None) == "text"]
    for part in text_parts:
        content = getattr(part, "content", "")
        lines.extend(_indent_lines(str(content), 2))

    # Then show tool calls (mimicking streaming style with 🧰)
    tool_call_parts = [p for p in parts if getattr(p, "part_kind", None) == "tool-call"]
    for part in tool_call_parts:
        lines.extend(_format_tool_call(part, pending_tool_calls))

    if model_name:
        lines.append(f"  🎯 Model: {model_name}")

    return lines


def _format_tool_call(part, pending_tool_calls: dict[str, str]) -> list[str]:
    """Format a ToolCallPart.

    Mimics the streaming style:
    🧰 {tool_call_id} | {tool_name} {args}
    """
    lines = []
    tool_name = getattr(part, "tool_name", None)
    tool_call_id = getattr(part, "tool_call_id", None)
    args = getattr(part, "args", None)

    # Track for matching with return
    if tool_call_id and tool_name:
        pending_tool_calls[tool_call_id] = tool_name

    args_str = _format_args(args)
    id_display = tool_call_id or "?"
    name_display = tool_name or "unknown"

    lines.append(f"  🧰 {id_display} | {name_display} {args_str}")
    return lines


def _format_tool_return(part, pending_tool_calls: dict[str, str]) -> list[str]:
    """Format a ToolReturnPart.

    Mimics the streaming style:
    🔠 {tool_call_id} | Return {content}
    """
    lines = []
    tool_name = getattr(part, "tool_name", None)
    tool_call_id = getattr(part, "tool_call_id", None)
    content = getattr(part, "content", "")
    outcome = getattr(part, "outcome", "success")

    # Status indicator
    status_icon = "✅" if str(outcome) == "success" else "❌"

    id_display = tool_call_id or "?"

    # Try to get tool name from pending calls
    if tool_name:
        name_display = tool_name
    elif tool_call_id and tool_call_id in pending_tool_calls:
        name_display = pending_tool_calls[tool_call_id]
    else:
        name_display = "unknown"

    content_str = str(content) if content else ""
    truncated = _truncate(content_str, 200)

    lines.append(f"  🔠 {id_display} | {name_display} {status_icon}")
    if truncated.strip():
        lines.extend(_indent_lines(truncated, 4, max_lines=3))

    return lines


def _indent_lines(text: str, indent: int = 2, max_lines: int = 50) -> list[str]:
    """Indent each line of text with proper truncation.

    Args:
        text: Text to format
        indent: Number of spaces for indentation
        max_lines: Maximum number of lines to show

    Returns:
        List of indented lines
    """
    indent_str = " " * indent
    lines = []
    text_lines = text.split("\n")

    for i, line in enumerate(text_lines[:max_lines]):
        lines.append(f"{indent_str}{line}")

    if len(text_lines) > max_lines:
        remaining = len(text_lines) - max_lines
        lines.append(f"{indent_str}... ({remaining} more lines)")

    return lines


def _truncate(text: str, max_length: int | None = None) -> str:
    """Truncate text to max_length with ellipsis."""
    from zrb.config.config import CFG

    if max_length is None:
        max_length = CFG.LLM_HISTORY_TRUNCATE_LENGTH
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def _format_args(args) -> str:
    """Format tool call arguments for display."""
    import json

    if args is None:
        return "{}"
    if isinstance(args, str):
        if args.strip() in ["", "null", "{}"]:
            return "{}"
        try:
            obj = json.loads(args)
            if isinstance(obj, dict):
                return _truncate_kwargs(obj)
        except (json.JSONDecodeError, TypeError):
            return _truncate(args, 50)
    if isinstance(args, dict):
        # Remove 'dummy' key if present (schema sanitization artifact)
        args_clean = {k: v for k, v in args.items() if k != "dummy"}
        return _truncate_kwargs(args_clean)
    return _truncate(str(args), 50)


def _truncate_kwargs(kwargs: dict, max_length: int = 30) -> str:
    """Truncate keyword arguments for display."""
    import json

    truncated = {}
    for key, val in kwargs.items():
        if isinstance(val, str) and len(val) > max_length:
            truncated[key] = f"{val[:max_length-3]}..."
        else:
            truncated[key] = val
    try:
        return json.dumps(truncated, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(truncated)


def _format_timestamp(timestamp) -> str:
    """Format timestamp for display.

    Args:
        timestamp: datetime object or ISO string or None

    Returns:
        Formatted timestamp (HH:MM) or empty string
    """
    if timestamp is None:
        return ""

    try:
        if isinstance(timestamp, str):
            # Parse ISO format
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
