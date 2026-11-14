"""The one addition a turn's fit has not seen: a `PostCompact` hook's own context."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import AgentRunResultEvent
from pydantic_ai.messages import SystemPromptPart

from zrb.llm.agent.run.runner import run_agent
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.hook.contracts.interface import HookCallable, HookContext, HookResult
from zrb.llm.hook.contracts.types import HookEvent
from zrb.llm.hook.manager import HookManager


def _run_from(agen_func):
    """Wrap an async generator into an ``agent.run(event_stream_handler=...)`` mock."""

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


def _agent_with_one_result() -> MagicMock:
    """A mock agent whose stream yields one result and then ends."""
    agent = MagicMock()
    agent.model = "deepseek:deepseek-flash"
    result = MagicMock()
    result.output = "Result"
    result.all_messages.return_value = []

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=result)

    agent.run = _run_from(_gen)
    return agent


def _limiter_fitting_twice() -> MagicMock:
    """A limiter whose first fit keeps the history and whose second one drops turns."""
    limiter = MagicMock(spec=LLMLimiter)
    limiter.max_token_per_request = 1000
    limiter.get_effective_context_window.return_value = 1000
    limiter.count_tokens.return_value = 10
    limiter.acquire = AsyncMock()
    limiter.fit_context_window.side_effect = [list(range(3)), [0]]
    return limiter


async def _turn(agent: MagicMock, limiter: MagicMock, hook: HookCallable) -> None:
    """Run one turn of three messages through *hook*'s POST_COMPACT event."""
    manager = HookManager(search_dirs=[])
    manager.add_hook(hook, events=[HookEvent.POST_COMPACT])
    with patch(
        "zrb.llm.agent.run.runner.ensure_alternating_roles", side_effect=lambda x: x
    ):
        await run_agent(
            agent=agent,
            message="Hi",
            message_history=[MagicMock() for _ in range(3)],
            limiter=limiter,
            hook_manager=manager,
        )


@pytest.mark.asyncio
async def test_a_post_compact_hook_s_context_is_fitted_into_the_window():
    """The fit runs before the hooks, so their context is the one part no fit has seen.

    Sent as-is it can put the request over the window, which a provider refuses
    rather than trims, so the trim runs once more after it has joined.
    """

    async def post_compact(context: HookContext) -> HookResult:
        return HookResult(success=True, modifications={"additionalContext": "ctx"})

    limiter = _limiter_fitting_twice()
    await _turn(_agent_with_one_result(), limiter, post_compact)

    assert limiter.fit_context_window.call_count == 2
    second_history = limiter.fit_context_window.call_args_list[1].args[0]
    assert len(second_history) == 4, "the hook's context joined before the second fit"
    assert isinstance(second_history[0].parts[0], SystemPromptPart)


@pytest.mark.asyncio
async def test_a_turn_with_no_hook_context_fits_once():
    """No hook answered, so there is nothing the fit has not already seen."""

    async def silent(context: HookContext) -> HookResult:
        return HookResult()

    limiter = _limiter_fitting_twice()
    await _turn(_agent_with_one_result(), limiter, silent)

    assert limiter.fit_context_window.call_count == 1
