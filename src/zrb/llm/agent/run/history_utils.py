from __future__ import annotations

from typing import Any

from zrb.llm.config.limiter import is_turn_start


def sanitize_history(
    messages: list[Any],
    allow_orphaned_tool_calls: bool = False,
) -> list[Any]:
    """Comprehensive history sanitization applied before every model call.

    Applies fixes in a fixed order so each step's output is valid input for the next:
    1. filter_nil_content         — fix None/empty part content; inject "." placeholder
    2. sanitize_orphaned_tool_calls — remove unmatched ToolCallPart/ToolReturnPart pairs
       (skipped when allow_orphaned_tool_calls=True, i.e. when deferred_tool_results is set:
        ToolCallParts in history legitimately have no matching return in that path)
    3. Drop messages that are now empty (all parts were removed by the above steps)
    4. ensure_alternating_roles   — merge consecutive same-role messages

    This single call replaces the previous scattered filter_nil_content +
    sanitize_orphaned_tool_calls pair and also adds the missing alternating-role
    enforcement to the main agent loop.
    """
    from zrb.llm.message import ensure_alternating_roles, sanitize_orphaned_tool_calls

    messages = filter_nil_content(messages)
    if not allow_orphaned_tool_calls:
        messages = sanitize_orphaned_tool_calls(messages)
    messages = [m for m in messages if getattr(m, "parts", None)]
    messages = ensure_alternating_roles(messages)
    return messages


def drop_oldest_turn(history: list[Any], min_turns: int = 0) -> list[Any]:
    """Removes the oldest conversation turn from history.

    If `min_turns` is specified, it will not drop turns if it would result in
    fewer than `min_turns` remaining.
    """
    if not history:
        return history

    # Count existing turns
    turn_count = 0
    for msg in history:
        if is_turn_start(msg):
            turn_count += 1

    if turn_count > 0 and turn_count <= min_turns:
        return history

    # Find the start of the second turn and drop everything before it
    for i in range(1, len(history)):
        if is_turn_start(history[i]):
            return history[i:]
    # Only one turn (or no clear boundary) — clear all
    return []


def strip_thinking_parts(messages: list[Any]) -> list[Any]:
    """Strip ThinkingParts from all ModelResponse messages.

    Used when a provider rejects history because reasoning_content is present
    in an assistant message that had tool calls but the content was dropped.
    Stripping ThinkingParts prevents pydantic-ai from sending reasoning_content
    at all, which is accepted by all providers.
    """
    from pydantic_ai.messages import ModelResponse, TextPart, ThinkingPart

    result = []
    for msg in messages:
        if not isinstance(msg, ModelResponse):
            result.append(msg)
            continue
        new_parts = [p for p in msg.parts if not isinstance(p, ThinkingPart)]
        if not new_parts:
            new_parts = [TextPart(content=".")]
        elif not any(isinstance(p, TextPart) and p.content for p in new_parts):
            new_parts.insert(0, TextPart(content="."))
        from dataclasses import replace

        result.append(replace(msg, parts=new_parts))
    return result


def filter_nil_content(messages: list[Any]) -> list[Any]:
    """Filter out parts with None/nil content from messages.

    This prevents "invalid message content type: <nil>" errors from OpenAI-compatible APIs.
    Must be called at runtime before passing messages to the model.
    """
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        SystemPromptPart,
        TextPart,
        ThinkingPart,
        ToolCallPart,
        ToolReturnPart,
        UserPromptPart,
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
                    # Tool returns MUST match tool calls, so we cannot drop them.
                    if part.content is None:
                        from dataclasses import replace

                        valid_parts.append(replace(part, content="null"))
                    else:
                        valid_parts.append(part)
                elif isinstance(part, ThinkingPart):
                    if part.content is None:
                        from dataclasses import replace

                        valid_parts.append(replace(part, content="."))
                    else:
                        valid_parts.append(part)
                elif isinstance(part, (TextPart, UserPromptPart, SystemPromptPart)):
                    if part.content is None:
                        from dataclasses import replace

                        valid_parts.append(replace(part, content="."))
                    else:
                        valid_parts.append(part)
                elif hasattr(part, "content"):
                    if getattr(part, "content") is None:
                        from dataclasses import replace

                        valid_parts.append(replace(part, content="."))
                    else:
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
                    if not part.content:  # None or empty string
                        from dataclasses import replace

                        valid_parts.append(replace(part, content="."))
                        has_text = True
                    else:
                        valid_parts.append(part)
                        has_text = True
                elif isinstance(part, ToolCallPart):
                    valid_parts.append(part)
                    has_tool_call = True
                elif isinstance(part, ThinkingPart):
                    if part.content is None:
                        from dataclasses import replace

                        valid_parts.append(replace(part, content="."))
                    else:
                        valid_parts.append(part)
                elif hasattr(part, "content"):
                    if getattr(part, "content") is None:
                        from dataclasses import replace

                        valid_parts.append(replace(part, content="."))
                    else:
                        valid_parts.append(part)
                else:
                    valid_parts.append(part)

            # Providers reject assistant messages with no content and no tool_calls.
            # Use "." (not empty string, not space) because:
            #   - Bedrock rejects blank text fields (ValidationException)
            #   - Anthropic models on Bedrock reject whitespace-only text
            #   - pydantic_ai's own Bedrock model uses "." for the same reason
            # This also covers thinking-only responses (ThinkingPart but no TextPart)
            # where providers like DeepSeek send thinking via a separate field
            # (e.g. reasoning_content) and serialize content as null.
            if not has_text and valid_parts:
                valid_parts.insert(0, TextPart(content="."))

            if valid_parts:
                from dataclasses import replace

                filtered.append(replace(msg, parts=valid_parts))
        else:
            # Unknown message type - keep as-is
            filtered.append(msg)
    return filtered
