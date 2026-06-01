"""Tests for background subagent delegation."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.agent.subagent.manager import SubAgentManager
from zrb.llm.permission import Capability, tool_capability
from zrb.llm.tool.delegate import AgentTaskResult
from zrb.llm.tool.delegate_background import (
    create_background_delegate_tool,
    create_get_delegation_result_tool,
    get_background_registry,
)


@pytest.fixture
def manager():
    return MagicMock(spec=SubAgentManager)


@pytest.fixture(autouse=True)
def clean_registry():
    yield
    get_background_registry().cancel_all()


def test_capabilities():
    assert tool_capability(create_background_delegate_tool(MagicMock())) == (
        Capability.DELEGATE
    )
    assert tool_capability(create_get_delegation_result_tool()) == Capability.META


def test_background_tool_is_delegate_tool(manager):
    tool = create_background_delegate_tool(manager)
    assert getattr(tool, "zrb_is_delegate_tool", False) is True
    assert tool.__name__ == "DelegateToAgentBackground"


@pytest.mark.asyncio
async def test_returns_handle_immediately_without_blocking(manager):
    """The start call must return before the (slow) sub-agent finishes."""
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_task(*args, **kwargs):
        started.set()
        await release.wait()
        return AgentTaskResult("agent", "done work", None)

    delegate = create_background_delegate_tool(manager)
    with patch(
        "zrb.llm.tool.delegate_background._run_agent_task", side_effect=slow_task
    ), patch(
        "zrb.llm.tool.delegate_background.get_current_ui", return_value=MagicMock()
    ):
        msg = await delegate("agent", "deliver", "do it", [])
        # The sub-agent has started but not completed.
        await asyncio.wait_for(started.wait(), timeout=1)

    assert "Handle:" in msg
    handle = msg.split("Handle:")[1].split(".")[0].strip()

    get_result = create_get_delegation_result_tool()
    # Still running before we release it.
    running = await get_result(handle)
    assert "still running" in running.lower()

    # Release and let it finish, then poll again.
    release.set()
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    done = await get_result(handle)
    assert "done work" in done


@pytest.mark.asyncio
async def test_get_result_unknown_handle():
    get_result = create_get_delegation_result_tool()
    msg = await get_result("nonexistent-handle")
    assert "Unknown handle" in msg


@pytest.mark.asyncio
async def test_failed_subagent_surfaces_error(manager):
    async def boom(*args, **kwargs):
        raise RuntimeError("kaboom")

    delegate = create_background_delegate_tool(manager)
    with patch(
        "zrb.llm.tool.delegate_background._run_agent_task", side_effect=boom
    ), patch(
        "zrb.llm.tool.delegate_background.get_current_ui", return_value=MagicMock()
    ):
        msg = await delegate("agent", "deliver", "do it", [])
        handle = msg.split("Handle:")[1].split(".")[0].strip()
        # Keep the patch active until the detached task actually runs.
        for _ in range(5):
            await asyncio.sleep(0)
        result = await create_get_delegation_result_tool()(handle)
    assert "failed" in result and "kaboom" in result


@pytest.mark.asyncio
async def test_background_inherits_parent_permission_context(manager):
    """The background task inherits the parent's approval channel and interactive
    mode (it does NOT neutralize them and does NOT force yolo), so its tool-call
    approvals route to the user's UI just like a synchronous delegate."""
    from zrb.llm.approval.approval_channel import current_approval_channel
    from zrb.llm.tool.ambient_state import get_interactive_mode, set_interactive_mode

    sentinel_channel = MagicMock()
    captured = {}

    async def capture_env(*args, **kwargs):
        captured["channel"] = current_approval_channel.get()
        captured["interactive"] = get_interactive_mode()
        captured["forced_yolo"] = "yolo" in kwargs
        return AgentTaskResult("agent", "ok", None)

    tok = current_approval_channel.set(sentinel_channel)
    set_interactive_mode(True)
    try:
        delegate = create_background_delegate_tool(manager)
        with patch(
            "zrb.llm.tool.delegate_background._run_agent_task", side_effect=capture_env
        ), patch(
            "zrb.llm.tool.delegate_background.get_current_ui", return_value=MagicMock()
        ):
            await delegate("agent", "deliver", "do it", [])
            for _ in range(5):
                await asyncio.sleep(0)
    finally:
        current_approval_channel.reset(tok)

    assert captured["channel"] is sentinel_channel  # inherited, not dropped
    assert captured["interactive"] is True  # not forced off
    assert captured["forced_yolo"] is False  # no forced auto-approve


@pytest.mark.asyncio
async def test_cancel_all_clears_running_tasks(manager):
    release = asyncio.Event()

    async def slow(*args, **kwargs):
        await release.wait()
        return AgentTaskResult("agent", "x", None)

    delegate = create_background_delegate_tool(manager)
    with patch(
        "zrb.llm.tool.delegate_background._run_agent_task", side_effect=slow
    ), patch(
        "zrb.llm.tool.delegate_background.get_current_ui", return_value=MagicMock()
    ):
        msg = await delegate("agent", "deliver", "do it", [])
    handle = msg.split("Handle:")[1].split(".")[0].strip()

    get_background_registry().cancel_all()
    # Handle is gone after cancel_all.
    result = await create_get_delegation_result_tool()(handle)
    assert "Unknown handle" in result
    release.set()


@pytest.mark.asyncio
async def test_handle_consumed_after_collection(manager):
    async def quick_task(*args, **kwargs):
        return AgentTaskResult("agent", "result text", None)

    delegate = create_background_delegate_tool(manager)
    get_result = create_get_delegation_result_tool()
    with patch(
        "zrb.llm.tool.delegate_background._run_agent_task", side_effect=quick_task
    ), patch(
        "zrb.llm.tool.delegate_background.get_current_ui", return_value=MagicMock()
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
