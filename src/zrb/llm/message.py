from collections.abc import Callable, Generator
from dataclasses import replace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from zrb.llm.agent.types import ModelMessage

# Placeholders for parts that would otherwise be empty or text-less. Readable so
# the model can tell a missing payload from a terse reply and not imitate it.
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

    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import ModelRequest, ModelResponse

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


def _is_tool_call(part: object) -> bool:
    """True when *part* is a tool call."""
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import ToolCallPart

    return isinstance(part, ToolCallPart)


def is_tool_return_part(part: object) -> bool:
    """True when *part* answers a tool call.

    Since pydantic-ai 2.60 that is a `ToolReturnPart` — a retry included, since a
    retry is the same part with `outcome='retried'`. History written before 2.60
    holds the deprecated `RetryPromptPart` instead; it is recognized by its kind
    and its id, so this module never imports the deprecated class, and a
    tool-less retry (which answers no call) is still not one.
    """
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import ToolReturnPart

    if isinstance(part, ToolReturnPart):
        return True
    return getattr(part, "part_kind", None) == "retry-prompt" and bool(
        getattr(part, "tool_call_id", None)
    )


def _strip_orphaned_parts(
    msg: "Any",
    orphaned_ids: "set[str]",
    matches: "Callable[[Any], bool]",
    ensure_text: bool = False,
) -> "Any | None":
    """Return *msg* with parts matching *orphaned_ids* removed, or ``None`` if empty.

    *matches* says which parts answer a call or make one — a predicate rather
    than a type, because a legacy retry part has to be recognized by its kind.
    When *ensure_text* is ``True`` and the result has no ``TextPart`` with
    content, a ``TOOL_CALL_PLACEHOLDER`` text part is prepended so the message
    stays valid.
    """
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import TextPart

    new_parts = [
        p
        for p in msg.parts
        if not (matches(p) and getattr(p, "tool_call_id", None) in orphaned_ids)
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
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import (
        ModelRequest,
        ModelResponse,
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
                msg, orphaned_calls, _is_tool_call, ensure_text=True
            )
            if patched is not None:
                result.append(patched)
        elif isinstance(msg, ModelRequest) and orphaned_returns:
            patched = _strip_orphaned_parts(
                msg, orphaned_returns, is_tool_return_part
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
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import ModelRequest

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
                msg, orphaned_returns, is_tool_return_part
            )
            if patched is not None:
                result.append(patched)
        else:
            result.append(msg)
    return result


def pending_tail_start(messages: "list[ModelMessage]") -> int | None:
    """The index where an unresolved (deferred) tool call's turn begins.

    A call with no return anywhere in *messages* may be a pending deferred
    tool result awaiting resumption (e.g. a permission approval in flight);
    from its message onward the tail must stay in native message form, not
    flattened text, so pydantic-ai can still resume it. Returns ``None`` when
    every call in *messages* already has its return.
    """
    tool_pairs = get_tool_pairs(messages)
    pending_indices = [
        indices["call_idx"]
        for indices in tool_pairs.values()
        if indices["call_idx"] is not None and indices["return_idx"] is None
    ]
    return min(pending_indices) if pending_indices else None


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
    ``ToolReturnPart``, which is also what a retry is since pydantic-ai 2.60
    (``outcome='retried'``; providers serialize it as a ``role='tool'``
    message). Parts without a ``tool_call_id`` are skipped.
    """
    for msg_idx, msg in enumerate(messages):
        for part in getattr(msg, "parts", []):
            tool_call_id = getattr(part, "tool_call_id", None)
            if not tool_call_id:
                continue
            if _is_tool_call(part):
                yield msg_idx, tool_call_id, "call"
            elif is_tool_return_part(part):
                yield msg_idx, tool_call_id, "return"
