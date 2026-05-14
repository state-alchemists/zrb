from collections.abc import Generator
from dataclasses import replace
from typing import Any


def _iter_tool_events(
    messages: list[Any],
) -> "Generator[tuple[int, str, str], None, None]":
    """Yield ``(msg_index, tool_call_id, kind)`` for every tool part in *messages*.

    *kind* is ``"call"`` for ``ToolCallPart`` and ``"return"`` for
    ``ToolReturnPart``.  Messages and parts that lack a ``tool_call_id`` (or
    the ``.parts`` attribute entirely) are silently skipped — this is deliberate:
    the caller expects a best-effort traversal, not an exception.

    Using a single traversal helper eliminates the duplicated for-loop /
    try-except / isinstance pattern that previously lived in three separate
    functions (``sanitize_orphaned_tool_calls``, ``get_tool_pairs``,
    ``validate_tool_pair_integrity``).
    """
    from pydantic_ai.messages import ToolCallPart, ToolReturnPart

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


def ensure_alternating_roles(messages: list[Any]) -> list[Any]:
    """
    Ensures that the message history has alternating roles (User/Model -> Model/User).
    Consecutive messages of the same role are merged.
    """
    if not messages:
        return messages

    from pydantic_ai.messages import ModelRequest, ModelResponse

    new_messages: list[Any] = []
    for msg in messages:
        if not new_messages:
            new_messages.append(msg)
            continue

        last_msg = new_messages[-1]

        # Case 1: Sequential ModelRequests (User -> User) - MERGE
        if isinstance(msg, ModelRequest) and isinstance(last_msg, ModelRequest):
            new_last_msg = ModelRequest(parts=list(last_msg.parts) + list(msg.parts))
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
    part_type: "type",
    ensure_text: bool = False,
) -> "Any | None":
    """Return *msg* with parts matching *orphaned_ids* removed, or ``None`` if empty.

    When *ensure_text* is ``True`` and the result has no ``TextPart`` with
    content, a ``"."`` text part is prepended so the message stays valid.
    """
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
            new_parts.insert(0, TextPart(content="."))
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
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
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
            patched = _strip_orphaned_parts(msg, orphaned_returns, ToolReturnPart)
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
