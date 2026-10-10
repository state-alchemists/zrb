"""History sanitization applied before every model call.

Several providers reject histories they produced a turn earlier (`content:
null`, missing `reasoning_content`, orphaned tool pairs). The failure
catalogue is in docs/technical-specs/llm-history-sanitization.md.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import is_dataclass, replace
from enum import IntEnum
from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.llm.config.limiter import is_turn_start
from zrb.llm.message import (
    EMPTY_CONTENT_PLACEHOLDER,
    TOOL_CALL_PLACEHOLDER,
    TOOL_RETURN_NULL_PLACEHOLDER,
    ensure_alternating_roles,
    sanitize_orphaned_tool_calls,
    validate_tool_pair_integrity,
)
from zrb.util.truncate import truncate_display

if TYPE_CHECKING:
    from pydantic_ai import DeferredToolResults
    from pydantic_ai.messages import ModelMessage

_TOOL_RESULT_MAX_CHARS = 500


class TurnPruneFloor(IntEnum):
    """How many oldest turns `drop_oldest_turn` refuses to remove.

    `KEEP_DEFERRED_TURN` protects a turn holding an approved deferred tool
    call: dropping it would make the retry re-run a side-effecting tool.
    """

    ANY_TURN_MAY_DROP = 0
    KEEP_DEFERRED_TURN = 1


def drop_oldest_turn(
    history: list[Any],
    min_turns: "TurnPruneFloor | int" = TurnPruneFloor.ANY_TURN_MAY_DROP,
) -> list[Any]:
    """Remove the oldest turn, unless at most `min_turns` remain."""
    if not history:
        return history

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

    For providers that reject a stray `reasoning_content`; without
    ThinkingParts pydantic-ai sends none.
    """
    from pydantic_ai.messages import (
        ModelResponse,  # lazy: heavy third-party
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
            new_parts = [TextPart(content=TOOL_CALL_PLACEHOLDER)]
        elif not any(isinstance(p, TextPart) and p.content for p in new_parts):
            new_parts.insert(0, TextPart(content=TOOL_CALL_PLACEHOLDER))

        result.append(replace(msg, parts=new_parts))
    return result


def sanitize_history(
    messages: list[Any],
    allow_orphaned_tool_calls: bool = False,
) -> list[Any]:
    """Apply `_SANITIZE_STEPS` in order before a model call.

    `allow_orphaned_tool_calls=True` (set when resuming with
    `deferred_tool_results`) skips `sanitize_orphaned_tool_calls`. Violations
    before and after are logged at DEBUG only.
    """
    debug = CFG.LOGGER.isEnabledFor(logging.DEBUG)
    if debug:
        for p in _detect_problems(messages):
            CFG.LOGGER.debug(f"sanitize_history [pre-fix]: {p}")

    for step in _SANITIZE_STEPS:
        if step is sanitize_orphaned_tool_calls and allow_orphaned_tool_calls:
            continue
        messages = step(messages)

    if debug:
        remaining = _detect_problems(messages)
        if remaining:
            CFG.LOGGER.debug(
                "sanitize_history: problems remain after the pipeline — "
                f"step order or a step's contract may be wrong: {remaining}"
            )
    return messages


def filter_nil_content(messages: list[Any]) -> list[Any]:
    """Replace nil content with placeholders and drop nameless tool calls.

    - None/empty/whitespace content → "(empty)" (or "null" for ToolReturnPart)
    - ToolCallPart with no tool_name → dropped
    - ModelResponse with neither text nor tool calls → TextPart("(tool call)")

    Bedrock rejects blank text, OpenAI rejects null content. A tool-call-only
    response gets no placeholder: weaker models learn to echo it as output.
    """

    from pydantic_ai.messages import (  # lazy: heavy third-party
        BaseToolReturnPart,
        ModelRequest,
        ModelResponse,
        TextPart,
        ToolCallPart,
    )

    def _sanitize(part: Any) -> Any:
        # NativeToolCallPart carries args, not content.
        if not is_dataclass(part) or not hasattr(part, "content"):
            return part
        content = getattr(part, "content", None)
        if content is None or (isinstance(content, str) and not content.strip()):
            placeholder = (
                TOOL_RETURN_NULL_PLACEHOLDER
                if isinstance(part, BaseToolReturnPart)
                else EMPTY_CONTENT_PLACEHOLDER
            )
            dc_part: Any = part
            return replace(dc_part, content=placeholder)
        return part

    filtered = []
    for msg in messages:
        if not isinstance(msg, (ModelRequest, ModelResponse)):
            filtered.append(msg)
            continue

        valid_parts = []
        has_text = False
        has_tool_call = False
        for part in msg.parts:
            if isinstance(part, ToolCallPart):
                if part.tool_name:
                    valid_parts.append(part)
                    has_tool_call = True
            else:
                valid_parts.append(_sanitize(part))
                if isinstance(part, TextPart):
                    has_text = True

        if (
            isinstance(msg, ModelResponse)
            and not has_text
            and not has_tool_call
            and valid_parts
        ):
            valid_parts.insert(0, TextPart(content=TOOL_CALL_PLACEHOLDER))

        if valid_parts:
            filtered.append(replace(msg, parts=valid_parts))

    return filtered


# Each step's output must be valid input for the next.
_SANITIZE_STEPS: tuple[Callable[[list[Any]], list[Any]], ...] = (
    filter_nil_content,
    sanitize_orphaned_tool_calls,
    ensure_alternating_roles,
)


def _detect_problems(messages: list[Any]) -> list[str]:
    """Invariant violations providers enforce but pydantic-ai does not check."""
    from pydantic_ai.messages import (
        ModelResponse,  # lazy: heavy third-party
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

    Collapses structured parts into plain text legal inside the parent
    message type (pydantic-ai's openai mapper asserts on a ``TextPart`` in a
    ``ModelRequest``). Tool parts become a ``(sanitized-history)`` prose label,
    not call syntax, so the model does not imitate it:

    ``ModelResponse`` (assistant role):
        ``BaseToolCallPart``      → ``TextPart("(sanitized-history) previously attempted to call tool …")``
        ``NativeToolReturnPart`` → ``TextPart("(sanitized-history) previous result from tool …")``
        ``ThinkingPart``          → ``TextPart(content)``
        ``TextPart``              → kept (empty content normalised to ``"(empty)"``)
    A ``ModelResponse`` left without any text part gets a leading
    ``TextPart("(tool call)")`` injected so providers still accept it.

    ``ModelRequest`` (user role):
        ``ToolReturnPart``                       → ``UserPromptPart("(sanitized-history) previous result …")``
        ``RetryPromptPart`` with ``tool_name``   → ``UserPromptPart("(sanitized-history) prior retry feedback …")``
        ``UserPromptPart`` / ``SystemPromptPart``/ tool-less ``RetryPromptPart``
                                                 → kept (empty content normalised to ``"(empty)"``)

    Both sides of every tool pair are converted, so nothing is orphaned.
    Large tool results are truncated to ``_TOOL_RESULT_MAX_CHARS``.
    """
    from pydantic_ai.messages import (
        ModelRequest,  # lazy: heavy third-party
        ModelResponse,
        TextPart,
    )

    result = []
    for msg in history:
        if isinstance(msg, ModelRequest):
            parts = [_normalize_for_request(p) for p in msg.parts]
            if parts:
                result.append(replace(msg, parts=parts))
        elif isinstance(msg, ModelResponse):
            parts = [_normalize_for_response(p) for p in msg.parts]
            has_text = any(isinstance(p, TextPart) and p.content for p in parts)
            if not has_text:
                parts.insert(0, TextPart(content=TOOL_CALL_PLACEHOLDER))
            if parts:
                result.append(replace(msg, parts=parts))
        else:
            result.append(msg)

    if not result:
        return history
    return result


def _sanitize_content(part: Any) -> Any:
    """Replace empty or whitespace-only content with the empty placeholder."""
    if hasattr(part, "content"):
        content = part.content
        if content is None or (isinstance(content, str) and not content.strip()):
            return replace(part, content=EMPTY_CONTENT_PLACEHOLDER)
    return part


def _normalize_for_response(part: Any) -> Any:
    """Collapse one `ModelResponse` part to what the assistant role accepts."""
    from pydantic_ai.messages import (  # lazy: heavy third-party
        BaseToolCallPart,
        BaseToolReturnPart,
        TextPart,
        ThinkingPart,
    )

    if isinstance(part, BaseToolCallPart):
        return TextPart(content=_tool_call_to_text(part))
    if isinstance(part, BaseToolReturnPart):
        return TextPart(content=_tool_return_to_text(part))
    if isinstance(part, ThinkingPart):
        return TextPart(content=_thinking_part_content(part))
    return _sanitize_content(part)


def _normalize_for_request(part: Any) -> Any:
    """Collapse one `ModelRequest` part to what the user role accepts."""
    from pydantic_ai.messages import (  # lazy: heavy third-party
        RetryPromptPart,
        SystemPromptPart,
        ToolReturnPart,
        UserPromptPart,
    )

    if isinstance(part, ToolReturnPart):
        return UserPromptPart(content=_tool_return_to_text(part))
    if isinstance(part, RetryPromptPart) and getattr(part, "tool_name", None):
        # A tool-linked retry maps to a tool-role message; keep no tool_call_id.
        return UserPromptPart(content=_retry_prompt_to_text(part))
    if isinstance(part, (UserPromptPart, SystemPromptPart, RetryPromptPart)):
        return _sanitize_content(part)
    return part


def _tool_call_to_text(part: Any) -> str:
    """Convert a ToolCallPart to a prose label (models imitated ``[Tool: name(args)]``)."""
    from pydantic_ai.messages import ToolCallPart  # lazy: heavy third-party

    if not isinstance(part, ToolCallPart):
        return ""
    name = part.tool_name or "(unnamed)"
    args = part.args if hasattr(part, "args") and part.args else ""
    return (
        f"(sanitized-history) previously attempted to call tool "
        f'"{name}" with arguments {args}. This text is a record, '
        "not a tool-calling format — do not imitate it."
    )


def _tool_return_to_text(part: Any) -> str:
    """Convert a BaseToolReturnPart to a truncated prose label."""
    from pydantic_ai.messages import BaseToolReturnPart  # lazy: heavy third-party

    if not isinstance(part, BaseToolReturnPart):
        return ""
    name = part.tool_name if hasattr(part, "tool_name") else "(unnamed)"
    raw = part.content
    content = str(raw) if raw is not None else "(no value)"
    content = truncate_display(content, _TOOL_RESULT_MAX_CHARS)
    return f'(sanitized-history) previous result from tool "{name}": ' f"{content}"


def _thinking_part_content(part: Any) -> str:
    """Extract the text content from a ThinkingPart."""
    from pydantic_ai.messages import ThinkingPart  # lazy: heavy third-party

    if not isinstance(part, ThinkingPart):
        return ""
    content = part.content if hasattr(part, "content") else ""
    return str(content) if content else EMPTY_CONTENT_PLACEHOLDER


def _retry_prompt_to_text(part: Any) -> str:
    """Convert a tool-linked ``RetryPromptPart`` to a prose label."""
    from pydantic_ai.messages import RetryPromptPart  # lazy: heavy third-party

    if not isinstance(part, RetryPromptPart):
        return ""
    name = getattr(part, "tool_name", None) or "(unnamed)"
    raw = part.content if hasattr(part, "content") else None
    content = str(raw) if raw not in (None, "") else "(no value)"
    content = truncate_display(content, _TOOL_RESULT_MAX_CHARS)
    return f'(sanitized-history) prior retry feedback for tool "{name}": ' f"{content}"


def merge_consecutive_messages(current_history, current_message):
    # lazy: heavy third-party
    from pydantic_ai.messages import ModelRequest, UserPromptPart

    if (
        current_history
        and isinstance(current_history[-1], ModelRequest)
        and current_message is not None
        and isinstance(current_message, (str, list))
    ):
        # A NEW ModelRequest: the last message is aliased to the history
        # manager's cached list, so appending in place would duplicate the
        # prompt on the next save.
        last_msg = current_history[-1]
        merged_parts = list(last_msg.parts) + [UserPromptPart(content=current_message)]
        current_history[-1] = replace(last_msg, parts=merged_parts)
        return None
    return current_message


# The "(tool call)" placeholder, and the "(tool call" weaker models echo.
_EMPTY_COMPLETION_MARKERS = frozenset(
    {TOOL_CALL_PLACEHOLDER, TOOL_CALL_PLACEHOLDER.rstrip(")")}
)


def is_empty_completion(result_output: Any) -> bool:
    """True when a str output is blank or just the "(tool call)" placeholder."""
    if not isinstance(result_output, str):
        return False
    stripped = result_output.strip()
    return not stripped or stripped in _EMPTY_COMPLETION_MARKERS


def close_dangling_tool_calls(history: list[Any], reason: str) -> list[Any]:
    """Synthesize a `ToolReturnPart` for every unresolved trailing `ToolCallPart`.

    An interrupted run leaves those calls dangling, which most providers
    reject. No-op unless the last message is a `ModelResponse` with tool calls.
    """
    # lazy: heavy third-party
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        ToolCallPart,
        ToolReturnPart,
    )

    if not history or not isinstance(history[-1], ModelResponse):
        return history
    tool_returns = [
        ToolReturnPart(
            tool_name=part.tool_name, content=reason, tool_call_id=part.tool_call_id
        )
        for part in history[-1].parts
        if isinstance(part, ToolCallPart)
    ]
    if not tool_returns:
        return history
    return [*history, ModelRequest(parts=tool_returns)]


def history_through_deferred_returns(
    messages: "list[ModelMessage]", results: "DeferredToolResults"
) -> "list[ModelMessage] | None":
    """`messages` cut after its last `ModelRequest`, when it already holds a
    tool return for one of `results`' deferred calls.

    That is how far a resumed round got once pydantic-ai ran the approved
    tools, whatever failed after. `None` when the round never ran them.
    """
    from pydantic_ai.messages import (
        ModelRequest,  # lazy: heavy third-party
        RetryPromptPart,
        ToolReturnPart,
    )

    deferred_ids = {*results.approvals, *results.calls}
    request_indexes = [
        i for i, msg in enumerate(messages) if isinstance(msg, ModelRequest)
    ]
    has_deferred_return = any(
        isinstance(part, (ToolReturnPart, RetryPromptPart))
        and part.tool_call_id in deferred_ids
        for i in request_indexes
        for part in messages[i].parts
    )
    if not has_deferred_return:
        return None
    return list(messages[: request_indexes[-1] + 1])


def history_without_trailing_response(run_history: list[Any]) -> list[Any]:
    """Drop the trailing ModelResponse so an empty completion can be regenerated."""
    from pydantic_ai.messages import ModelResponse  # lazy: heavy third-party

    if run_history and isinstance(run_history[-1], ModelResponse):
        trimmed = run_history[:-1]
        if trimmed:
            return trimmed
    return run_history
