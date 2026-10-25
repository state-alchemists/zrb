"""A message as text: labelled for a reader, raw for a scanner.

Two callers want the same conversion for different reasons. Summarization wants
what a reader sees — ``User: …``, ``AI: …``, ``Tool Result (x): …`` — because
that text is handed to a model. A scan for a marker inside the content wants
the parts joined with no decoration, because a label in front of the marker
moves it off the start of the line it was written on.

Both live here, and here is a leaf: a compaction repair needs the same text the
summarizer does, and neither should have to import the package that happens to
own the other. That is what forced a second, subtly different extractor the
last time this was needed.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from zrb.llm.agent.types import ModelRequest, ModelResponse
else:
    ModelRequest = Any
    ModelResponse = Any

TAIL_TOOL_OUTPUT_LIMIT = 2_000
"""Characters of a tool result kept in a handover tail.

A tail is recency, not evidence: the messages it replaces are archived in full,
so 40,000 characters of test log left whole here spend the next turn's window on
output nobody will read again.
"""


def message_to_text(msg: Any, tool_output_limit: int | None = None) -> str:
    """A message as a reader sees it — `User: …`, `AI: …` — for a summary.

    *tool_output_limit* shortens each tool result to that many characters. It is
    for a caller that keeps the message as a handover rather than as evidence: a
    verbatim tail carrying an unchecked 40,000-character test log spends the next
    turn's window on output nobody will read again.
    """
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import ModelRequest, ModelResponse

    if isinstance(msg, ModelRequest):
        return model_request_to_text(msg, tool_output_limit)
    if isinstance(msg, ModelResponse):
        return model_response_to_text(msg, tool_output_limit)
    try:
        return str(msg)
    except Exception:
        return f"[Unconvertible message of type: {type(msg).__name__}]"


def render_verbatim_messages(
    messages: Sequence[object], tool_output_limit: int = TAIL_TOOL_OUTPUT_LIMIT
) -> str:
    """*messages* as one block of text, each tool result clipped to the limit.

    This is the form a compaction's kept tail is sent in, and so the form its
    size is measured in: a budget spent on the unclipped messages leaves most of
    itself unspent once the clipping happens. The two callers that matter are
    the renderer that sends the tail and the measurement that decides how much
    of it fits, which is why the conversion lives here rather than beside either.
    """
    return "\n".join(message_to_text(m, tool_output_limit) for m in messages)


def _clip_tool_output(content: object, limit: int | None) -> str:
    """*content* as text, shortened to *limit* characters when one is set."""
    text = content if isinstance(content, str) else str(content)
    if limit is None or limit <= 0 or len(text) <= limit:
        return text
    omitted = len(text) - limit
    return f"{text[:limit]}\n[truncated: {omitted} of {len(text)} characters omitted]"


def message_content_text(msg: object) -> str:
    """A message's parts joined as they were written, with no labels.

    For scanning content for a marker rather than for reading it: the labelled
    form prefixes every part, so a marker that began a line no longer does.
    """
    parts = getattr(msg, "parts", None) or ()
    return "\n".join(
        str(part.content)
        for part in parts
        if getattr(part, "content", None) is not None
    )


def model_request_to_text(
    msg: ModelRequest, tool_output_limit: int | None = None
) -> str:
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import SystemPromptPart, ToolReturnPart, UserPromptPart
    from zrb.llm.util.history_formatter import format_multimodal_item

    parts = []
    msg_parts = getattr(msg, "parts", [])
    for p in msg_parts:
        if isinstance(p, UserPromptPart):
            content = getattr(p, "content", "")
            if isinstance(content, str):
                parts.append(f"User: {content}")
            elif isinstance(content, Sequence):
                for item in content:
                    if isinstance(item, str):
                        parts.append(f"User: {item}")
                    else:
                        parts.append(format_multimodal_item(item))
            else:
                parts.append(f"User: {str(content)}")
        elif isinstance(p, ToolReturnPart):
            tool_name = getattr(p, "tool_name", "unknown_tool")
            content = getattr(p, "content", None)
            if content is not None:
                clipped = _clip_tool_output(content, tool_output_limit)
                parts.append(f"Tool Result ({tool_name}): {clipped}")
            else:
                parts.append(f"Tool Result ({tool_name}): [No content]")
        elif isinstance(p, SystemPromptPart):
            content = getattr(p, "content", "")
            if content is not None:
                parts.append(f"System: {content}")
        else:
            parts.append(f"[Unknown part type: {type(p).__name__}]")
    return "\n".join(parts) if parts else "[Empty ModelRequest]"


def model_response_to_text(
    msg: ModelResponse, tool_output_limit: int | None = None
) -> str:
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import FilePart, TextPart, ToolCallPart, ToolReturnPart

    parts = []
    msg_parts = getattr(msg, "parts", [])
    for p in msg_parts:
        if isinstance(p, TextPart):
            content = getattr(p, "content", "")
            if content is not None:
                parts.append(f"AI: {content}")
        elif isinstance(p, ToolCallPart):
            tool_name = getattr(p, "tool_name", "unknown_tool")
            args = getattr(p, "args", {})
            args_str = str(args) if args is not None else "{}"
            tool_call_id = getattr(p, "tool_call_id", "unknown_id")
            parts.append(f"AI Tool Call [{tool_call_id}]: {tool_name}({args_str})")
        elif isinstance(p, FilePart):
            content = getattr(p, "content", None)
            media_type = "unknown"
            if content:
                media_type = getattr(content, "media_type", "unknown")
            parts.append(f"[AI Generated File: {media_type}]")
        elif isinstance(p, ToolReturnPart):
            tool_name = getattr(p, "tool_name", "unknown_tool")
            content = getattr(p, "content", None)
            if content is not None:
                clipped = _clip_tool_output(content, tool_output_limit)
                parts.append(f"AI Tool Result ({tool_name}): {clipped}")
        else:
            parts.append(f"[Unknown response part: {type(p).__name__}]")
    return "\n".join(parts) if parts else "[Empty ModelResponse]"
