from typing import TYPE_CHECKING, Any, Sequence

if TYPE_CHECKING:
    from pydantic_ai.messages import ModelRequest, ModelResponse
else:
    ModelRequest = Any
    ModelResponse = Any


def message_to_text(msg: Any) -> str:
    """Convert a pydantic_ai message to a readable text representation for summarization."""
    from pydantic_ai.messages import ModelRequest, ModelResponse

    if isinstance(msg, ModelRequest):
        return model_request_to_text(msg)
    if isinstance(msg, ModelResponse):
        return model_response_to_text(msg)
    # Fallback for unknown message types
    try:
        return str(msg)
    except Exception:
        return f"[Unconvertible message of type: {type(msg).__name__}]"


def model_request_to_text(msg: ModelRequest) -> str:
    from pydantic_ai.messages import (
        AudioUrl,
        BinaryContent,
        DocumentUrl,
        ImageUrl,
        SystemPromptPart,
        ToolReturnPart,
        UserPromptPart,
        VideoUrl,
    )

    parts = []
    # Safely get parts with default
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
                    elif isinstance(item, ImageUrl):
                        parts.append(f"[Image URL: {item.url}]")
                    elif isinstance(item, BinaryContent):
                        media_type = getattr(item, "media_type", "unknown")
                        parts.append(f"[Binary Content: {media_type}]")
                    elif isinstance(item, AudioUrl):
                        parts.append(f"[Audio URL: {item.url}]")
                    elif isinstance(item, VideoUrl):
                        parts.append(f"[Video URL: {item.url}]")
                    elif isinstance(item, DocumentUrl):
                        parts.append(f"[Document URL: {item.url}]")
                    else:
                        parts.append(f"[Unknown User Content: {type(item).__name__}]")
            else:
                parts.append(f"User: {str(content)}")
        elif isinstance(p, ToolReturnPart):
            tool_name = getattr(p, "tool_name", "unknown_tool")
            content = getattr(p, "content", None)
            if content is not None:
                content_str = str(content) if not isinstance(content, str) else content
                parts.append(f"Tool Result ({tool_name}): {content_str}")
            else:
                parts.append(f"Tool Result ({tool_name}): [No content]")
        elif isinstance(p, SystemPromptPart):
            content = getattr(p, "content", "")
            if content is not None:
                parts.append(f"System: {content}")
        else:
            # Fallback for unknown part types
            parts.append(f"[Unknown part type: {type(p).__name__}]")
    return "\n".join(parts) if parts else "[Empty ModelRequest]"


def model_response_to_text(msg: ModelResponse) -> str:
    from pydantic_ai.messages import FilePart, TextPart, ToolCallPart, ToolReturnPart

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
            # FilePart has 'content' which is likely BinaryContent
            content = getattr(p, "content", None)
            media_type = "unknown"
            if content:
                media_type = getattr(content, "media_type", "unknown")
            parts.append(f"[AI Generated File: {media_type}]")
        elif isinstance(p, ToolReturnPart):
            # Tool returns can also appear in ModelResponse in some cases
            tool_name = getattr(p, "tool_name", "unknown_tool")
            content = getattr(p, "content", None)
            if content is not None:
                content_str = str(content) if not isinstance(content, str) else content
                parts.append(f"AI Tool Result ({tool_name}): {content_str}")
        else:
            parts.append(f"[Unknown response part: {type(p).__name__}]")
    return "\n".join(parts) if parts else "[Empty ModelResponse]"
