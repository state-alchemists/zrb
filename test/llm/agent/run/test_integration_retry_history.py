"""Integration test: a stream-error retry must not duplicate or drop a
tool_call/tool_return pair already committed to history.

Real internal units wired together (`run_agent`, `TurnCursor`, `retry_loop`,
`history_utils`) with real `pydantic_ai.messages` objects — nothing mocked
below the model-call boundary (`agent.run` itself), matching the house style
of `test/llm/summarizer/test_integration_summarization.py` and
`test/llm/tool_call/test_tool_policy_integration.py`. Closes the coverage gap
`test_retry_loop.py`/`test_turn_cursor.py` leave: those operate on plain
string lists, never real `tool_call_id`-bearing message objects, so a real
duplication/loss regression in this already-correct mechanism would not be
caught by any existing test.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import AgentRunResultEvent
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from zrb.llm.agent.run.runner import run_agent
from zrb.llm.config.limiter import LLMLimiter


def _run_from(agen_func):
    """Wrap an async generator into an `agent.run(event_stream_handler=...)` fake.

    Local copy of `test_runner.py`'s helper — no cross-test-module imports
    elsewhere in this suite, so this stays self-contained.
    """

    async def fake_run(*args, **kwargs):
        handler = kwargs.pop("event_stream_handler", None)
        result_holder = []

        async def events():
            async for event in agen_func(*args, **kwargs):
                if isinstance(event, AgentRunResultEvent):
                    result_holder.append(event.result)
                    return
                yield event

        if handler is not None:
            await handler(MagicMock(), events())
        else:
            async for _ in events():
                pass
        return result_holder[0] if result_holder else None

    return fake_run


class _RetryableError(Exception):
    """A transient (429) provider error — matches `is_retryable_error`."""

    status_code = 429


def _history_with_one_tool_round() -> list:
    """A conversation already holding one resolved tool_call/tool_return pair."""
    return [
        ModelRequest(parts=[UserPromptPart(content="search for cats")]),
        ModelResponse(
            parts=[ToolCallPart(tool_name="search", args={}, tool_call_id="tc1")]
        ),
        ModelRequest(
            parts=[ToolReturnPart(tool_name="search", content="🐱", tool_call_id="tc1")]
        ),
    ]


def _count_parts_with_tool_call_id(messages: list, part_type: type) -> int:
    """How many *part_type* parts (e.g. `ToolCallPart`) carry tool_call_id "tc1".

    Counted per part-type rather than as one combined total: a resolved round
    has exactly one `ToolCallPart` *and* one `ToolReturnPart` tagged "tc1" —
    that pair is the correct, non-duplicated shape, not something to collapse
    into a single count.
    """
    count = 0
    for message in messages:
        for part in getattr(message, "parts", []):
            if isinstance(part, part_type) and part.tool_call_id == "tc1":
                count += 1
    return count


@pytest.mark.asyncio
async def test_transient_retry_does_not_duplicate_or_drop_tool_result():
    """First `agent.run()` call fails transiently *after* a tool round already
    landed in history; the retry must resend that round exactly once, not
    duplicate it (a naive retry that appends rather than resends) or drop it
    (a naive retry that resets history)."""
    history_in = _history_with_one_tool_round()
    agent = MagicMock()
    call_count = 0
    histories_seen = []

    async def _gen(*_args, **kwargs):
        nonlocal call_count
        call_count += 1
        histories_seen.append(kwargs.get("message_history"))
        if call_count == 1:
            raise _RetryableError("rate limited")
        good = MagicMock()
        good.output = "done"
        good.all_messages.return_value = history_in + [
            ModelResponse(parts=[TextPart(content="done")])
        ]
        yield AgentRunResultEvent(result=good)

    agent.run = _run_from(_gen)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result, new_history = await run_agent(
            agent=agent,
            message="continue",
            message_history=history_in,
            limiter=LLMLimiter(),
        )

    assert result == "done"
    assert call_count == 2
    # The retried (second) call must see the tool round exactly once: one
    # ToolCallPart, one ToolReturnPart — not duplicated, not dropped.
    assert _count_parts_with_tool_call_id(histories_seen[1], ToolCallPart) == 1
    assert _count_parts_with_tool_call_id(histories_seen[1], ToolReturnPart) == 1
    # The final history handed back to the caller must too.
    assert _count_parts_with_tool_call_id(new_history, ToolCallPart) == 1
    assert _count_parts_with_tool_call_id(new_history, ToolReturnPart) == 1


@pytest.mark.asyncio
async def test_opaque_400_retry_does_not_duplicate_or_drop_tool_result():
    """Same guarantee for the opaque-400 (unparseable provider error) path,
    which collapses history to text-only rather than resending verbatim —
    a different code path than the transient-retry case above."""

    class _OpaqueError(Exception):
        status_code = 400

        def __init__(self):
            super().__init__("something went wrong")
            self.body = {"message": "something went wrong"}

    history_in = _history_with_one_tool_round()
    agent = MagicMock()
    call_count = 0
    histories_seen = []

    async def _gen(*_args, **kwargs):
        nonlocal call_count
        call_count += 1
        histories_seen.append(kwargs.get("message_history"))
        if call_count == 1:
            raise _OpaqueError()
        good = MagicMock()
        good.output = "done"
        good.all_messages.return_value = history_in + [
            ModelResponse(parts=[TextPart(content="done")])
        ]
        yield AgentRunResultEvent(result=good)

    agent.run = _run_from(_gen)

    result, new_history = await run_agent(
        agent=agent,
        message="continue",
        message_history=history_in,
        limiter=LLMLimiter(),
    )

    assert result == "done"
    assert call_count == 2
    # strip_to_text_only collapses the round to text (0 real ToolCallPart/
    # ToolReturnPart is the correct, by-design outcome) — this must never
    # exceed 1 of either, which is what duplication would look like.
    assert _count_parts_with_tool_call_id(histories_seen[1], ToolCallPart) <= 1
    assert _count_parts_with_tool_call_id(histories_seen[1], ToolReturnPart) <= 1
    # The final history handed back to the caller must reflect the round
    # exactly once, not duplicated.
    assert _count_parts_with_tool_call_id(new_history, ToolCallPart) == 1
    assert _count_parts_with_tool_call_id(new_history, ToolReturnPart) == 1
