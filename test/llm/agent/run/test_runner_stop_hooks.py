from unittest.mock import MagicMock

import pytest
from pydantic_ai import AgentRunResultEvent

from zrb.llm.agent.run.runner import run_agent
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.hook.interface import HookContext, HookResult
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
async def test_stop_failure_fires_on_unrecoverable_error():
    """When a turn ends on an unrecoverable error, STOP_FAILURE fires with a
    classified error_type and the original exception still propagates."""
    captured: dict = {}

    async def rec(context: HookContext) -> HookResult:
        if context.event == HookEvent.STOP_FAILURE:
            captured["error_type"] = context.error_type
            captured["error"] = context.error
        return HookResult()

    manager = HookManager(search_dirs=[])
    manager.add_hook(rec, events=[HookEvent.STOP_FAILURE])

    agent = MagicMock()

    async def _gen(*args, **kwargs):
        raise ValueError("bad request")
        yield  # pragma: no cover — marks this a generator

    agent.run = _run_from(_gen)

    with pytest.raises(ValueError):
        await run_agent(
            agent=agent,
            message="hi",
            message_history=[],
            limiter=LLMLimiter(),
            hook_manager=manager,
        )

    assert captured.get("error_type") == "unknown"
    assert "bad request" in (captured.get("error") or "")


@pytest.mark.asyncio
async def test_run_agent_stop_replace_response_false():
    """Test STOP hook with replace_response=False returns original response."""
    agent = MagicMock()

    # Original response from LLM
    mock_original_result = MagicMock()
    mock_original_result.output = "Original AI response"
    mock_original_result.all_messages.return_value = []

    # Extended session response (should NOT be returned)
    mock_extended_result = MagicMock()
    mock_extended_result.output = "Extended session response"
    mock_extended_result.all_messages.return_value = []

    call_count = 0

    async def _gen(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield AgentRunResultEvent(result=mock_original_result)
        else:
            yield AgentRunResultEvent(result=mock_extended_result)

    agent.run = _run_from(_gen)

    # Stateful hook that only fires once (prevents infinite loop)
    class OnceHook:
        def __init__(self):
            self.fired = False

        async def __call__(self, context: HookContext) -> HookResult:
            if context.event == HookEvent.STOP:
                if not self.fired:
                    self.fired = True
                    return HookResult(
                        success=True,
                        modifications={
                            "systemMessage": "Side effect message",
                            "replaceResponse": False,
                        },
                    )
            return HookResult()

    manager = HookManager(search_dirs=[])
    manager.add_hook(OnceHook(), events=[HookEvent.STOP])

    result, history = await run_agent(
        agent=agent,
        message="Test message",
        message_history=[],
        limiter=LLMLimiter(),
        hook_manager=manager,
    )

    # Should return ORIGINAL response (replace_response=False)
    assert result == "Original AI response"
    assert call_count == 2  # Original + extended session


@pytest.mark.asyncio
async def test_run_agent_stop_replace_response_true():
    """Test STOP hook with replace_response=True returns extended response."""
    agent = MagicMock()

    # Original response from LLM
    mock_original_result = MagicMock()
    mock_original_result.output = "Original AI response"
    mock_original_result.all_messages.return_value = []

    # Extended session response (should BE returned)
    mock_transformed_result = MagicMock()
    mock_transformed_result.output = "Transformed response"
    mock_transformed_result.all_messages.return_value = []

    call_count = 0

    async def _gen(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield AgentRunResultEvent(result=mock_original_result)
        else:
            yield AgentRunResultEvent(result=mock_transformed_result)

    agent.run = _run_from(_gen)

    # Stateful hook that only fires once (prevents infinite loop)
    class OnceHook:
        def __init__(self):
            self.fired = False

        async def __call__(self, context: HookContext) -> HookResult:
            if context.event == HookEvent.STOP:
                if not self.fired:
                    self.fired = True
                    return HookResult(
                        success=True,
                        modifications={
                            "systemMessage": "Summarize the above.",
                            "replaceResponse": True,
                        },
                    )
            return HookResult()

    manager = HookManager(search_dirs=[])
    manager.add_hook(OnceHook(), events=[HookEvent.STOP])

    result, history = await run_agent(
        agent=agent,
        message="Test message",
        message_history=[],
        limiter=LLMLimiter(),
        hook_manager=manager,
    )

    # Should return TRANSFORMED response (replace_response=True)
    assert result == "Transformed response"
    assert call_count == 2


@pytest.mark.asyncio
async def test_run_agent_stop_block_continues_turn():
    """A STOP hook returning decision=block re-runs the agent with the reason
    injected; the continued response is returned."""
    agent = MagicMock()
    first = MagicMock()
    first.output = "first answer"
    first.all_messages.return_value = []
    second = MagicMock()
    second.output = "continued answer"
    second.all_messages.return_value = []

    call_count = 0

    async def _gen(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        yield AgentRunResultEvent(result=first if call_count == 1 else second)

    agent.run = _run_from(_gen)

    class BlockOnce:
        def __init__(self):
            self.fired = False

        async def __call__(self, context: HookContext) -> HookResult:
            if context.event == HookEvent.STOP and not self.fired:
                self.fired = True
                return HookResult(
                    success=False,
                    should_stop=True,
                    modifications={"decision": "block", "reason": "keep going"},
                )
            return HookResult()

    manager = HookManager(search_dirs=[])
    manager.add_hook(BlockOnce(), events=[HookEvent.STOP])

    result, history = await run_agent(
        agent=agent,
        message="hi",
        message_history=[],
        limiter=LLMLimiter(),
        hook_manager=manager,
    )

    assert result == "continued answer"
    assert call_count == 2


@pytest.mark.asyncio
async def test_run_agent_stop_block_cap_prevents_infinite_loop():
    """A STOP hook that always blocks is overridden after the block cap so the
    agent cannot loop forever."""
    from zrb.llm.agent.run.session_extension import STOP_HOOK_BLOCK_CAP

    agent = MagicMock()

    call_count = 0

    async def _gen(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        result.output = f"turn {call_count}"
        result.all_messages.return_value = []
        yield AgentRunResultEvent(result=result)

    agent.run = _run_from(_gen)

    async def always_block(context: HookContext) -> HookResult:
        if context.event == HookEvent.STOP:
            return HookResult(
                success=False,
                should_stop=True,
                modifications={"decision": "block", "reason": "more"},
            )
        return HookResult()

    manager = HookManager(search_dirs=[])
    manager.add_hook(always_block, events=[HookEvent.STOP])

    result, history = await run_agent(
        agent=agent,
        message="hi",
        message_history=[],
        limiter=LLMLimiter(),
        hook_manager=manager,
    )

    # First turn + STOP_HOOK_BLOCK_CAP continuations, then the cap forces a stop.
    assert call_count == STOP_HOOK_BLOCK_CAP + 1
