"""Tests for the "talk to a running sub-agent directly" live-session registry."""

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


def _response_with_text(text: str):
    from types import SimpleNamespace

    return SimpleNamespace(
        kind="response",
        parts=[SimpleNamespace(part_kind="text", content=text)],
    )


def _request_without_reply():
    from types import SimpleNamespace

    return SimpleNamespace(kind="request", parts=[])


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
async def test_cancelled_then_continued_session_reports_back_to_main_agent(
    registry, buffered_ui, sub_agent_manager
):
    """A session the user cancelled (Esc) and then kept chatting with must hand
    its latest response back to the main agent when it ends naturally — the main
    agent only ever heard "Cancelled by user" from that delegation."""
    entry = _add_idle_session(
        registry, "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )
    entry.pending_queue = ["queued"]
    assert registry.cancel("sess1", "a") is True
    assert entry.notify_parent_on_end is True

    reply = _response_with_text("the final answer")

    async def fake_run_agent(**kwargs):
        return "reply", [reply]

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
        await registry.send_message("sess1", "a", "keep going")
        for _ in range(10):
            await asyncio.sleep(0)
        assert entry.state == "idle"

    # The main agent receives only the continuation's latest response — no
    # wrapper, no transcript pointer.
    buffered_ui.parent_ui.submit_message.assert_called_once_with(
        "the final answer", None
    )


@pytest.mark.asyncio
async def test_never_cancelled_session_does_not_report_back(
    registry, buffered_ui, sub_agent_manager
):
    """A normal continuation of a sub-agent that finished (not cancelled)
    must not push anything: the main agent already received its delegation
    result."""
    entry = _add_idle_session(
        registry, "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )

    async def fake_run_agent(**kwargs):
        return "reply", [_response_with_text("normal reply")]

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
    buffered_ui.parent_ui.submit_message.assert_not_called()


@pytest.mark.asyncio
async def test_second_cancel_suppresses_report_back(
    registry, buffered_ui, sub_agent_manager
):
    """A continuation cut short by another Esc must not report: the user's
    latest word on this sub-agent was cancel, so the main agent should not be
    told it finished."""
    entry = _add_idle_session(
        registry, "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )
    entry.pending_queue = ["queued"]
    assert registry.cancel("sess1", "a") is True  # first cancel: sticky notify flag

    started = asyncio.Event()

    async def blocking_run_agent(**kwargs):
        started.set()
        await asyncio.Event().wait()

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

        assert registry.cancel("sess1", "a") is True  # second cancel cuts it short

        with pytest.raises(asyncio.CancelledError):
            await task

    buffered_ui.parent_ui.submit_message.assert_not_called()


@pytest.mark.asyncio
async def test_report_back_skipped_when_history_has_no_reply(
    registry, buffered_ui, sub_agent_manager
):
    """A continued session whose history contains no assistant text (tool-only
    or failed turns) has nothing to report."""
    entry = _add_idle_session(
        registry, "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )
    entry.pending_queue = ["queued"]
    assert registry.cancel("sess1", "a") is True

    async def fake_run_agent(**kwargs):
        return "reply", [_request_without_reply()]

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
        await registry.send_message("sess1", "a", "keep going")
        await entry.active_task

    buffered_ui.parent_ui.submit_message.assert_not_called()


@pytest.mark.asyncio
async def test_report_back_skipped_when_parent_cannot_deliver(
    registry, buffered_ui, sub_agent_manager
):
    """A parent UI without the submit_message channel (e.g. StdUI-backed) means
    the report has nowhere to go — the drain must still finish cleanly."""
    entry = _add_idle_session(
        registry, "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )
    entry.pending_queue = ["queued"]
    assert registry.cancel("sess1", "a") is True
    buffered_ui.parent_ui = MagicMock(spec=["no_submit_message_channel"])

    async def fake_run_agent(**kwargs):
        return "reply", [_response_with_text("orphaned reply")]

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
        await registry.send_message("sess1", "a", "keep going")
        for _ in range(10):
            await asyncio.sleep(0)
        assert entry.state == "idle"


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


@pytest.mark.asyncio
async def test_cancelled_turn_cannot_reset_the_replacement_turn(
    registry, buffered_ui, sub_agent_manager
):
    """After Esc, a replacement continuation may start before the cancelled
    turn handles its CancelledError. That cancelled turn must not idle the
    replacement (which would let a third turn run concurrently) or append a
    stale <Done>/report for a run the human already cancelled."""
    entry = _add_idle_session(
        registry, "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )
    first_started = asyncio.Event()
    second_started = asyncio.Event()

    async def fake_run_agent(**kwargs):
        if kwargs["message"] == "first":
            first_started.set()
        else:
            second_started.set()
        await asyncio.Event().wait()  # neither turn finishes on its own

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
        await registry.send_message("sess1", "a", "first")
        await first_started.wait()
        first_task = entry.active_task
        assert first_task is not None

        assert registry.cancel("sess1", "a") is True
        # The replacement starts before the cancelled turn has yielded.
        await registry.send_message("sess1", "a", "second")
        second_task = entry.active_task
        assert second_task is not None and second_task is not first_task
        await second_started.wait()
        # Let the cancelled turn run its `finally`.
        for _ in range(5):
            await asyncio.sleep(0)

        assert first_task.done()
        assert entry.state == "running"
        assert entry.active_task is second_task
        assert "<Done>" not in [
            call.args[0] for call in buffered_ui.append_to_output.call_args_list
        ]
        buffered_ui.parent_ui.submit_message.assert_not_called()

        # A third message queues behind the replacement instead of starting a
        # third concurrent turn.
        await registry.send_message("sess1", "a", "third")
        assert entry.pending_queue == ["third"]
        assert entry.active_task is second_task

        assert registry.cancel("sess1", "a") is True
        with pytest.raises(asyncio.CancelledError):
            await second_task
