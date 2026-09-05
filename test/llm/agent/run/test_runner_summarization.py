from unittest.mock import MagicMock

import pytest
from pydantic_ai import AgentRunResultEvent

from zrb.llm.agent.run.runner import run_agent
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.hook.interface import HookResult
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent


def _run_from(agen_func):
    """Wrap an async generator function into an ``agent.run(event_stream_handler=...)`` mock.

    ``agen_func`` keeps yielding the same events every test already
    constructs, ending with ``AgentRunResultEvent(result=...)`` (the old
    ``run_stream_events()`` shape). Real pydantic-ai's ``event_stream_handler``
    never receives that trailing event -- it's ``run_stream_events()``'s own
    addition, synthesized by its consumer-facing iterator after the
    background run finishes. This strips it the same way ``_execution_loop``
    does and returns its ``.result`` as ``agent.run()``'s return value.
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


@pytest.mark.asyncio
async def test_run_agent_summarization_keeps_turn_boundary_valid():
    """A history processor that summarizes -- replaces a whole span of old
    messages with one shorter summary message -- must not corrupt the turn
    boundary. Stop's `turn` field (sliced from the post-processor baseline)
    must be exactly this turn's own new messages, never the summarized-away
    old ones and never an out-of-range slice."""
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        TextPart,
        UserPromptPart,
    )

    from zrb.llm.agent.common import create_agent

    old_history = [
        ModelRequest(parts=[UserPromptPart(content=f"question {i}")]) for i in range(6)
    ]
    # A ModelResponse, not a ModelRequest: ending on a ModelRequest would hit
    # merge_consecutive_messages's same-role-merge and fold "Hi" into the
    # summary itself instead of starting a new turn message — a different
    # (also real) code path, not the one this test targets.
    summary_message = ModelResponse(
        parts=[TextPart(content="[SUMMARY of 6 earlier turns]")]
    )

    async def summarizer(msgs, system_prompt_overhead: int = 0):
        # Real summarization shape: the whole span collapses to one message.
        return [summary_message]

    agent = create_agent(
        model="openai-chat:gpt-4o-mini",
        system_prompt="test",
        history_processors=[summarizer],
        yolo=True,
    )

    new_turn_messages = [
        ModelRequest(parts=[UserPromptPart(content="Hi")]),
        ModelResponse(parts=[TextPart(content="done")]),
    ]
    mock_result = MagicMock()
    mock_result.output = "done"
    mock_result.all_messages.return_value = [summary_message, *new_turn_messages]

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    agent.run = _run_from(_gen)

    captured: list = []

    async def record(context):
        captured.append(context.event_data)
        return HookResult(success=True)

    manager = HookManager(search_dirs=[])
    manager.add_hook(record, events=[HookEvent.STOP])

    result, history = await run_agent(
        agent=agent,
        message="Hi",
        message_history=list(old_history),
        limiter=LLMLimiter(),
        hook_manager=manager,
    )

    def _texts(messages):
        return [
            p.content
            for msg in messages
            for p in getattr(msg, "parts", [])
            if isinstance(p, (UserPromptPart, TextPart))
        ]

    assert result == "done"
    # The summary replaced the old span outright: none of the six original
    # questions survive in the returned history, and the summary is present.
    assert all(f"question {i}" not in _texts(history) for i in range(6))
    assert "[SUMMARY of 6 earlier turns]" in _texts(history)
    # The turn boundary is still correct even though history shrank
    # underneath it: Stop's "turn" is exactly this round's new messages, not
    # the summary (which predates round_baseline) and not an invalid slice.
    assert _texts(captured[0]["turn"]) == _texts(new_turn_messages)
    assert len(captured[0]["turn"]) == len(new_turn_messages)
