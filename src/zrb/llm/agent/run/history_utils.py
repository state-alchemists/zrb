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
    from pydantic_ai.messages import (  # lazy: heavy third-party
        ModelResponse,
        TextPart,
        ThinkingPart,
    )

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


def filter_nil_content(messages: list[Any]) -> list[Any]:
    """Sanitize message history before sending to any provider.

    Fixes applied in one pass:
    - None/empty/whitespace content → "." (or "null" for ToolReturnPart)
    - ToolCallPart with no tool_name → dropped
    - ModelResponse with no text and no tool calls → TextPart(".") injected

    Bedrock rejects blank text fields, OpenAI rejects null content.
    """

    from pydantic_ai.messages import (  # lazy: heavy third-party
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


def _detect_problems(messages: list[Any]) -> list[str]:
    """Return a list of invariant violations found in message history.

    Checks semantic invariants that providers enforce but that pydantic-ai's
    TypeAdapter does not catch (e.g. content=None on a str-typed field, orphaned
    tool pairs, consecutive same-role messages, text-less ModelResponses).
    Intended for DEBUG-level logging before sanitize_history runs.
    """
    from pydantic_ai.messages import (  # lazy: heavy third-party
        ModelResponse,
        TextPart,
        ToolCallPart,
    )

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


def strip_to_text_only(history: list[Any]) -> list[Any]:
    """Sanitize history for last-resort retry.

    Converts ``ToolCallPart`` → ``[Tool: name(args)]``,
    ``BaseToolReturnPart`` → ``[Result (name): content]``, and
    ``ThinkingPart`` → its text content, so the provider receives only
    plain-text messages — no tool-call/response or reasoning structure
    that it might reject.

    Null/empty content is replaced with ``"."``.  Large tool results are
    truncated to ``_TOOL_RESULT_MAX_CHARS``.
    """
    from pydantic_ai.messages import (  # lazy: heavy third-party
        BaseToolReturnPart,
        ModelRequest,
        ModelResponse,
        TextPart,
        ThinkingPart,
        ToolCallPart,
    )

    def _normalize_content(part: Any) -> Any:
        if isinstance(part, ToolCallPart):
            return TextPart(content=_tool_call_to_text(part))
        if isinstance(part, BaseToolReturnPart):
            return TextPart(content=_tool_return_to_text(part))
        if isinstance(part, ThinkingPart):
            return TextPart(content=_thinking_part_content(part))
        if hasattr(part, "content"):
            content = part.content
            if content is None or (isinstance(content, str) and not content.strip()):
                return replace(part, content=".")
        return part

    result = []
    for msg in history:
        if isinstance(msg, (ModelRequest, ModelResponse)):
            parts = [_normalize_content(p) for p in msg.parts]
            # _normalize_content never returns None, so no filter needed.
            if isinstance(msg, ModelResponse):
                has_text = any(isinstance(p, TextPart) and p.content for p in parts)
                if not has_text:
                    parts.insert(0, TextPart(content="."))
            if parts:
                result.append(replace(msg, parts=parts))
        else:
            result.append(msg)

    if not result:
        return history
    return result


_TOOL_RESULT_MAX_CHARS = 500


def _tool_call_to_text(part: Any) -> str:
    """Convert a ToolCallPart to a descriptive text label."""
    from pydantic_ai.messages import ToolCallPart  # lazy: heavy third-party

    if not isinstance(part, ToolCallPart):
        return ""
    name = part.tool_name or "(unnamed)"
    args = part.args if hasattr(part, "args") and part.args else ""
    return f"[Tool: {name}({args})]"


def _tool_return_to_text(part: Any) -> str:
    """Convert a BaseToolReturnPart to a descriptive text label.

    Truncates large results to ``_TOOL_RESULT_MAX_CHARS`` to avoid blowing
    up the context window during a last-resort retry.
    """
    from pydantic_ai.messages import BaseToolReturnPart  # lazy: heavy third-party

    if not isinstance(part, BaseToolReturnPart):
        return ""
    name = part.tool_name if hasattr(part, "tool_name") else "(unnamed)"
    raw = part.content
    content = str(raw) if raw is not None else "(no value)"
    if len(content) > _TOOL_RESULT_MAX_CHARS:
        content = content[:_TOOL_RESULT_MAX_CHARS] + "..."
    return f"[Result ({name}): {content}]"


def _thinking_part_content(part: Any) -> str:
    """Extract the text content from a ThinkingPart."""
    from pydantic_ai.messages import ThinkingPart  # lazy: heavy third-party

    if not isinstance(part, ThinkingPart):
        return ""
    content = part.content if hasattr(part, "content") else ""
    return str(content) if content else "."
