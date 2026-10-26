from unittest.mock import AsyncMock, MagicMock, patch

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


def _single_turn_agent(output="ok"):
    """A mock agent whose stream yields one result and then ends."""
    agent = MagicMock()
    result = MagicMock()
    result.output = output
    result.all_messages.return_value = []

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=result)

    agent.run = _run_from(_gen)
    return agent


@pytest.mark.asyncio
async def test_session_start_source_startup_vs_resume():
    """SESSION_START reports source=startup for a fresh history and resume for a
    populated one, so Claude-style startup/resume matchers work."""
    captured: list[str | None] = []

    async def rec(context: HookContext) -> HookResult:
        if context.event == HookEvent.SESSION_START:
            captured.append(context.source)
        return HookResult()

    manager = HookManager(search_dirs=[])
    manager.add_hook(rec, events=[HookEvent.SESSION_START])

    await run_agent(
        agent=_single_turn_agent(),
        message="hi",
        message_history=[],
        limiter=LLMLimiter(),
        hook_manager=manager,
    )
    await run_agent(
        agent=_single_turn_agent(),
        message="again",
        message_history=["prior turn"],
        limiter=LLMLimiter(),
        hook_manager=manager,
    )

    assert captured == ["startup", "resume"]


@pytest.mark.asyncio
async def test_user_prompt_submit_populates_prompt_field():
    """UserPromptSubmit must populate context.prompt so matchers (mapped to the
    `prompt` field) and the CLAUDE_PROMPT env var see the submitted text."""
    captured: dict = {}

    async def rec(context: HookContext) -> HookResult:
        if context.event == HookEvent.USER_PROMPT_SUBMIT:
            captured["prompt"] = context.prompt
        return HookResult()

    manager = HookManager(search_dirs=[])
    manager.add_hook(rec, events=[HookEvent.USER_PROMPT_SUBMIT])

    await run_agent(
        agent=_single_turn_agent(),
        message="hello world",
        message_history=[],
        limiter=LLMLimiter(),
        hook_manager=manager,
    )

    assert captured.get("prompt") == "hello world"


@pytest.mark.asyncio
async def test_pre_compact_trigger_and_additional_context():
    """PRE_COMPACT fires with trigger=auto and its additionalContext is injected
    ahead of summarization."""
    captured: dict = {}

    async def rec(context: HookContext) -> HookResult:
        if context.event == HookEvent.PRE_COMPACT:
            captured["trigger"] = context.trigger
            return HookResult(
                success=True, modifications={"additionalContext": "keep the steps"}
            )
        return HookResult()

    manager = HookManager(search_dirs=[])
    manager.add_hook(rec, events=[HookEvent.PRE_COMPACT])

    await run_agent(
        agent=_single_turn_agent(),
        message="hi",
        message_history=[],
        limiter=LLMLimiter(),
        hook_manager=manager,
    )

    assert captured.get("trigger") == "auto"


@pytest.mark.asyncio
async def test_pre_compact_prompt_is_what_the_user_typed():
    """The flush quotes this value, so it is the typed message and not
    `prompt_content`: a fallback model may have described an attachment in there,
    and a generated description is not the user's words."""
    captured: dict = {}

    async def rec(context: HookContext) -> HookResult:
        if context.event == HookEvent.PRE_COMPACT:
            captured["prompt"] = context.event_data.get("prompt")
        return HookResult()

    manager = HookManager(search_dirs=[])
    manager.add_hook(rec, events=[HookEvent.PRE_COMPACT])

    await run_agent(
        agent=_single_turn_agent(),
        message="look at this papaya",
        message_history=[],
        limiter=LLMLimiter(),
        hook_manager=manager,
    )

    assert captured.get("prompt") == "look at this papaya"


