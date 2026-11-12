"""A history processor that notices serially-issued independent lookups.

Every round re-sends the whole conversation, so three `Read` calls made in
three rounds cost three request bodies where one would do. The rule asking the
model to batch is in the prompt already; this is the check that notices when it
was ignored, and says so once rather than every round after — once in the user
turn that ignored it. A nudge silences the rest of its own turn and nothing
past it: the turn after may be a new question, may arrive an hour later, or may
be a conversation resumed from a compaction, and the model is told again.

Only calls that are certainly independent are counted: a lookup tool calling
once per round, over consecutive rounds, on *different* arguments. The tools
may differ — a `Read` between two `Grep` calls is still three lookups issued
one round apart, since none of them needs the last one's output. Writes and
shell commands are never counted — there the next call usually depends on what
the previous one printed, and batching them would be wrong.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.config.limiter import is_turn_start
from zrb.llm.shared.agent_state import get_current_model
from zrb.llm.util.capabilities import model_capabilities

if TYPE_CHECKING:
    from zrb.llm.agent.types import ModelMessage

# Lookups whose calls are interchangeable: reading one more file or directory
# needs nothing from the last one's output.
BATCHABLE_TOOLS = frozenset({"Read", "Grep", "Glob", "LS"})
"""Tools a single-call streak may be made of."""

STREAK_LENGTH = 3
"""Single-call rounds in a row that count as evidence, not as a coincidence."""

NUDGE_MARKER = "[SYSTEM SUGGESTION]: batching"
"""Opening words of an injected nudge; their presence suppresses the next one."""


def create_batch_nudge_processor() -> (
    "Callable[[list[ModelMessage], int], Awaitable[list[ModelMessage]]]"
):
    """Create the processor, shaped as a zrb history processor.

    The second positional argument is the system-prompt overhead the runner
    passes to every processor; this one does not measure tokens, so it is
    accepted and ignored.
    """

    async def process_history(
        messages: "list[ModelMessage]", system_prompt_overhead: int = 0
    ) -> "list[ModelMessage]":
        if not CFG.LLM_BATCH_TOOL_CALL_NUDGE_ENABLED or (
            _is_parallel_calls_unsupported()
        ):
            return messages
        tool_names = _single_call_streak_tools(messages)
        if tool_names is None:
            return messages
        return [*messages, _create_nudge(tool_names)]

    return process_history


def _is_parallel_calls_unsupported() -> bool:
    """Whether the run's model is known to malform parallel tool calls.

    `supports_parallel_tool_calls` is a deny-list, so only `False` is acted on:
    `None` means unknown, and an unknown model keeps the reminder. For a model
    on the list the System Context has already withdrawn the batch rule, and a
    reminder pushing the other way would cost it both calls in the round.
    """
    model = get_current_model() or CFG.LLM_MODEL
    return model_capabilities.get(model).supports_parallel_tool_calls is False


def _single_call_streak_tools(messages: "list[ModelMessage]") -> list[str] | None:
    """The tools of a trailing single-call streak, or ``None`` when there is none.

    The tools may differ: three lookups issued one round apart are the same
    waste whether or not they are the same lookup. Walking backwards, a final
    answer with no tool calls ends the tail the question is about, a round that
    already carried several calls shows the model is batching, and a call that
    is not a lookup ends it too — any of the three answers ``None``. A nudge
    already in this turn answers ``None`` as well; one from an earlier turn does
    not, because the model has been asked something else since.
    """
    if _is_reminded_this_turn(messages):
        return None
    collected: list[tuple[str, str]] = []
    for message in reversed(messages):
        calls = _tool_calls(message)
        if calls is None:
            continue
        if not calls or len(calls) > 1:
            return None
        tool_name, args = calls[0]
        if tool_name not in BATCHABLE_TOOLS:
            return None
        collected.append((tool_name, args))
        if len(collected) == STREAK_LENGTH:
            if not _is_each_call_distinct(collected):
                return None
            return [name for name, _ in collected]
    return None


def _is_reminded_this_turn(messages: "list[ModelMessage]") -> bool:
    """Whether a nudge already sits in the user turn the next request belongs to.

    The turn starts at the latest user prompt, which is `is_turn_start` — the
    boundary the limiter prunes by, the summarizer splits by and the retry
    prunes to: a request carrying a `UserPromptPart` and no tool return. Context
    zrb injects rides inside the request that carries the person's own words
    (`runner.run_agent` prepends a hook's `additionalContext` to their message,
    and the live-context block is appended to it), so that request is their
    turn. A request that merges a prompt with tool returns is a tool result —
    often an image — rather than someone speaking, and no turn starts there. A
    block zrb injects standing alone does start one: telling those apart would
    take a list of their opening words to maintain, and each is the model being
    addressed afresh rather than a streak the reminder already covers.

    The scan covers the whole turn, not the rounds the streak walk collects: the
    walk stops as soon as it has its three, so a nudge four rounds back would
    never be reached, and it is still this turn's reminder.
    """
    turn: list[object] = []
    for message in reversed(messages):
        turn.append(message)
        if is_turn_start(message):
            break
    # With no user prompt anywhere there is nothing to separate turns by, so the
    # whole history is one.
    return any(_is_nudge(seen) for seen in turn)


def _is_nudge(message: object) -> bool:
    """Whether the message is a nudge zrb injected.

    Only a user prompt can carry one, that being the role the nudge is injected
    as. A tool result that quotes this module — a `Read` of its own source —
    mentions the marker without being a reminder.
    """
    return any(NUDGE_MARKER in text for text in _prompt_texts(message))


def _tool_calls(message: object) -> list[tuple[str, str]] | None:
    """The message's tool calls as ``(name, rendered args)``, or ``None`` when
    it is not a model response.

    Parts are read by `part_kind`, as `usage_log.count_tool_calls` does; the
    response check is the one thing needing the type, and it is imported here so
    importing this module stays free of pydantic-ai.
    """
    from zrb.llm.agent.types import ModelResponse

    if not isinstance(message, ModelResponse):
        return None
    calls: list[tuple[str, str]] = []
    for part in getattr(message, "parts", None) or ():
        if getattr(part, "part_kind", "") != "tool-call":
            continue
        name = getattr(part, "tool_name", "")
        if not isinstance(name, str) or not name:
            continue
        calls.append((name, _render_args(getattr(part, "args", None))))
    return calls


def _render_args(args: object) -> str:
    """One comparable form for a call's arguments: key order must not matter."""
    try:
        return json.dumps(args, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return repr(args)


def _is_each_call_distinct(collected: list[tuple[str, str]]) -> bool:
    """Whether every call in the streak asked for something different.

    The tool is part of what was asked: `Grep x` after `Glob x` is two
    lookups even though their arguments are identical, while the same tool on
    the same arguments is one lookup repeated.
    """
    return len(set(collected)) == len(collected)


def _prompt_texts(message: object) -> list[str]:
    """The textual user prompts a message carries.

    Parts are read by `part_kind`, as `_tool_calls` does, so this needs no
    pydantic-ai type.
    """
    texts: list[str] = []
    for part in getattr(message, "parts", None) or ():
        if getattr(part, "part_kind", "") != "user-prompt":
            continue
        content = getattr(part, "content", None)
        if isinstance(content, str):
            texts.append(content)
    return texts


def _create_nudge(tool_names: list[str]) -> "ModelMessage":
    """The nudge, as the user turn that carries it."""
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import ModelRequest, UserPromptPart

    distinct = sorted(set(tool_names))
    call = f"one `{distinct[0]}` call" if len(distinct) == 1 else "a single lookup"
    return ModelRequest(
        parts=[
            UserPromptPart(
                content=(
                    f"{NUDGE_MARKER} — the last {STREAK_LENGTH} rounds each carried "
                    f"{call} on different arguments. If those calls "
                    "did not depend on each other's results, put them in one "
                    "response: each extra round re-sends the whole conversation."
                )
            )
        ]
    )
