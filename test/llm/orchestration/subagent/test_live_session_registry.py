"""Tests for the "talk to a running sub-agent directly" live-session registry."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.orchestration.subagent.live_session import LiveSubAgentSessionRegistry
from zrb.llm.presentation.ui.fallback.std_ui import StdUI


@pytest.fixture
def registry():
    return LiveSubAgentSessionRegistry()


@pytest.fixture
def buffered_ui():
    ui = MagicMock()
    ui.input = ui.tools = ui
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
    # The original delegation owns the session's turn from registration on.
    assert entry.state == "running"
    assert entry.history == []
    assert entry.pending_queue == []
    assert entry.notify_parent_on_end is False


def test_restored_session_stays_idle(registry, buffered_ui, sub_agent_manager):
    """A session rebuilt from a saved transcript has no turn in flight."""
    entry = registry.restore_session(
        "sess1", "agent-1", "researcher", sub_agent_manager, buffered_ui, []
    )
    assert entry.state == "idle"
    assert entry.active_task is None


def test_get_unknown_returns_none(registry):
    assert registry.get("sess1", "no-such-agent") is None


def test_get_parent_ui_hands_back_a_ui_that_takes_a_message(
    registry, buffered_ui, sub_agent_manager
):
    """A parent that declares an input side is the one the sub-agent messages."""
    parent = StdUI()
    buffered_ui.parent_ui = parent
    registry.add_session(
        "sess1", "agent-1", "researcher", sub_agent_manager, buffered_ui
    )
    assert registry.get_parent_ui("sess1", "agent-1") is parent


def test_get_parent_ui_refuses_a_parent_with_no_input_side(
    registry, buffered_ui, sub_agent_manager
):
    """A parent that cannot take a message is reported absent.

    The sender then answers with the documented refusal instead of failing on a
    missing attribute, which is why the check asks what the parent can do
    rather than which class built it.
    """
    buffered_ui.parent_ui = object()
    registry.add_session(
        "sess1", "agent-1", "researcher", sub_agent_manager, buffered_ui
    )
    assert registry.get_parent_ui("sess1", "agent-1") is None


def test_get_parent_ui_refuses_when_no_session_is_tracked(registry):
    assert registry.get_parent_ui("sess1", "no-such-agent") is None


def test_active_scopes_by_session_id(registry, buffered_ui, sub_agent_manager):
    """A process hosting multiple sessions must not bleed one session's
    live sub-agents into another's picker listing."""
    registry.add_session("sess1", "a", "researcher", sub_agent_manager, buffered_ui)
    registry.add_session("sess2", "b", "reviewer", sub_agent_manager, buffered_ui)

    assert [e.agent_id for e in registry.active("sess1")] == ["a"]
    assert [e.agent_id for e in registry.active("sess2")] == ["b"]
    assert registry.active("sess3") == []


@pytest.mark.asyncio
async def test_mark_turn_finished_updates_history_clears_owner_and_goes_idle(
    registry, buffered_ui, sub_agent_manager
):
    entry = registry.add_session(
        "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )
    entry.active_task = asyncio.current_task()  # the original delegation's turn

    registry.mark_turn_finished("sess1", "a", ["fake", "history"])

    assert entry.history == ["fake", "history"]
    assert entry.active_task is None
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
        "zrb.llm.orchestration.subagent.live_session.steer_into_live_run",
        return_value=True,
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
    registry.mark_turn_finished("sess1", "a", [])  # the original turn finished
    entry.history = [{"turn": 1}]

    async def fake_run_agent(**kwargs):
        return "reply", [{"turn": 1}, {"turn": 2}]

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
    """A second message arriving while the session is still owned by a turn
    must just queue -- not spawn a second, concurrent continuation."""
    entry = registry.add_session(
        "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )

    with patch(
        "zrb.llm.orchestration.subagent.live_session.steer_into_live_run",
        return_value=False,
    ):
        result = await registry.send_message("sess1", "a", "and another thing")

    assert result is True
    assert entry.pending_queue == ["and another thing"]


@pytest.mark.asyncio
async def test_message_during_the_original_turns_gap_does_not_start_a_turn(
    registry, buffered_ui, sub_agent_manager
):
    """A delegation whose run is between rounds (approval, a rate-limit wait)
    has no active run context to steer into. The session still belongs to that
    turn, so a human message queues; it must not start a second, concurrent
    continuation while the original turn is still running."""
    entry = registry.add_session(
        "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )
    entry.active_task = asyncio.current_task()  # the original delegation's turn

    with patch(
        "zrb.llm.orchestration.subagent.live_session.steer_into_live_run",
        return_value=False,
    ):
        await registry.send_message("sess1", "a", "first")
        await registry.send_message("sess1", "a", "second")

    assert entry.state == "running"
    assert entry.active_task is asyncio.current_task()
    assert entry.pending_queue == ["first", "second"]


@pytest.mark.asyncio
async def test_mark_turn_finished_drains_messages_queued_during_the_turn(
    registry, buffered_ui, sub_agent_manager
):
    """Messages that arrived between the finished turn's rounds are delivered
    as one continuation instead of being stranded in the queue."""
    entry = registry.add_session(
        "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )
    entry.active_task = asyncio.current_task()  # the original delegation's turn
    with patch(
        "zrb.llm.orchestration.subagent.live_session.steer_into_live_run",
        return_value=False,
    ):
        await registry.send_message("sess1", "a", "first")
        await registry.send_message("sess1", "a", "second")

    # The original turn still owns the session: no continuation was spawned.
    assert entry.active_task is asyncio.current_task()

    seen: list = []

    async def fake_run_agent(**kwargs):
        seen.append(kwargs["message"])
        return "ok", kwargs["message_history"] + [kwargs["message"]]

    with patch(
        "zrb.llm.contracts.shared.subagent_turn.run_agent",
        side_effect=fake_run_agent,
    ):
        registry.mark_turn_finished("sess1", "a", [])
        task = entry.active_task
        assert task is not None and task is not asyncio.current_task()
        await task

    assert seen == ["first", "second"]
    assert entry.state == "idle"
    assert entry.pending_queue == []


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
    registry.mark_turn_finished("sess1", "a", [])  # the original turn finished
    entry.pending_queue = ["keep going"]

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
        assert task is not None and not task.done()

        assert registry.cancel("sess1", "a") is True
        with pytest.raises(asyncio.CancelledError):
            await task

    assert entry.active_task is None
    assert entry.state == "idle"