@pytest.mark.asyncio
async def test_a_precompact_hook_s_context_does_not_hide_a_dropped_message():
    """The POST_COMPACT counts start after a PreCompact hook's own context has joined the
    history. Counting from before it lets one message out and one in look like nothing
    happened, which is the case this pins."""
    agent = MagicMock()
    agent.model = "deepseek:deepseek-flash"
    mock_result = MagicMock()
    mock_result.output = "Result"
    mock_result.all_messages.return_value = []

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    limiter = MagicMock(spec=LLMLimiter)
    limiter.max_token_per_request = 100
    limiter.get_effective_context_window.return_value = 100
    limiter.acquire = AsyncMock()
    # The same total before and after, so the token count alone cannot show the drop.
    limiter.count_tokens.side_effect = lambda value: 80
    limiter.fit_context_window.side_effect = lambda history, *a, **k: history[1:]

    captured: dict = {}

    async def rec(context: HookContext) -> HookResult:
        if context.event == HookEvent.PRE_COMPACT:
            return HookResult(success=True, modifications={"additionalContext": "ctx"})
        if context.event == HookEvent.POST_COMPACT:
            captured.update(context.event_data)
        return HookResult()

    manager = HookManager(search_dirs=[])
    manager.add_hook(rec, events=[HookEvent.PRE_COMPACT, HookEvent.POST_COMPACT])

    with (
        patch.object(agent, "run") as mock_run,
        patch(
            "zrb.llm.agent.run.runner.ensure_alternating_roles", side_effect=lambda x: x
        ),
    ):
        mock_run.side_effect = _run_from(_gen)
        await run_agent(
            agent=agent,
            message="Hi",
            message_history=[MagicMock() for _ in range(3)],
            limiter=limiter,
            hook_manager=manager,
        )

    assert captured["before_message_count"] == 4, "three came in and the hook added one"
    assert captured["message_count"] == 3, "the fit dropped one"
    assert captured["compacted"] is True


@pytest.mark.asyncio
async def test_the_ninety_percent_fit_is_reported_as_a_compaction():
    """`_acquire_rate_limit` trims to 90% of the window, and it used to do that *after* the
    event, so a history that fit the window but not the margin was dropped with no day line.
    The fit runs before the event now, and the counts are the ones that survive it."""
    agent = MagicMock()
    agent.model = "deepseek:deepseek-flash"
    mock_result = MagicMock()
    mock_result.output = "Result"
    mock_result.all_messages.return_value = []

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    limiter = MagicMock(spec=LLMLimiter)
    limiter.max_token_per_request = 100
    limiter.get_effective_context_window.return_value = 100  # 90% of it is 90
    limiter.acquire = AsyncMock()
    # 95 fits the window, so no force-prune; it does not fit the 90% margin, so the fit trims.
    limiter.count_tokens.side_effect = lambda value: (
        95 if isinstance(value, list) and len(value) == 3 else 40
    )
    limiter.fit_context_window.side_effect = lambda history, *a, **k: history[1:]

    captured: dict = {}

    async def rec(context: HookContext) -> HookResult:
        if context.event == HookEvent.POST_COMPACT:
            captured.update(context.event_data)
        return HookResult()

    manager = HookManager(search_dirs=[])
    manager.add_hook(rec, events=[HookEvent.POST_COMPACT])

    with (
        patch.object(agent, "run") as mock_run,
        patch(
            "zrb.llm.agent.run.runner.ensure_alternating_roles", side_effect=lambda x: x
        ),
    ):
        mock_run.side_effect = _run_from(_gen)
        await run_agent(
            agent=agent,
            message="Hi",
            message_history=[MagicMock() for _ in range(3)],
            limiter=limiter,
            hook_manager=manager,
        )

    assert len(captured["history"]) == 2, "the event reports what the fit left"
    assert captured["message_count"] == 2
    assert captured["token_count"] == 40
    assert captured["before_message_count"] == 3
    assert captured["compacted"] is True


@pytest.mark.asyncio
async def test_a_force_prune_is_reported_as_a_compaction():
    """The prune is the last resort and the largest replacement there is. It runs
    before the event now, so the event reports the history that is actually left and
    a hook recording compactions is told that this one happened."""
    agent = MagicMock()
    agent.model = "deepseek:deepseek-flash"
    mock_result = MagicMock()
    mock_result.output = "Result"
    mock_result.all_messages.return_value = []

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    limiter = MagicMock(spec=LLMLimiter)
    limiter.max_token_per_request = 100
    limiter.get_effective_context_window.return_value = 100  # small enough to force it
    limiter.acquire = AsyncMock()
    limiter.fit_context_window.side_effect = lambda h, m, r, *a, **k: h
    limiter.count_tokens.side_effect = lambda value: 200 if isinstance(value, list) else 50

    captured: dict = {}

    async def rec(context: HookContext) -> HookResult:
        if context.event == HookEvent.POST_COMPACT:
            captured.update(context.event_data)
        return HookResult()

    manager = HookManager(search_dirs=[])
    manager.add_hook(rec, events=[HookEvent.POST_COMPACT])

    with (
        patch.object(agent, "run") as mock_run,
        patch(
            "zrb.llm.agent.run.runner.ensure_alternating_roles", side_effect=lambda x: x
        ),
    ):
        mock_run.side_effect = _run_from(_gen)
        await run_agent(
            agent=agent,
            message="Hi",
            message_history=[MagicMock() for _ in range(3)],
            limiter=limiter,
            hook_manager=manager,
        )

    assert captured["compacted"] is True
    assert captured["before_message_count"] == 3
    assert captured["message_count"] == 1, "what survived the prune is what is reported"


