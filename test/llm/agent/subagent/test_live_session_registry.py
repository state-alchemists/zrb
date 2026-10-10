"""Tests for the "talk to a running sub-agent directly" live-session registry."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.agent.subagent.live_session import LiveSubAgentSessionRegistry


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


@pytest.mark.asyncio
async def test_continue_live_session_drains_multiple_queued_messages(
    registry, buffered_ui, sub_agent_manager
):
    entry = registry.add_session(
        "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )

    calls = []

    async def fake_run_agent(**kwargs):
        calls.append(kwargs["message"])
        return "ok", kwargs["message_history"] + [kwargs["message"]]

    with (
        patch(
            "zrb.llm.agent.subagent.live_session.steer_into_live_run",
            return_value=False,
        ),
        patch(
            "zrb.llm.agent.subagent.live_session.run_agent", side_effect=fake_run_agent
        ),
    ):
        await registry.send_message("sess1", "a", "first")
        task = entry.active_task
        # Second message arrives before the spawned task has had a chance to
        # run (no `await` yet) — it must queue behind the first, not spawn a
        # second continuation.
        await registry.send_message("sess1", "a", "second")
        await task

    assert calls == ["first", "second"]
    assert entry.history == ["first", "second"]
    assert entry.state == "idle"


@pytest.mark.asyncio
async def test_continue_live_session_reuses_entrys_run_scope_across_turns(
    registry, buffered_ui, sub_agent_manager
):
    """Each drained message is a separate run_agent() call, but they're all
    turns of the SAME sub-agent conversation — file_observation.py's
    read-before-overwrite tracking must see them as one run_scope, not a
    fresh one per turn (which would make it forget files read in an earlier
    turn of this same continuation)."""
    entry = registry.add_session(
        "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )

    scopes = []

    async def fake_run_agent(**kwargs):
        scopes.append(kwargs["run_scope"])
        return "ok", kwargs["message_history"] + [kwargs["message"]]

    with (
        patch(
            "zrb.llm.agent.subagent.live_session.steer_into_live_run",
            return_value=False,
        ),
        patch(
            "zrb.llm.agent.subagent.live_session.run_agent", side_effect=fake_run_agent
        ),
    ):
        await registry.send_message("sess1", "a", "first")
        task = entry.active_task
        await registry.send_message("sess1", "a", "second")
        await task

    assert scopes == [entry.run_scope, entry.run_scope]
    assert entry.run_scope != ""


@pytest.mark.asyncio
async def test_continue_live_session_uses_captured_authority_not_ambient(
    registry, buffered_ui, sub_agent_manager
):
    """A continuation must rebind the ORIGINAL delegation's authority, not
    whatever happens to be ambient whenever the continuation later runs.
    `live_session.py` is the one `asyncio.ensure_future` spawn site where
    ambient inheritance alone would be wrong (ADR-0069's "spawn inside the
    still-bound scope" invariant does not hold here — see
    `authority_snapshot.py`)."""
    from zrb.llm.agent.run.runner import current_yolo
    from zrb.llm.permission.policy import PermissionPolicy, Rule
    from zrb.llm.permission.state import permission_policy
    from zrb.util.contextvar_scope import scoped

    narrow_policy = PermissionPolicy(rules=(Rule("*", "deny"),))
    broad_policy = PermissionPolicy(rules=(Rule("*", "allow"),))

    # The original delegation's own bound scope, still active when the
    # session is created (mirrors run_agent_task calling add_session
    # synchronously inside the parent's own run_agent() call).
    with permission_policy(narrow_policy), scoped(current_yolo, False):
        entry = registry.add_session(
            "sess1", "a", "researcher", sub_agent_manager, buffered_ui
        )

    assert entry.authority is not None
    assert entry.authority.permission_policy is narrow_policy
    assert entry.authority.yolo is False

    captured_kwargs = {}

    async def fake_run_agent(**kwargs):
        captured_kwargs.update(kwargs)
        return "ok", kwargs["message_history"] + [kwargs["message"]]

    with (
        patch(
            "zrb.llm.agent.subagent.live_session.steer_into_live_run",
            return_value=False,
        ),
        patch(
            "zrb.llm.agent.subagent.live_session.run_agent", side_effect=fake_run_agent
        ),
        # Ambient state at continuation time is broader than what the
        # delegation was granted — must not leak into the continuation.
        permission_policy(broad_policy),
        scoped(current_yolo, True),
    ):
        await registry.send_message("sess1", "a", "keep going")
        task = entry.active_task
        if task is not None:
            await task

    assert captured_kwargs["permission_policy"] is narrow_policy
    assert captured_kwargs["yolo"] is False
    assert captured_kwargs["sandbox_policy"] is not None
    assert captured_kwargs["sandbox_policy"].enabled is False


@pytest.mark.asyncio
async def test_continue_live_session_reflects_in_activity_registry(
    registry, buffered_ui, sub_agent_manager
):
    """A continuation is a sub-agent running -- it must show in the compact
    main-view activity line the same as the original turn did."""
    entry = registry.add_session(
        "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )

    async def fake_run_agent(**kwargs):
        return "ok", []

    with (
        patch(
            "zrb.llm.agent.subagent.live_session.steer_into_live_run",
            return_value=False,
        ),
        patch(
            "zrb.llm.agent.subagent.live_session.run_agent", side_effect=fake_run_agent
        ),
        patch(
            "zrb.llm.agent.subagent.live_session.agent_activity_registry"
        ) as mock_registry,
    ):
        await registry.send_message("sess1", "a", "hello")
        await entry.active_task

    mock_registry.start.assert_called_once_with(
        "a", "researcher", task="hello", session_id="sess1"
    )
    mock_registry.finish.assert_called_once_with("a", session_id="sess1")
