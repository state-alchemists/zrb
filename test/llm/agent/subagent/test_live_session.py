"""Tests for the "talk to a running sub-agent directly" live-session registry."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.agent.subagent.live_session import (
    LiveSubAgentSessionRegistry,
    _continue_live_session,
)


@pytest.fixture
def registry():
    return LiveSubAgentSessionRegistry()


@pytest.fixture
def buffered_ui():
    ui = MagicMock()
    ui.active_run_context = None
    return ui


@pytest.fixture
def sub_agent_manager():
    manager = MagicMock()
    manager.create_agent.return_value = MagicMock()
    return manager


def test_register_and_get_round_trip(registry, buffered_ui, sub_agent_manager):
    entry = registry.add_session(
        "sess1", "agent-1", "researcher", sub_agent_manager, buffered_ui
    )
    assert registry.get("sess1", "agent-1") is entry
    assert entry.agent_name == "researcher"
    assert entry.state == "idle"
    assert entry.history == []
    assert entry.pending_queue == []
    assert entry.notify_parent_on_end is False


def test_get_unknown_returns_none(registry):
    assert registry.get("sess1", "no-such-agent") is None


def test_active_scopes_by_session_id(registry, buffered_ui, sub_agent_manager):
    """A process hosting multiple sessions must not bleed one session's
    live sub-agents into another's picker listing."""
    registry.add_session("sess1", "a", "researcher", sub_agent_manager, buffered_ui)
    registry.add_session("sess2", "b", "reviewer", sub_agent_manager, buffered_ui)

    assert [e.agent_id for e in registry.active("sess1")] == ["a"]
    assert [e.agent_id for e in registry.active("sess2")] == ["b"]
    assert registry.active("sess3") == []


