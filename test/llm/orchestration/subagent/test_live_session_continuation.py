"""A live continuation's own turn: its mechanics and captured authority."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.orchestration.subagent.live_session import LiveSubAgentSessionRegistry


@pytest.fixture
def registry():
    return LiveSubAgentSessionRegistry()


@pytest.fixture
def buffered_ui():
    ui = MagicMock()
    ui.input = ui.tools = ui
    ui.parent_ui.input = ui.parent_ui
    ui.parent_ui.tools = ui.parent_ui
    ui.active_run_context = None
    return ui


@pytest.fixture
def sub_agent_manager():
    manager = MagicMock()
    manager.create_agent.return_value = MagicMock()
    return manager


def _add_idle_session(registry, session_id, agent_id, agent_name, manager, ui):
    """Register a session whose original delegation has already finished.

    `add_session` claims the original turn as running — that is what keeps a
    human message from starting a second concurrent turn — so a continuation
    test must first put the session in the idle state `mark_turn_finished`
    leaves behind.
    """
    entry = registry.add_session(session_id, agent_id, agent_name, manager, ui)
    registry.mark_turn_finished(session_id, agent_id, [])
    return entry


@pytest.mark.asyncio
async def test_continue_live_session_skips_message_when_agent_no_longer_resolves(
    registry, buffered_ui, sub_agent_manager
):
    """The definition disappeared mid-session -- drop that message rather
    than loop forever on it, but keep draining the rest of the queue."""
    sub_agent_manager.create_agent.return_value = None
    entry = _add_idle_session(
        registry, "sess1", "a", "ghost", sub_agent_manager, buffered_ui
    )

    with patch(
        "zrb.llm.orchestration.subagent.live_session.steer_into_live_run",
        return_value=False,
    ):
        await registry.send_message("sess1", "a", "hello")
        await entry.active_task

    assert entry.state == "idle"
    assert entry.pending_queue == []


@pytest.mark.asyncio
async def test_continue_live_session_swallows_run_agent_exception(
    registry, buffered_ui, sub_agent_manager
):
    """A failed continuation turn must not crash the drain loop or leave the
    session stuck in "running" forever."""
    entry = _add_idle_session(
        registry, "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )

    with (
        patch(
            "zrb.llm.orchestration.subagent.live_session.steer_into_live_run",
            return_value=False,
        ),
        patch(
            "zrb.llm.contracts.shared.subagent_turn.run_agent",
            side_effect=RuntimeError("boom"),
        ),
    ):
        await registry.send_message("sess1", "a", "hello")
        await entry.active_task  # must not raise

    assert entry.state == "idle"


@pytest.mark.asyncio
async def test_continue_live_session_marks_done_after_drain(
    registry, buffered_ui, sub_agent_manager
):
    """A session that ends marks its end in the live view: the transcript the
    user is watching shows a trailing <Done>, so a finished sub-agent is
    unambiguous even while viewing it."""
    entry = _add_idle_session(
        registry, "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )

    async def fake_run_agent(**kwargs):
        return "ok", [{"turn": 1}]

    with (
        patch(
            "zrb.llm.orchestration.subagent.live_session.steer_into_live_run",
            return_value=False,
        ),
        patch(
            "zrb.llm.contracts.shared.subagent_turn.run_agent",
            side_effect=fake_run_agent,
        ),
    ):
        await registry.send_message("sess1", "a", "hello")
        await entry.active_task

    assert entry.state == "idle"
    buffered_ui.append_to_output.assert_any_call("<Done>")


@pytest.mark.asyncio
async def test_continue_live_session_skips_done_when_human_cancelled(
    registry, buffered_ui, sub_agent_manager
):
    """A human-cancelled session must NOT show <Done>: the TUI already wrote
    <Esc> Canceled via cancel_viewed_agent, and a <Done> on top would
    contradict it."""
    entry = _add_idle_session(
        registry, "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )

    started = asyncio.Event()

    async def blocking_run_agent(**kwargs):
        started.set()
        await asyncio.Event().wait()  # never finishes on its own

    with (
        patch(
            "zrb.llm.orchestration.subagent.live_session.steer_into_live_run",
            return_value=False,
        ),
        patch(
            "zrb.llm.contracts.shared.subagent_turn.run_agent",
            side_effect=blocking_run_agent,
        ),
    ):
        await registry.send_message("sess1", "a", "keep going")
        await started.wait()
        task = entry.active_task

        assert registry.cancel("sess1", "a") is True
        with pytest.raises(asyncio.CancelledError):
            await task

    calls = [c.args[0] for c in buffered_ui.append_to_output.call_args_list]
    assert "<Done>" not in calls


@pytest.mark.asyncio
async def test_a_continuation_runs_as_a_nested_sub_agent_turn(
    registry, buffered_ui, sub_agent_manager
):
    """Continued from a key handler, where no run is bound, the turn is still
    a sub-agent's: marked nested, so the parent's self-review covers it."""
    entry = _add_idle_session(
        registry, "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )
    seen: list = []

    async def fake_run_agent(**kwargs):
        seen.append(kwargs)
        return "ok", []

    with (
        patch(
            "zrb.llm.orchestration.subagent.live_session.steer_into_live_run",
            return_value=False,
        ),
        patch(
            "zrb.llm.contracts.shared.subagent_turn.run_agent",
            side_effect=fake_run_agent,
        ),
    ):
        await registry.send_message("sess1", "a", "hello")
        await entry.active_task

    assert seen[0]["nested"] is True


@pytest.mark.asyncio
async def test_a_continuation_carries_the_parent_runs_hook_manager(
    registry, buffered_ui, sub_agent_manager
):
    """The continuation is started from a key handler, long after the parent's
    scope exited, so the hook manager travels with the rest of the captured
    authority — otherwise the turn fires on the program-wide singleton."""
    from zrb.llm.capabilities.hook.manager import HookManager
    from zrb.llm.contracts.shared.agent_state import current_hook_manager
    from zrb.util.contextvar_scope import scoped

    parent_manager = HookManager(search_dirs=[])
    with scoped(current_hook_manager, parent_manager):
        entry = _add_idle_session(
            registry, "sess1", "a", "researcher", sub_agent_manager, buffered_ui
        )
    seen: list = []

    async def fake_run_agent(**kwargs):
        seen.append(kwargs)
        return "ok", []

    with (
        patch(
            "zrb.llm.orchestration.subagent.live_session.steer_into_live_run",
            return_value=False,
        ),
        patch(
            "zrb.llm.contracts.shared.subagent_turn.run_agent",
            side_effect=fake_run_agent,
        ),
    ):
        await registry.send_message("sess1", "a", "hello")
        await entry.active_task

    assert seen[0]["hook_manager"] is parent_manager


@pytest.mark.asyncio
async def test_a_continuation_carries_the_parent_runs_approval_handler(
    registry, buffered_ui, sub_agent_manager
):
    """A continuation runs outside the parent's run, so the tool policies and
    approval channel its first turn inherited must travel with the captured
    authority — otherwise its tool calls skip the parent's policies."""
    from zrb.llm.capabilities.tool_call import ToolCallHandler
    from zrb.llm.contracts.shared.agent_state import (
        current_approval_channel,
        current_tool_confirmation,
    )
    from zrb.util.contextvar_scope import scoped

    handler = ToolCallHandler()
    channel = object()
    with (
        scoped(current_tool_confirmation, handler),
        scoped(current_approval_channel, channel),
    ):
        entry = _add_idle_session(
            registry, "sess1", "a", "researcher", sub_agent_manager, buffered_ui
        )
    seen: list = []

    async def fake_run_agent(**kwargs):
        seen.append(kwargs)
        return "ok", []

    with (
        patch(
            "zrb.llm.orchestration.subagent.live_session.steer_into_live_run",
            return_value=False,
        ),
        patch(
            "zrb.llm.contracts.shared.subagent_turn.run_agent",
            side_effect=fake_run_agent,
        ),
    ):
        await registry.send_message("sess1", "a", "hello")
        await entry.active_task

    assert seen[0]["tool_confirmation"] is handler
    assert seen[0]["approval_channel"] is channel


@pytest.mark.asyncio
async def test_a_continuation_does_not_pick_up_an_ambient_approval_handler(
    registry, buffered_ui, sub_agent_manager
):
    """A delegation captured with no approval handler keeps none: `run_agent`
    reads a `None` argument as "inherit", so the captured value is bound."""
    from zrb.llm.capabilities.tool_call import ToolCallHandler
    from zrb.llm.contracts.shared.agent_state import (
        current_approval_channel,
        current_tool_confirmation,
    )
    from zrb.util.contextvar_scope import scoped

    entry = _add_idle_session(
        registry, "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )
    seen: list = []

    async def fake_run_agent(**kwargs):
        seen.append((current_tool_confirmation.get(), current_approval_channel.get()))
        return "ok", []

    with (
        scoped(current_tool_confirmation, ToolCallHandler()),
        scoped(current_approval_channel, object()),
        patch(
            "zrb.llm.orchestration.subagent.live_session.steer_into_live_run",
            return_value=False,
        ),
        patch(
            "zrb.llm.contracts.shared.subagent_turn.run_agent",
            side_effect=fake_run_agent,
        ),
    ):
        await registry.send_message("sess1", "a", "hello")
        await entry.active_task

    assert seen == [(None, None)]