@pytest.mark.asyncio
async def test_post_compact_fires_after_processing():
    """POST_COMPACT fires (mirror of PreCompact) with trigger=auto once history
    processing has run."""
    captured: dict = {}

    async def rec(context: HookContext) -> HookResult:
        if context.event == HookEvent.POST_COMPACT:
            captured["trigger"] = context.trigger
            captured["fired"] = True
        return HookResult()

    manager = HookManager(search_dirs=[])
    manager.add_hook(rec, events=[HookEvent.POST_COMPACT])

    await run_agent(
        agent=_single_turn_agent(),
        message="hi",
        message_history=[],
        limiter=LLMLimiter(),
        hook_manager=manager,
    )

    assert captured.get("fired") is True
    assert captured.get("trigger") == "auto"


@pytest.mark.asyncio
async def test_run_agent_user_prompt_submit_block_ends_turn():
    """A UserPromptSubmit hook that blocks ends the turn before the model runs;
    the reason is surfaced as the output."""
    agent = MagicMock()
    agent.run = MagicMock(
        side_effect=AssertionError("model must not run when prompt is blocked")
    )

    async def blocking_hook(context: HookContext) -> HookResult:
        if context.event == HookEvent.USER_PROMPT_SUBMIT:
            return HookResult.block("policy violation")
        return HookResult()

    manager = HookManager(search_dirs=[])
    manager.add_hook(blocking_hook, events=[HookEvent.USER_PROMPT_SUBMIT])

    result, history = await run_agent(
        agent=agent,
        message="do something",
        message_history=[],
        limiter=LLMLimiter(),
        hook_manager=manager,
    )

    assert result == "policy violation"


@pytest.mark.asyncio
async def test_run_agent_session_start_context_prepending():
    from pydantic_ai.messages import ModelRequest, SystemPromptPart

    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "Result"
    mock_result.all_messages.return_value = []

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    agent.run = _run_from(_gen)

    manager = HookManager(search_dirs=[])

    async def session_start_hook(ctx):
        return HookResult(
            success=True, modifications={"additionalContext": "INIT_CONTEXT"}
        )

    manager.add_hook(session_start_hook, events=[HookEvent.SESSION_START])

    limiter = MagicMock(spec=LLMLimiter)
    limiter.count_tokens.return_value = 10
    limiter.max_token_per_request = 1000
    limiter.get_effective_context_window.return_value = 1000
    limiter.fit_context_window.side_effect = lambda h, m, r, *args, **kwargs: h
    limiter.acquire = AsyncMock()

    with patch.object(agent, "run") as mock_run:
        mock_run.side_effect = _run_from(_gen)

        result, _ = await run_agent(
            agent=agent,
            message="Hi",
            message_history=[],
            limiter=limiter,
            hook_manager=manager,
        )

        # Check history passed to agent.run
        passed_history = mock_run.call_args[1]["message_history"]
        assert len(passed_history) == 1
        assert isinstance(passed_history[0], ModelRequest)
        assert isinstance(passed_history[0].parts[0], SystemPromptPart)
        assert passed_history[0].parts[0].content == "INIT_CONTEXT"


@pytest.mark.asyncio
async def test_run_agent_user_prompt_context_prepending():
    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "Result"
    mock_result.all_messages.return_value = []

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    agent.run = _run_from(_gen)

    manager = HookManager(search_dirs=[])

    async def prompt_hook(ctx):
        return HookResult(
            success=True, modifications={"additionalContext": "PROMPT_CONTEXT"}
        )

    manager.add_hook(prompt_hook, events=[HookEvent.USER_PROMPT_SUBMIT])

    limiter = MagicMock(spec=LLMLimiter)
    limiter.count_tokens.return_value = 10
    limiter.max_token_per_request = 1000
    limiter.get_effective_context_window.return_value = 1000
    limiter.fit_context_window.side_effect = lambda h, m, r, *args, **kwargs: h
    limiter.acquire = AsyncMock()

    with patch.object(agent, "run") as mock_run:
        mock_run.side_effect = _run_from(_gen)

        result, _ = await run_agent(
            agent=agent,
            message="Hi",
            message_history=[],
            limiter=limiter,
            hook_manager=manager,
        )

        # Check message passed to agent.run
        passed_message = mock_run.call_args[0][0]
        assert "PROMPT_CONTEXT" in passed_message
        assert "Hi" in passed_message

