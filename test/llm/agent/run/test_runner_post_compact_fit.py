"""The one addition a turn's fit has not seen: a `PostCompact` hook's own context."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import AgentRunResultEvent
from pydantic_ai.messages import SystemPromptPart

from zrb.llm.agent.run.runner import run_agent
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.hook.contracts.interface import HookCallable, HookContext, HookResult
from zrb.llm.hook.contracts.types import HookEvent
from zrb.llm.hook.manager import HookManager

CONTEXT = "ctx"


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


def _agent_handed_a_history() -> MagicMock:
    """A mock agent that yields one result and records the history it was sent."""
    agent = MagicMock()
    agent.model = "deepseek:deepseek-flash"
    agent.sent = []
    result = MagicMock()
    result.output = "Result"
    result.all_messages.return_value = []

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=result)

    run = _run_from(_gen)

    async def recording_run(*args, **kwargs):
        agent.sent.append(kwargs.get("message_history"))
        return await run(*args, **kwargs)

    agent.run = recording_run
    return agent


def _limiter(fit) -> MagicMock:
    """A limiter whose ``fit_context_window`` is *fit*; everything else is constant."""
    limiter = MagicMock(spec=LLMLimiter)
    limiter.max_token_per_request = 1000
    limiter.get_effective_context_window.return_value = 1000
    limiter.count_tokens.return_value = 10
    limiter.count_content_tokens.return_value = 10
    limiter.acquire = AsyncMock()
    limiter.fit_context_window.side_effect = fit
    return limiter


async def _turn(
    agent,
    limiter,
    hook: HookCallable,
    history: "list[Any] | None" = None,
    print_fn=print,
) -> None:
    """Run one turn through *hook*'s POST_COMPACT event."""
    if history is None:
        history = [MagicMock() for _ in range(3)]
    manager = HookManager(search_dirs=[])
    manager.add_hook(hook, events=[HookEvent.POST_COMPACT])
    with patch(
        "zrb.llm.agent.run.runner.ensure_alternating_roles", side_effect=lambda x: x
    ):
        await run_agent(
            agent=agent,
            message="Hi",
            message_history=history,
            limiter=limiter,
            hook_manager=manager,
            print_fn=print_fn,
        )


def _answers_with_context() -> HookCallable:
    async def post_compact(context: HookContext) -> HookResult:
        return HookResult(success=True, modifications={"additionalContext": CONTEXT})

    return post_compact


@pytest.mark.asyncio
async def test_the_context_is_fitted_around_and_prepended_after():
    """The trim takes whole turns off the front, so the context cannot be in that list.

    Its cost is reserved while the history is fitted, and the context joins the
    request only afterwards, where no trim can reach it.
    """

    def fit(history, new_message, reserved_tokens=0, model=None):
        return list(history)

    limiter = _limiter(fit)
    agent = _agent_handed_a_history()
    await _turn(agent, limiter, _answers_with_context())

    second = limiter.fit_context_window.call_args_list[1]
    assert len(second.args[0]) == 3, "the fit is handed the history, not the context"
    assert second.args[2] == 10, "the context's own tokens are reserved"
    sent = agent.sent[0]
    assert len(sent) == 4
    assert isinstance(sent[0].parts[0], SystemPromptPart)
    assert sent[0].parts[0].content == CONTEXT


@pytest.mark.asyncio
async def test_a_trim_cannot_drop_the_hook_s_context():
    """The first finding: the context was the first message, so the trim took it first."""

    def fit(history, new_message, reserved_tokens=0, model=None):
        return list(history) if reserved_tokens == 0 else list(history[-1:])

    limiter = _limiter(fit)
    agent = _agent_handed_a_history()
    await _turn(agent, limiter, _answers_with_context())

    sent = agent.sent[0]
    assert len(sent) == 2, "the history was trimmed to its newest turn, and no further"
    assert isinstance(sent[0].parts[0], SystemPromptPart)
    assert sent[0].parts[0].content == CONTEXT


@pytest.mark.asyncio
async def test_a_first_turn_still_sends_the_hook_s_context():
    """The second finding: with no history, an empty fit is not a verdict on the context.

    `fit_context_window` returns an empty history unchanged, so answering "does
    the context fit" with that answer drops what a hook injected on every first
    turn.
    """

    def fit(history, new_message, reserved_tokens=0, model=None):
        return list(history)

    limiter = _limiter(fit)
    agent = _agent_handed_a_history()
    await _turn(agent, limiter, _answers_with_context(), history=[])

    sent = agent.sent[0]
    assert len(sent) == 1
    assert isinstance(sent[0].parts[0], SystemPromptPart)
    assert sent[0].parts[0].content == CONTEXT


@pytest.mark.asyncio
async def test_the_context_is_charged_to_pacing_even_beside_a_usage_anchor():
    """`count_tokens` prefers an anchor, and that request never carried this context."""

    def fit(history, new_message, reserved_tokens=0, model=None):
        return list(history)

    limiter = _limiter(fit)
    limiter.count_content_tokens.return_value = 100
    agent = _agent_handed_a_history()
    await _turn(agent, limiter, _answers_with_context())

    estimated = limiter.acquire.call_args.kwargs["estimated_tokens"]
    assert estimated == 10 + 100 + 10, "history, hook context, and the message"


@pytest.mark.asyncio
async def test_a_context_too_large_to_send_is_dropped_and_said_out_loud():
    """Sending it is a provider error every turn; losing it silently is worse."""

    def fit(history, new_message, reserved_tokens=0, model=None):
        # Reserving the context's cost leaves no room, and the probe says the
        # context does not fit on its own either.
        if reserved_tokens:
            return []
        if len(history) == 1 and isinstance(history[0].parts[0], SystemPromptPart):
            return []
        return list(history[-1:])

    printed: list[str] = []
    limiter = _limiter(fit)
    agent = _agent_handed_a_history()
    await _turn(agent, limiter, _answers_with_context(), print_fn=printed.append)

    sent = agent.sent[0]
    assert len(sent) == 1, "only the newest turn survives"
    assert not any(isinstance(part, SystemPromptPart) for part in sent[0].parts)
    assert any("POST_COMPACT hook context dropped" in line for line in printed)


@pytest.mark.asyncio
async def test_a_turn_with_no_hook_context_fits_once():
    """No hook answered, so there is nothing the fit has not already seen."""

    async def silent(context: HookContext) -> HookResult:
        return HookResult()

    limiter = _limiter(lambda history, new_message, reserved_tokens=0, model=None: [])
    await _turn(_agent_handed_a_history(), limiter, silent)

    assert limiter.fit_context_window.call_count == 1
