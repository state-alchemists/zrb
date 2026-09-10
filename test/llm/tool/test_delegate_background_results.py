"""Tests for background subagent delegation."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.agent.subagent.manager import SubAgentManager
from zrb.llm.tool.delegate import AgentTaskResult
from zrb.llm.tool.delegate_background import (
    background_delegation_live_context,
    create_background_delegate_tool,
    create_get_delegation_result_tool,
    get_background_registry,
    get_own_background_handles,
)


@pytest.fixture
def manager():
    return MagicMock(spec=SubAgentManager)


@pytest.fixture(autouse=True)
def clean_registry():
    yield
    get_background_registry().cancel_all()


@pytest.mark.asyncio
async def test_get_result_wait_times_out_still_running(manager):
    release = asyncio.Event()

    async def gated(*args, **kwargs):
        await release.wait()
        return AgentTaskResult("agent", "x", None)

    delegate = create_background_delegate_tool(manager)
    get_result = create_get_delegation_result_tool()
    with (
        patch("zrb.llm.tool.delegate_background.run_agent_task", side_effect=gated),
        patch(
            "zrb.llm.tool.delegate_background.get_current_ui", return_value=MagicMock()
        ),
    ):
        msg = await delegate("agent", "deliver", "do it", [])
        handle = msg.split("Handle:")[1].split(".")[0].strip()
        result = await get_result(handle, wait=0.1)
        assert "still running" in result.lower()
        release.set()


@pytest.mark.asyncio
async def test_get_result_kill_cancels_and_consumes(manager):
    release = asyncio.Event()

    async def gated(*args, **kwargs):
        await release.wait()
        return AgentTaskResult("agent", "never", None)

    delegate = create_background_delegate_tool(manager)
    get_result = create_get_delegation_result_tool()
    with (
        patch("zrb.llm.tool.delegate_background.run_agent_task", side_effect=gated),
        patch(
            "zrb.llm.tool.delegate_background.get_current_ui", return_value=MagicMock()
        ),
    ):
        msg = await delegate("agent", "deliver", "do it", [])
        handle = msg.split("Handle:")[1].split(".")[0].strip()
        killed = await get_result(handle, kill=True)
        assert "Killed" in killed
        # Handle is consumed after kill.
        gone = await get_result(handle)
        assert "Unknown handle" in gone


@pytest.mark.asyncio
async def test_approval_prompt_surfaces_during_wait(manager):
    """While GetDelegationResult(wait=N) is parked, a background sub-agent that
    needs approval must still reach the parent UI (the wait is async, so the
    event loop is free to service the prompt)."""
    parent_ui = MagicMock()
    parent_ui.ask_user = AsyncMock(return_value="yes")

    async def needs_approval(*args, **kwargs):
        # Routed through BufferedUI → parent_ui.ask_user.
        answer = await kwargs["ui"].ask_user("approve?")
        return AgentTaskResult("agent", f"approved={answer}", None)

    delegate = create_background_delegate_tool(manager)
    get_result = create_get_delegation_result_tool()
    with (
        patch(
            "zrb.llm.tool.delegate_background.run_agent_task",
            side_effect=needs_approval,
        ),
        patch(
            "zrb.llm.tool.delegate_background.get_current_ui", return_value=parent_ui
        ),
    ):
        msg = await delegate("agent", "deliver", "do it", [])
        handle = msg.split("Handle:")[1].split(".")[0].strip()
        # The sub-agent has not run yet; the prompt must surface inside this wait.
        result = await asyncio.wait_for(get_result(handle, wait=5), timeout=2)

    parent_ui.ask_user.assert_awaited()  # the prompt surfaced during the wait
    assert "approved=yes" in result


@pytest.mark.asyncio
async def test_handle_consumed_after_collection(manager):
    async def quick_task(*args, **kwargs):
        return AgentTaskResult("agent", "result text", None)

    delegate = create_background_delegate_tool(manager)
    get_result = create_get_delegation_result_tool()
    with (
        patch(
            "zrb.llm.tool.delegate_background.run_agent_task", side_effect=quick_task
        ),
        patch(
            "zrb.llm.tool.delegate_background.get_current_ui", return_value=MagicMock()
        ),
    ):
        msg = await delegate("agent", "deliver", "do it", [])
        handle = msg.split("Handle:")[1].split(".")[0].strip()
        # Keep the patch active until the detached task actually runs.
        for _ in range(5):
            await asyncio.sleep(0)
        first = await get_result(handle)
        # Second poll: handle has been consumed.
        second = await get_result(handle)
    assert "result text" in first
    assert "Unknown handle" in second


@pytest.mark.asyncio
async def test_own_background_handles_track_only_this_calls_handle(manager):
    """`register_background_handle` scopes to this delegate call's own handle."""

    async def quick_task(*args, **kwargs):
        return AgentTaskResult("agent", "ok", None)

    delegate = create_background_delegate_tool(manager)
    with (
        patch(
            "zrb.llm.tool.delegate_background.run_agent_task", side_effect=quick_task
        ),
        patch(
            "zrb.llm.tool.delegate_background.get_current_ui", return_value=MagicMock()
        ),
    ):
        assert get_own_background_handles() == set()
        msg = await delegate("agent", "deliver", "do it", [])
    handle = msg.split("Handle:")[1].split(".")[0].strip()
    assert get_own_background_handles() == {handle}


