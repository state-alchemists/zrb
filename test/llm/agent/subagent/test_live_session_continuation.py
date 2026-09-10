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
    entry = registry.add_session("sess1", "a", "ghost", sub_agent_manager, buffered_ui)

    with patch(
        "zrb.llm.agent.subagent.live_session.steer_into_live_run",
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
    entry = registry.add_session(
        "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )

    with (
        patch(
            "zrb.llm.agent.subagent.live_session.steer_into_live_run",
            return_value=False,
        ),
        patch(
            "zrb.llm.agent.subagent.live_session.run_agent",
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
    entry = registry.add_session(
        "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )

    async def fake_run_agent(**kwargs):
        return "ok", [{"turn": 1}]

    with (
        patch(
            "zrb.llm.agent.subagent.live_session.steer_into_live_run",
            return_value=False,
        ),
        patch(
            "zrb.llm.agent.subagent.live_session.run_agent", side_effect=fake_run_agent
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
    entry = registry.add_session(
        "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )

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
    registry, buffered_ui, sub_agent_manager
):
    """A normal continuation of a sub-agent that finished (not cancelled)
    must not push anything: the main agent already received its delegation
    result."""
    entry = registry.add_session(
        "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )

    async def fake_run_agent(**kwargs):
        return "reply", [_response_with_text("normal reply")]

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
    entry = registry.add_session(
        "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )
    entry.pending_queue = ["queued"]
    assert registry.cancel("sess1", "a") is True  # first cancel: sticky notify flag

    started = asyncio.Event()

    async def blocking_run_agent(**kwargs):
        started.set()
        await asyncio.Event().wait()

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
    entry = registry.add_session(
        "sess1", "a", "researcher", sub_agent_manager, buffered_ui
    )
    entry.pending_queue = ["queued"]
    assert registry.cancel("sess1", "a") is True

    async def fake_run_agent(**kwargs):
        return "reply", [_request_without_reply()]

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
        await entry.active_task

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
