from collections.abc import Generator
from dataclasses import replace
from typing import Any

# Self-describing placeholders injected when a part would otherwise be empty or
# text-less. Centralised here (the lowest-level history module) so every layer
# that has to patch history for provider compatibility uses the same literals.
# They are deliberately human-readable so the model can tell a missing payload
# from a real terse response and not imitate a literal "." in its next turn.
TOOL_CALL_PLACEHOLDER = "(tool call)"
EMPTY_CONTENT_PLACEHOLDER = "(empty)"
# ToolReturnParts use "null" (not "(empty)") because some providers special-case
# a literal null tool result.
TOOL_RETURN_NULL_PLACEHOLDER = "null"


def ensure_alternating_roles(messages: list[Any]) -> list[Any]:
    """
    Ensures that the message history has alternating roles (User/Model -> Model/User).
    Consecutive messages of the same role are merged.
    """
    if not messages:
        return messages

    # lazy: heavy third-party
    from pydantic_ai.messages import ModelRequest, ModelResponse

    new_messages: list[Any] = []
    for msg in messages:
        if not new_messages:
            new_messages.append(msg)
            continue

        last_msg = new_messages[-1]

        # Case 1: Sequential ModelRequests (User -> User) - MERGE
        # replace() keeps non-part fields (instructions, run_id, ...) that a
        # freshly constructed ModelRequest would silently drop.
        if isinstance(msg, ModelRequest) and isinstance(last_msg, ModelRequest):
            new_last_msg = replace(
                last_msg, parts=list(last_msg.parts) + list(msg.parts)
            )
            new_messages[-1] = new_last_msg
            continue

        # Case 2: Sequential ModelResponses (Assistant -> Assistant) - MERGE
        if isinstance(msg, ModelResponse) and isinstance(last_msg, ModelResponse):

            new_last_msg = replace(
                last_msg, parts=list(last_msg.parts) + list(msg.parts)
            )
            new_messages[-1] = new_last_msg
            continue

        new_messages.append(msg)

    return new_messages


def _strip_orphaned_parts(
    msg: "Any",
    orphaned_ids: "set[str]",
    part_type: "type | tuple[type, ...]",
    ensure_text: bool = False,
) -> "Any | None":
    """Return *msg* with parts matching *orphaned_ids* removed, or ``None`` if empty.

    When *ensure_text* is ``True`` and the result has no ``TextPart`` with
    content, a ``TOOL_CALL_PLACEHOLDER`` text part is prepended so the message
    stays valid.
    """
    # lazy: heavy third-party
    from pydantic_ai.messages import TextPart

    new_parts = [
        p
        for p in msg.parts
        if not (
            isinstance(p, part_type)
            and getattr(p, "tool_call_id", None) in orphaned_ids
        )
    ]
    if not new_parts:
        return None
    if new_parts != list(msg.parts):
        if ensure_text and not any(
            isinstance(p, TextPart) and p.content for p in new_parts
        ):
            new_parts.insert(0, TextPart(content=TOOL_CALL_PLACEHOLDER))
        return replace(msg, parts=new_parts)
    return msg


def sanitize_orphaned_tool_calls(messages: list[Any]) -> list[Any]:
    """Remove ToolCallParts with no matching ToolReturnPart and vice versa.

    After history compression the kept slice can contain tool calls whose
    returns were in the summarised portion (or vice versa).  Most providers
    (Bedrock, OpenAI) reject a conversation where a tool call has no following
    return.  This function strips the orphaned parts and patches any messages
    that become text-less as a result.
    """
    # lazy: heavy third-party
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        RetryPromptPart,
        ToolCallPart,
        ToolReturnPart,
    )

    call_ids: set[str] = set()
    return_ids: set[str] = set()
    for _msg_idx, tool_call_id, kind in _iter_tool_events(messages):
        if kind == "call":
            call_ids.add(tool_call_id)
        else:
            return_ids.add(tool_call_id)

    orphaned_calls = call_ids - return_ids
    orphaned_returns = return_ids - call_ids

    if not orphaned_calls and not orphaned_returns:
        return messages

    result = []
    for msg in messages:
        if isinstance(msg, ModelResponse) and orphaned_calls:
            patched = _strip_orphaned_parts(
                msg, orphaned_calls, ToolCallPart, ensure_text=True
            )
            if patched is not None:
                result.append(patched)
        elif isinstance(msg, ModelRequest) and orphaned_returns:
            patched = _strip_orphaned_parts(
                msg, orphaned_returns, (ToolReturnPart, RetryPromptPart)
            )
            if patched is not None:
                result.append(patched)
        else:
            result.append(msg)
    return result


