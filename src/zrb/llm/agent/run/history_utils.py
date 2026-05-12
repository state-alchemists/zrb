"""History sanitization applied before every model call.

Several providers (DeepSeek, Bedrock, Ollama, …) reject histories that they
themselves produced one turn earlier — `content: null`, missing
`reasoning_content`, orphaned tool-call/return pairs after compression, etc.
`sanitize_history()` is the four-step defensive layer Zrb applies before
each `converse_stream` call to neutralise those provider-side inconsistencies.

For the full failure catalogue and the rationale behind each step, see
docs/advanced-topics/maintainer-guide.md#llm-history-sanitization-layer.
"""

from __future__ import annotations

from dataclasses import is_dataclass, replace
from typing import Any

from zrb.config.config import CFG
from zrb.llm.config.limiter import is_turn_start
from zrb.llm.message import (
    ensure_alternating_roles,
    sanitize_orphaned_tool_calls,
    validate_tool_pair_integrity,
)


def _detect_problems(messages: list[Any]) -> list[str]:
    """Return a list of invariant violations found in message history.

    Checks semantic invariants that providers enforce but that pydantic-ai's
    TypeAdapter does not catch (e.g. content=None on a str-typed field, orphaned
    tool pairs, consecutive same-role messages, text-less ModelResponses).
    Intended for DEBUG-level logging before sanitize_history runs.
    """
    from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart

    problems: list[str] = []
    prev_type: type | None = None

    for i, msg in enumerate(messages):
        parts = getattr(msg, "parts", None)
        if not parts:
            problems.append(f"msg[{i}] ({type(msg).__name__}) has no parts")
            prev_type = type(msg)
            continue

        for j, part in enumerate(parts):
            content = getattr(part, "content", "N/A")
            if content is None or content == "":
                problems.append(
                    f"msg[{i}].parts[{j}] ({type(part).__name__}) has nil/empty content"
                )

        if isinstance(msg, ModelResponse):
            has_text = any(isinstance(p, TextPart) and p.content for p in parts)
            has_tool = any(isinstance(p, ToolCallPart) for p in parts)
            if not has_text and not has_tool:
                problems.append(f"msg[{i}] ModelResponse has no text and no tool calls")

        if prev_type is not None and type(msg) is prev_type:
            problems.append(
                f"msg[{i}] and msg[{i - 1}] are consecutive {type(msg).__name__}"
            )
        prev_type = type(msg)

    _, pair_problems = validate_tool_pair_integrity(messages)
    problems.extend(pair_problems)
    return problems


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

    Violations found before fixing are logged at DEBUG level so that the root cause
    of provider 400 errors can be traced in logs without any production overhead.
    """

    problems = _detect_problems(messages)
    if problems:
        for p in problems:
            CFG.LOGGER.debug(f"sanitize_history [pre-fix]: {p}")

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

        result.append(replace(msg, parts=new_parts))
    return result


def strip_to_text_only(history: list[Any]) -> list[Any]:
    """Sanitize history for retry: strip thinking, fix null/empty content.

    Preserves all message structure (ToolCallPart, ToolReturnPart,
    UserPromptPart, etc.) but ensures every content field is a valid
    non-null, non-empty text string. Removes ThinkingPart entries,
    which cause ``reasoning_content`` serialization issues on many
    providers (DeepSeek, GLM-5 on Bedrock, etc.).

    This is the provider-agnostic "nuclear option": it doesn't guess
    what upset the provider — it normalises everything to the lowest
    common denominator that every provider accepts.
    """
    from pydantic_ai.messages import (
        BaseToolReturnPart,
        ModelRequest,
        ModelResponse,
        TextPart,
        ThinkingPart,
        ToolCallPart,
        UserPromptPart,
    )

    def _normalize_content(part: Any) -> Any | None:
        if isinstance(part, ThinkingPart):
            return None
        if isinstance(part, ToolCallPart):
            if part.tool_name:
                return TextPart(content=f"[Tool: {part.tool_name}({part.args})]")
            return None
        if isinstance(part, BaseToolReturnPart):
            content = part.content
            if content is None or (isinstance(content, str) and not content.strip()):
                display = "(no value)"
            else:
                display = content
            return UserPromptPart(content=f"[Result ({part.tool_name}): {display}]")
        if hasattr(part, "content"):
            content = part.content
            if content is None or (isinstance(content, str) and not content.strip()):
                return replace(part, content=".")
        return part

    result = []
    for msg in history:
        if isinstance(msg, (ModelRequest, ModelResponse)):
            parts = [_normalize_content(p) for p in msg.parts]
            parts = [p for p in parts if p is not None]
            if isinstance(msg, ModelResponse):
                has_text = any(isinstance(p, TextPart) and p.content for p in parts)
                has_tool = any(isinstance(p, ToolCallPart) for p in parts)
                if not has_text and has_tool:
                    parts.insert(0, TextPart(content="."))
                elif not has_text and not has_tool:
                    parts.insert(0, TextPart(content="."))
            if parts:
                result.append(replace(msg, parts=parts))
        else:
            result.append(msg)

    if not result:
        return history
    return result


def filter_nil_content(messages: list[Any]) -> list[Any]:
    """Sanitize message history before sending to any provider.

    Fixes applied in one pass:
    - None/empty/whitespace content → "." (or "null" for ToolReturnPart)
    - ToolCallPart with no tool_name → dropped
    - ModelResponse with no text and no tool calls → TextPart(".") injected

    Bedrock rejects blank text fields, OpenAI rejects null content.
    """

    from pydantic_ai.messages import (
        BaseToolReturnPart,
        ModelRequest,
        ModelResponse,
        TextPart,
        ToolCallPart,
    )

    def _sanitize(part: Any) -> Any:
        """Replace bad content with provider-safe placeholder."""
        # Skip non-dataclasses and dataclasses without a content field
        # (e.g. BuiltinToolCallPart, which carries args instead of content).
        if not is_dataclass(part) or not hasattr(part, "content"):
            return part
        content = part.content
        if content is None or (isinstance(content, str) and not content.strip()):
            placeholder = "null" if isinstance(part, BaseToolReturnPart) else "."
            return replace(part, content=placeholder)
        return part

    filtered = []
    for msg in messages:
        if not isinstance(msg, (ModelRequest, ModelResponse)):
            filtered.append(msg)
            continue

        valid_parts = []
        has_text = False
        for part in msg.parts:
            if isinstance(part, ToolCallPart):
                if part.tool_name:
                    valid_parts.append(part)
            else:
                valid_parts.append(_sanitize(part))
                if isinstance(part, TextPart):
                    has_text = True

        # Providers reject assistant messages with no text and no tool calls
        if isinstance(msg, ModelResponse) and not has_text and valid_parts:
            valid_parts.insert(0, TextPart(content="."))

        if valid_parts:
            filtered.append(replace(msg, parts=valid_parts))

    return filtered
