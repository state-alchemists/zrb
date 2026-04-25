from __future__ import annotations

from typing import Any

from zrb.llm.config.limiter import is_turn_start


def drop_oldest_turn(history: list[Any]) -> list[Any]:
    """Removes the oldest conversation turn from history."""
    if not history:
        return history
    # Find the start of the second turn and drop everything before it
    for i in range(1, len(history)):
        if is_turn_start(history[i]):
            return history[i:]
    # Only one turn (or no clear boundary) — clear all
    return []


def filter_nil_content(messages: list[Any]) -> list[Any]:
    """Filter out parts with None/nil content from messages.

    This prevents "invalid message content type: <nil>" errors from OpenAI-compatible APIs.
    Must be called at runtime before passing messages to the model.
    """
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        TextPart,
        ToolCallPart,
        ToolReturnPart,
        ThinkingPart,
    )

    filtered = []
    for msg in messages:
        if isinstance(msg, ModelRequest):
            # Filter parts in ModelRequest
            valid_parts = []
            for part in msg.parts:
                if isinstance(part, ToolCallPart):
                    # Keep tool calls that have a tool_name
                    if part.tool_name:
                        valid_parts.append(part)
                elif isinstance(part, ToolReturnPart):
                    # Keep tool returns, ensure content is not None
                    if part.content is not None:
                        valid_parts.append(part)
                elif isinstance(part, ThinkingPart):
                    if part.content is not None:
                        valid_parts.append(part)
                elif hasattr(part, "content"):
                    # TextPart, UserPromptPart, etc. - keep if content is not None
                    if part.content is not None:
                        valid_parts.append(part)
                else:
                    # Parts without content field - keep as-is
                    valid_parts.append(part)
            if valid_parts:
                from dataclasses import replace

                filtered.append(replace(msg, parts=valid_parts))
        elif isinstance(msg, ModelResponse):
            # Filter parts in ModelResponse
            valid_parts = []
            has_text = False
            has_tool_call = False
            for part in msg.parts:
                if isinstance(part, TextPart):
                    if part.content is not None:
                        valid_parts.append(part)
                        has_text = True
                elif isinstance(part, ToolCallPart):
                    valid_parts.append(part)
                    has_tool_call = True
                elif isinstance(part, ThinkingPart):
                    if part.content is not None:
                        valid_parts.append(part)
                elif hasattr(part, "content"):
                    if part.content is not None:
                        valid_parts.append(part)
                        # We don't set has_text=True for unknown parts with content
                else:
                    valid_parts.append(part)

            # Some providers (e.g. DeepSeek via Cloudflare) require a non-null
            # text content when tool calls are present.
            if has_tool_call and not has_text:
                valid_parts.insert(0, TextPart(content=""))

            if valid_parts:
                from dataclasses import replace

                filtered.append(replace(msg, parts=valid_parts))
        else:
            # Unknown message type - keep as-is
            filtered.append(msg)
    return filtered