def strip_orphaned_returns(messages: list[Any]) -> list[Any]:
    """Remove ToolReturnParts whose matching ToolCallPart is not in *messages*.

    Unlike sanitize_orphaned_tool_calls, this does NOT remove orphaned
    ToolCallParts — they may be pending deferred tool results from the
    model's most recent turn.  Only ToolReturnParts whose calls were in
    the summarised (dropped) portion are stripped.
    """
    # lazy: heavy third-party
    from pydantic_ai.messages import (
        ModelRequest,
        RetryPromptPart,
        ToolReturnPart,
    )

    call_ids: set[str] = set()
    return_ids: set[str] = set()
    for _msg_idx, tool_call_id, kind in _iter_tool_events(messages):
        if kind == "call":
            call_ids.add(tool_call_id)
        else:
            return_ids.add(tool_call_id)

    orphaned_returns = return_ids - call_ids
    if not orphaned_returns:
        return messages

    result: list[Any] = []
    for msg in messages:
        if isinstance(msg, ModelRequest) and orphaned_returns:
            patched = _strip_orphaned_parts(
                msg, orphaned_returns, (ToolReturnPart, RetryPromptPart)
            )
            if patched is not None:
                result.append(patched)
        else:
            result.append(msg)
    return result


def get_tool_pairs(messages: list[Any]) -> dict[str, dict[str, int | None]]:
    """
    Extract tool call/return pairs from messages.

    Returns a dict mapping tool_call_id to {"call_idx": index, "return_idx": index}
    where indices are message indices containing the call/return.
    """
    tool_pairs: dict[str, dict[str, int | None]] = {}
    for _msg_idx, tool_call_id, kind in _iter_tool_events(messages):
        pair = tool_pairs.setdefault(
            tool_call_id, {"call_idx": None, "return_idx": None}
        )
        pair[f"{kind}_idx"] = _msg_idx
    return tool_pairs


def validate_tool_pair_integrity(messages: list[Any]) -> tuple[bool, list[str]]:
    """
    Check if all tool calls in the messages have corresponding returns.

    Returns (is_valid, list_of_problems)
    """
    tool_calls: dict[str, int] = {}
    tool_returns: dict[str, int] = {}
    for msg_idx, tool_call_id, kind in _iter_tool_events(messages):
        if kind == "call":
            tool_calls[tool_call_id] = msg_idx
        else:
            tool_returns[tool_call_id] = msg_idx

    problems = [
        *(
            f"Tool call {tid} at message {idx} has no return"
            for tid, idx in tool_calls.items()
            if tid not in tool_returns
        ),
        *(
            f"Tool return {tid} at message {idx} has no call"
            for tid, idx in tool_returns.items()
            if tid not in tool_calls
        ),
    ]
    return len(problems) == 0, problems


def _iter_tool_events(
    messages: list[Any],
) -> "Generator[tuple[int, str, str], None, None]":
    """Yield ``(msg_index, tool_call_id, kind)`` for every tool part in *messages*.

    *kind* is ``"call"`` for ``ToolCallPart`` and ``"return"`` for
    ``ToolReturnPart`` — or for a tool-linked ``RetryPromptPart``: pydantic-ai
    answers a failed tool call with a retry part that providers serialize as a
    ``role='tool'`` message, so for pairing purposes it *is* the return
    (mirrors ``history_utils``).  Tool-less retries (``tool_name is None``)
    are skipped: they map to user messages despite their auto-generated
    ``tool_call_id``.  Messages and parts that lack a ``tool_call_id`` (or
    the ``.parts`` attribute entirely) are silently skipped — this is deliberate:
    the caller expects a best-effort traversal, not an exception.

    Using a single traversal helper eliminates the duplicated for-loop /
    try-except / isinstance pattern that previously lived in three separate
    functions (``sanitize_orphaned_tool_calls``, ``get_tool_pairs``,
    ``validate_tool_pair_integrity``).
    """
    # lazy: heavy third-party
    from pydantic_ai.messages import RetryPromptPart, ToolCallPart, ToolReturnPart

    for msg_idx, msg in enumerate(messages):
        try:
            parts = getattr(msg, "parts", [])
        except AttributeError:
            continue
        for part in parts:
            tool_call_id = getattr(part, "tool_call_id", None)
            if not tool_call_id:
                continue
            if isinstance(part, ToolCallPart):
                yield msg_idx, tool_call_id, "call"
            elif isinstance(part, ToolReturnPart):
                yield msg_idx, tool_call_id, "return"
            elif isinstance(part, RetryPromptPart) and part.tool_name:
                yield msg_idx, tool_call_id, "return"