@pytest.mark.asyncio
async def test_peek_done_reports_completion_once(manager):
    """peek_done surfaces a finished handle exactly once, without consuming it."""

    async def quick_task(*args, **kwargs):
        return AgentTaskResult("agent", "ok", None)

    delegate = create_background_delegate_tool(manager)
    with (
        patch(
            "zrb.llm.tool.delegate_background.run_agent_task", side_effect=quick_task
        ),
        patch(
            "zrb.llm.tool.delegate_background.get_current_ui", return_value=MagicMock()
        ),
    ):
        msg = await delegate("agent", "deliver", "do it", [])
        handle = msg.split("Handle:")[1].split(".")[0].strip()
        for _ in range(5):
            await asyncio.sleep(0)

        registry = get_background_registry()
        first = registry.peek_done({handle})
        second = registry.peek_done({handle})

    assert first == [(handle, "agent")]
    assert second == []


@pytest.mark.asyncio
async def test_live_context_notice_reports_once_then_stays_quiet(manager):
    async def quick_task(*args, **kwargs):
        return AgentTaskResult("agent", "ok", None)

    delegate = create_background_delegate_tool(manager)
    with (
        patch(
            "zrb.llm.tool.delegate_background.run_agent_task", side_effect=quick_task
        ),
        patch(
            "zrb.llm.tool.delegate_background.get_current_ui", return_value=MagicMock()
        ),
    ):
        msg = await delegate("agent", "deliver", "do it", [])
        handle = msg.split("Handle:")[1].split(".")[0].strip()
        for _ in range(5):
            await asyncio.sleep(0)

        notice = background_delegation_live_context(MagicMock())
        quiet = background_delegation_live_context(MagicMock())

    assert notice is not None
    assert handle in notice
    assert "agent" in notice
    assert "GetDelegationResult" in notice
    assert quiet is None


@pytest.mark.asyncio
async def test_live_context_silent_while_still_running(manager):
    release = asyncio.Event()

    async def gated(*args, **kwargs):
        await release.wait()
        return AgentTaskResult("agent", "x", None)

    delegate = create_background_delegate_tool(manager)
    with (
        patch("zrb.llm.tool.delegate_background.run_agent_task", side_effect=gated),
        patch(
            "zrb.llm.tool.delegate_background.get_current_ui", return_value=MagicMock()
        ),
    ):
        await delegate("agent", "deliver", "do it", [])
        notice = background_delegation_live_context(MagicMock())
        release.set()

    assert notice is None


@pytest.mark.asyncio
async def test_live_context_notice_does_not_consume_the_handle(manager):
    """The push notice is a heads-up, not the retrieval — GetDelegationResult
    must still return the real payload afterward (single-consumption intact)."""

    async def quick_task(*args, **kwargs):
        return AgentTaskResult("agent", "payload here", None)

    delegate = create_background_delegate_tool(manager)
    get_result = create_get_delegation_result_tool()
    with (
        patch(
            "zrb.llm.tool.delegate_background.run_agent_task", side_effect=quick_task
        ),
        patch(
            "zrb.llm.tool.delegate_background.get_current_ui", return_value=MagicMock()
        ),
    ):
        msg = await delegate("agent", "deliver", "do it", [])
        handle = msg.split("Handle:")[1].split(".")[0].strip()
        for _ in range(5):
            await asyncio.sleep(0)

        background_delegation_live_context(MagicMock())  # surfaces, doesn't consume
        result = await get_result(handle)

    assert "payload here" in result
