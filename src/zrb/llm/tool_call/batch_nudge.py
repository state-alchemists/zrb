"""A history processor that notices serially-issued independent lookups.

Every round re-sends the whole conversation, so three `Read` calls made in
three rounds cost three request bodies where one would do. The rule asking the
model to batch is in the prompt already; this is the check that notices when it
was ignored, and says so once rather than every round after.

Only calls that are certainly independent are counted: the same lookup tool,
one call per round, over consecutive rounds, on *different* arguments. Writes
and shell commands are never counted — there the next call usually depends on
what the previous one printed, and batching them would be wrong.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from zrb.config.config import CFG
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
        tool_name = _single_call_streak_tool(messages)
        if tool_name is None:
            return messages
        return [*messages, _create_nudge(tool_name)]

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


def _single_call_streak_tool(messages: "list[ModelMessage]") -> str | None:
    """The tool of a trailing single-call streak, or ``None`` when there is none.

    Walking backwards, a final answer with no tool calls ends the tail the
    question is about, a round that already carried several calls shows the
    model is batching, and a nudge already in the history means this streak has
    been mentioned once — any of the three answers ``None``.
    """
    collected: list[tuple[str, str]] = []
    for message in reversed(messages):
        texts = _message_texts(message)
        if any(NUDGE_MARKER in text for text in texts):
            return None
        calls = _tool_calls(message)
        if calls is None:
            continue
        if not calls or len(calls) > 1:
            return None
        tool_name, args = calls[0]
        if tool_name not in BATCHABLE_TOOLS:
            return None
        if not _is_same_tool_streak(collected, tool_name):
            return None
        collected.append((tool_name, args))
        if len(collected) == STREAK_LENGTH:
            return tool_name if _is_each_call_distinct(collected) else None
    return None


def _is_same_tool_streak(collected: list[tuple[str, str]], tool_name: str) -> bool:
    """Whether nothing is collected yet, or all of it is this same tool."""
    return not collected or collected[-1][0] == tool_name


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
    """Whether every call in the streak asked for something different."""
    return len({args for _, args in collected}) == len(collected)


def _message_texts(message: object) -> list[str]:
    """The textual parts of a message, for spotting an earlier nudge."""
    texts: list[str] = []
    for part in getattr(message, "parts", None) or ():
        content = getattr(part, "content", None)
        if isinstance(content, str):
            texts.append(content)
    return texts


def _create_nudge(tool_name: str) -> "ModelMessage":
    """The nudge, as the user turn that carries it."""
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import ModelRequest, UserPromptPart

    return ModelRequest(
        parts=[
            UserPromptPart(
                content=(
                    f"{NUDGE_MARKER} — the last {STREAK_LENGTH} rounds each carried "
                    f"one `{tool_name}` call on different arguments. If those calls "
                    "did not depend on each other's results, put them in one "
                    "response: each extra round re-sends the whole conversation."
                )
            )
        ]
    )
