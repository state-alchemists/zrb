"""Continuation dispatch: a queued message becomes a sub-agent turn."""

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
    ui.active_run_context = None
    return ui


@pytest.fixture
def sub_agent_manager():
    manager = MagicMock()
    manager.create_agent.return_value = MagicMock()
    return manager


@pytest.mark.asyncio
async def test_continue_live_session_drains_multiple_queued_messages(
    registry, buffered_ui, sub_agent_manager
):
    entry = registry.add_session(
        "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )
    registry.mark_turn_finished("sess1", "a", [])  # the original turn finished

    calls = []

    async def fake_run_agent(**kwargs):
        calls.append(kwargs["message"])
        return "ok", kwargs["message_history"] + [kwargs["message"]]

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
    registry.mark_turn_finished("sess1", "a", [])  # the original turn finished

    scopes = []

    async def fake_run_agent(**kwargs):
        scopes.append(kwargs["run_scope"])
        return "ok", kwargs["message_history"] + [kwargs["message"]]

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
    from zrb.llm.capabilities.permission.policy import PermissionPolicy, Rule
    from zrb.llm.capabilities.permission.state import permission_policy
    from zrb.llm.engine.agent.run.runner import current_yolo
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
        registry.mark_turn_finished("sess1", "a", [])  # the original turn finished

    assert entry.authority is not None
    assert entry.authority.permission_policy is narrow_policy
    assert entry.authority.yolo is False

    captured_kwargs = {}

    async def fake_run_agent(**kwargs):
        captured_kwargs.update(kwargs)
        return "ok", kwargs["message_history"] + [kwargs["message"]]

    with (
        patch(
            "zrb.llm.orchestration.subagent.live_session.steer_into_live_run",
            return_value=False,
        ),
        patch(
            "zrb.llm.contracts.shared.subagent_turn.run_agent",
            side_effect=fake_run_agent,
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
    registry.mark_turn_finished("sess1", "a", [])  # the original turn finished

    async def fake_run_agent(**kwargs):
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
        patch(
            "zrb.llm.orchestration.subagent.live_session.agent_activity_registry"
        ) as mock_registry,
    ):
        await registry.send_message("sess1", "a", "hello")
        await entry.active_task

    mock_registry.start.assert_called_once_with(
        "a", "researcher", task="hello", session_id="sess1"
    )
    mock_registry.finish.assert_called_once_with("a", session_id="sess1")