def test_mark_turn_finished_updates_history_and_goes_idle(
    registry, buffered_ui, sub_agent_manager
):
    entry = registry.add_session(
        "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )
    entry.state = "running"

    registry.mark_turn_finished("sess1", "a", ["fake", "history"])

    assert entry.history == ["fake", "history"]
    assert entry.state == "idle"


def test_mark_turn_finished_unknown_entry_is_noop(registry):
    registry.mark_turn_finished("sess1", "no-such-agent", ["x"])  # must not raise


def test_clear_one_session_leaves_others_intact(
    registry, buffered_ui, sub_agent_manager
):
    registry.add_session("sess1", "a", "researcher", sub_agent_manager, buffered_ui)
    registry.add_session("sess2", "b", "reviewer", sub_agent_manager, buffered_ui)

    registry.clear(session_id="sess1")

    assert registry.active("sess1") == []
    assert [e.agent_id for e in registry.active("sess2")] == ["b"]


def test_clear_without_session_id_clears_every_session(
    registry, buffered_ui, sub_agent_manager
):
    registry.add_session("sess1", "a", "researcher", sub_agent_manager, buffered_ui)
    registry.add_session("sess2", "b", "reviewer", sub_agent_manager, buffered_ui)

    registry.clear()

    assert registry.active("sess1") == []
    assert registry.active("sess2") == []


# ── send_message ──


@pytest.mark.asyncio
async def test_send_message_unknown_session_returns_false(registry):
    assert await registry.send_message("sess1", "no-such-agent", "hi") is False


@pytest.mark.asyncio
async def test_send_message_injects_live_when_turn_is_in_flight(
    registry, buffered_ui, sub_agent_manager
):
    """The sub-agent's turn is still running: the message must be injected
    via steer_into_live_run (ADR-0078's mid-turn mechanism), not queued."""
    entry = registry.add_session(
        "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )
    entry.state = "running"
    buffered_ui.active_run_context = MagicMock()  # a "live" run context

    with patch(
        "zrb.llm.agent.subagent.live_session.steer_into_live_run", return_value=True
    ) as mock_steer:
        result = await registry.send_message("sess1", "a", "focus on pricing")

    assert result is True
    mock_steer.assert_called_once_with(
        buffered_ui.active_run_context, "focus on pricing", []
    )
    assert entry.pending_queue == []  # delivered live, never queued


@pytest.mark.asyncio
async def test_send_message_queues_and_starts_continuation_when_idle(
    registry, buffered_ui, sub_agent_manager
):
    """The sub-agent has already finished: no live run to inject into, so the
    message queues and (since idle) a continuation starts immediately."""
    entry = registry.add_session(
        "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )
    entry.history = [{"turn": 1}]

    async def fake_run_agent(**kwargs):
        return "reply", [{"turn": 1}, {"turn": 2}]

    with (
        patch(
            "zrb.llm.agent.subagent.live_session.steer_into_live_run",
            return_value=False,
        ),
        patch(
            "zrb.llm.agent.subagent.live_session.run_agent",
            side_effect=fake_run_agent,
        ),
    ):
        result = await registry.send_message("sess1", "a", "keep going")
        assert result is True
        assert entry.state == "running"  # claimed synchronously before spawn
        # Let the spawned continuation task actually run.
        for _ in range(5):
            await asyncio.sleep(0)

    assert entry.history == [{"turn": 1}, {"turn": 2}]
    assert entry.state == "idle"
    assert entry.pending_queue == []


@pytest.mark.asyncio
async def test_send_message_queues_without_double_spawning_when_already_running(
    registry, buffered_ui, sub_agent_manager
):
    """A second message arriving while a continuation is already draining
    must just queue -- not spawn a second, concurrent continuation."""
    entry = registry.add_session(
        "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )
    entry.state = "running"  # a continuation is already in flight

    with patch(
        "zrb.llm.agent.subagent.live_session.steer_into_live_run", return_value=False
    ):
        result = await registry.send_message("sess1", "a", "and another thing")

    assert result is True
    assert entry.pending_queue == ["and another thing"]


# ── cancel ──


def test_cancel_unknown_session_returns_false(registry):
    assert registry.cancel("sess1", "no-such-agent") is False


def test_cancel_drops_queue_and_cancels_in_flight_task(
    registry, buffered_ui, sub_agent_manager
):
    """Esc while viewing a running sub-agent must drop its queued messages and
    cancel its run task (flagging it so the delegate task can tell a
    human-initiated cancel apart from the main run's own cancellation)."""
    entry = registry.add_session(
        "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )
    entry.pending_queue = ["queued 1", "queued 2"]
    task = MagicMock()
    task.done.return_value = False
    entry.active_task = task
    entry.state = "running"

    assert registry.cancel("sess1", "a") is True

    assert entry.pending_queue == []
    task.cancel.assert_called_once()
    assert entry.cancelled_by_human is True
    assert entry.notify_parent_on_end is True
    assert entry.active_task is None
    assert entry.state == "idle"


def test_cancel_with_only_queued_messages_reports_work(
    registry, buffered_ui, sub_agent_manager
):
    """Queued-but-unsent messages count as work to cancel even with no task."""
    entry = registry.add_session(
        "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )
    entry.pending_queue = ["queued"]
    entry.state = "running"

    assert registry.cancel("sess1", "a") is True
    assert entry.pending_queue == []
    assert entry.state == "idle"


def test_cancel_with_nothing_in_flight_returns_false(
    registry, buffered_ui, sub_agent_manager
):
    entry = registry.add_session(
        "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )
    entry.state = "idle"

    assert registry.cancel("sess1", "a") is False
    assert entry.state == "idle"
    assert entry.notify_parent_on_end is False


def test_cancel_does_not_cancel_a_finished_task(
    registry, buffered_ui, sub_agent_manager
):
    entry = registry.add_session(
        "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )
    task = MagicMock()
    task.done.return_value = True
    entry.active_task = task
    entry.state = "running"

    assert registry.cancel("sess1", "a") is False
    task.cancel.assert_not_called()


@pytest.mark.asyncio
async def test_cancel_stops_a_running_continuation(
    registry, buffered_ui, sub_agent_manager
):
    """Cancel during a live continuation stops the sub-agent's turn: the
    spawned task ends cancelled and the session goes idle."""
    entry = registry.add_session(
        "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )
    entry.pending_queue = ["keep going"]

    started = asyncio.Event()

    async def blocking_run_agent(**kwargs):
        started.set()
        await asyncio.Event().wait()  # never finishes on its own

    with (
        patch(
            "zrb.llm.agent.subagent.live_session.steer_into_live_run",
            return_value=False,
        ),
        patch(
            "zrb.llm.agent.subagent.live_session.run_agent",
            side_effect=blocking_run_agent,
        ),
    ):
        await registry.send_message("sess1", "a", "keep going")
        await started.wait()
        task = entry.active_task
        assert task is not None and not task.done()

        assert registry.cancel("sess1", "a") is True
        with pytest.raises(asyncio.CancelledError):
            await task

    assert entry.active_task is None
    assert entry.state == "idle"


# ── _continue_live_session ──


@pytest.mark.asyncio
async def test_continue_live_session_drains_multiple_queued_messages(
    buffered_ui, sub_agent_manager
):
    from zrb.llm.agent.subagent.live_session import LiveSubAgentSession

    entry = LiveSubAgentSession(
        agent_id="a",
        agent_name="researcher",
        session_id="sess1",
        sub_agent_manager=sub_agent_manager,
        buffered_ui=buffered_ui,
        history=[],
        pending_queue=["first", "second"],
        state="running",
    )

    calls = []

    async def fake_run_agent(**kwargs):
        calls.append(kwargs["message"])
        return "ok", kwargs["message_history"] + [kwargs["message"]]

    with patch(
        "zrb.llm.agent.subagent.live_session.run_agent", side_effect=fake_run_agent
    ):
        await _continue_live_session(entry)

    assert calls == ["first", "second"]
    assert entry.history == ["first", "second"]
    assert entry.state == "idle"


@pytest.mark.asyncio
async def test_continue_live_session_reuses_entrys_run_scope_across_turns(
    buffered_ui, sub_agent_manager
):
    """Each drained message is a separate run_agent() call, but they're all
    turns of the SAME sub-agent conversation — file_observation.py's
    read-before-overwrite tracking must see them as one run_scope, not a
    fresh one per turn (which would make it forget files read in an earlier
    turn of this same continuation)."""
    from zrb.llm.agent.subagent.live_session import LiveSubAgentSession

    entry = LiveSubAgentSession(
        agent_id="a",
        agent_name="researcher",
        session_id="sess1",
        sub_agent_manager=sub_agent_manager,
        buffered_ui=buffered_ui,
        history=[],
        pending_queue=["first", "second"],
        state="running",
    )

    scopes = []

    async def fake_run_agent(**kwargs):
        scopes.append(kwargs["run_scope"])
        return "ok", kwargs["message_history"] + [kwargs["message"]]

    with patch(
        "zrb.llm.agent.subagent.live_session.run_agent", side_effect=fake_run_agent
    ):
        await _continue_live_session(entry)

    assert scopes == [entry.run_scope, entry.run_scope]
    assert entry.run_scope != ""


@pytest.mark.asyncio
async def test_continue_live_session_reflects_in_activity_registry(
    buffered_ui, sub_agent_manager
):
    """A continuation is a sub-agent running -- it must show in the compact
    main-view activity line the same as the original turn did."""
    from zrb.llm.agent.subagent.live_session import LiveSubAgentSession

    entry = LiveSubAgentSession(
        agent_id="a",
        agent_name="researcher",
        session_id="sess1",
        sub_agent_manager=sub_agent_manager,
        buffered_ui=buffered_ui,
        pending_queue=["hello"],
        state="running",
    )

    async def fake_run_agent(**kwargs):
        return "ok", []

    with (
        patch(
            "zrb.llm.agent.subagent.live_session.run_agent", side_effect=fake_run_agent
        ),
        patch(
            "zrb.llm.agent.subagent.live_session.agent_activity_registry"
        ) as mock_registry,
    ):
        await _continue_live_session(entry)

    mock_registry.start.assert_called_once_with(
        "a", "researcher", task="hello", session_id="sess1"
    )
    mock_registry.finish.assert_called_once_with("a", session_id="sess1")


@pytest.mark.asyncio
async def test_continue_live_session_skips_message_when_agent_no_longer_resolves(
    buffered_ui,
):
    """The definition disappeared mid-session -- drop that message rather
    than loop forever on it, but keep draining the rest of the queue."""
    from zrb.llm.agent.subagent.live_session import LiveSubAgentSession

    manager = MagicMock()
    manager.create_agent.return_value = None
    entry = LiveSubAgentSession(
        agent_id="a",
        agent_name="ghost",
        session_id="sess1",
        sub_agent_manager=manager,
        buffered_ui=buffered_ui,
        pending_queue=["hello"],
        state="running",
    )

    await _continue_live_session(entry)

    assert entry.state == "idle"
    assert entry.pending_queue == []


@pytest.mark.asyncio
async def test_continue_live_session_swallows_run_agent_exception(
    buffered_ui, sub_agent_manager
):
    """A failed continuation turn must not crash the drain loop or leave the
    session stuck in "running" forever."""
    from zrb.llm.agent.subagent.live_session import LiveSubAgentSession

    entry = LiveSubAgentSession(
        agent_id="a",
        agent_name="researcher",
        session_id="sess1",
        sub_agent_manager=sub_agent_manager,
        buffered_ui=buffered_ui,
        pending_queue=["hello"],
        state="running",
    )

    with patch(
        "zrb.llm.agent.subagent.live_session.run_agent",
        side_effect=RuntimeError("boom"),
    ):
        await _continue_live_session(entry)  # must not raise

    assert entry.state == "idle"


@pytest.mark.asyncio
async def test_continue_live_session_marks_done_after_drain(
    buffered_ui, sub_agent_manager
):
    """A session that ends marks its end in the live view: the transcript the
    user is watching shows a trailing <Done>, so a finished sub-agent is
    unambiguous even while viewing it."""
    from zrb.llm.agent.subagent.live_session import LiveSubAgentSession

    entry = LiveSubAgentSession(
        agent_id="a",
        agent_name="researcher",
        session_id="sess1",
        sub_agent_manager=sub_agent_manager,
        buffered_ui=buffered_ui,
        pending_queue=["hello"],
        state="running",
    )

    async def fake_run_agent(**kwargs):
        return "ok", [{"turn": 1}]

    with patch(
        "zrb.llm.agent.subagent.live_session.run_agent", side_effect=fake_run_agent
    ):
        await _continue_live_session(entry)

    assert entry.state == "idle"
    buffered_ui.append_to_output.assert_any_call("<Done>")


@pytest.mark.asyncio
async def test_continue_live_session_skips_done_when_human_cancelled(
    buffered_ui, sub_agent_manager
):
    """A human-cancelled session must NOT show <Done>: the TUI already wrote
    <Esc> Canceled via cancel_viewed_agent, and a <Done> on top would
    contradict it."""
    from zrb.llm.agent.subagent.live_session import LiveSubAgentSession

    entry = LiveSubAgentSession(
        agent_id="a",
        agent_name="researcher",
        session_id="sess1",
        sub_agent_manager=sub_agent_manager,
        buffered_ui=buffered_ui,
        pending_queue=["hello"],
        state="running",
        cancelled_by_human=True,
    )

    async def fake_run_agent(**kwargs):
        return "ok", [{"turn": 1}]

    with patch(
        "zrb.llm.agent.subagent.live_session.run_agent", side_effect=fake_run_agent
    ):
        await _continue_live_session(entry)

    calls = [c.args[0] for c in buffered_ui.append_to_output.call_args_list]
    assert "<Done>" not in calls


# ── cancelled-then-continued report-back ──


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
async def test_cancelled_then_continued_session_reports_back_to_main_agent(
    registry, buffered_ui, sub_agent_manager
):
    """A session the user cancelled (Esc) and then kept chatting with must hand
    its latest response back to the main agent when it ends naturally — the main
    agent only ever heard "Cancelled by user" from that delegation."""
    entry = registry.add_session(
        "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )
    entry.pending_queue = ["queued"]
    assert registry.cancel("sess1", "a") is True
    assert entry.notify_parent_on_end is True

    reply = _response_with_text("the final answer")

    async def fake_run_agent(**kwargs):
        return "reply", [reply]

    with (
        patch(
            "zrb.llm.agent.subagent.live_session.steer_into_live_run",
            return_value=False,
        ),
        patch(
            "zrb.llm.agent.subagent.live_session.run_agent",
            side_effect=fake_run_agent,
        ),
    ):
        await registry.send_message("sess1", "a", "keep going")
        for _ in range(10):
            await asyncio.sleep(0)
        assert entry.state == "idle"

    # The main agent receives only the continuation's latest response — no
    # wrapper, no transcript pointer.
    buffered_ui.parent_ui.submit_message.assert_called_once_with("the final answer")


@pytest.mark.asyncio
async def test_never_cancelled_session_does_not_report_back(
    buffered_ui, sub_agent_manager
):
    """A normal continuation of a sub-agent that finished (not cancelled)
    must not push anything: the main agent already received its delegation
    result."""
    from zrb.llm.agent.subagent.live_session import LiveSubAgentSession

    entry = LiveSubAgentSession(
        agent_id="a",
        agent_name="researcher",
        session_id="sess1",
        sub_agent_manager=sub_agent_manager,
        buffered_ui=buffered_ui,
        pending_queue=["hello"],
        state="running",
        notify_parent_on_end=False,
    )

    async def fake_run_agent(**kwargs):
        return "reply", [_response_with_text("normal reply")]

    with patch(
        "zrb.llm.agent.subagent.live_session.run_agent",
        side_effect=fake_run_agent,
    ):
        await _continue_live_session(entry)

    assert entry.state == "idle"
    buffered_ui.parent_ui.submit_message.assert_not_called()


@pytest.mark.asyncio
async def test_second_cancel_suppresses_report_back(buffered_ui, sub_agent_manager):
    """A continuation cut short by another Esc must not report: the user's
    latest word on this sub-agent was cancel, so the main agent should not be
    told it finished."""
    from zrb.llm.agent.subagent.live_session import LiveSubAgentSession

    entry = LiveSubAgentSession(
        agent_id="a",
        agent_name="researcher",
        session_id="sess1",
        sub_agent_manager=sub_agent_manager,
        buffered_ui=buffered_ui,
        pending_queue=["hello"],
        state="running",
        cancelled_by_human=True,
        notify_parent_on_end=True,
    )

    async def fake_run_agent(**kwargs):
        return "reply", [_response_with_text("partial reply")]

    with patch(
        "zrb.llm.agent.subagent.live_session.run_agent",
        side_effect=fake_run_agent,
    ):
        await _continue_live_session(entry)

    buffered_ui.parent_ui.submit_message.assert_not_called()


@pytest.mark.asyncio
async def test_report_back_skipped_when_history_has_no_reply(
    buffered_ui, sub_agent_manager
):
    """A continued session whose history contains no assistant text (tool-only
    or failed turns) has nothing to report."""
    from zrb.llm.agent.subagent.live_session import LiveSubAgentSession

    entry = LiveSubAgentSession(
        agent_id="a",
        agent_name="researcher",
        session_id="sess1",
        sub_agent_manager=sub_agent_manager,
        buffered_ui=buffered_ui,
        pending_queue=["hello"],
        state="running",
        notify_parent_on_end=True,
    )

    async def fake_run_agent(**kwargs):
        return "reply", [_request_without_reply()]

    with patch(
        "zrb.llm.agent.subagent.live_session.run_agent",
        side_effect=fake_run_agent,
    ):
        await _continue_live_session(entry)

    buffered_ui.parent_ui.submit_message.assert_not_called()


@pytest.mark.asyncio
async def test_report_back_skipped_when_parent_cannot_deliver(
    registry, buffered_ui, sub_agent_manager
):
    """A parent UI without the submit_message channel (e.g. StdUI-backed) means
    the report has nowhere to go — the drain must still finish cleanly."""
    entry = registry.add_session(
        "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )
    entry.pending_queue = ["queued"]
    assert registry.cancel("sess1", "a") is True
    buffered_ui.parent_ui = MagicMock(spec=["no_submit_message_channel"])

    async def fake_run_agent(**kwargs):
        return "reply", [_response_with_text("orphaned reply")]

    with (
        patch(
            "zrb.llm.agent.subagent.live_session.steer_into_live_run",
            return_value=False,
        ),
        patch(
            "zrb.llm.agent.subagent.live_session.run_agent",
            side_effect=fake_run_agent,
        ),
    ):
        await registry.send_message("sess1", "a", "keep going")
        for _ in range(10):
            await asyncio.sleep(0)
        assert entry.state == "idle"
