"""Tests for background subagent delegation."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.agent.subagent.manager import SubAgentDefinition, SubAgentManager
from zrb.llm.permission import Capability, tool_capability
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


def test_capabilities():
    assert tool_capability(create_background_delegate_tool(MagicMock())) == (
        Capability.DELEGATE
    )
    assert tool_capability(create_get_delegation_result_tool()) == Capability.META


def test_background_tool_is_delegate_tool(manager):
    tool = create_background_delegate_tool(manager)
    assert getattr(tool, "zrb_is_delegate_tool", False) is True
    assert tool.__name__ == "DelegateToAgentBackground"


def test_background_docstring_carries_the_agent_roster(manager):
    manager.scan.return_value = [
        SubAgentDefinition(
            name="test-agent",
            path="path",
            description="A test agent",
            system_prompt="prompt",
        )
    ]

    tool = create_background_delegate_tool(manager)

    assert "AVAILABLE AGENTS" in tool.__doc__
    assert "test-agent" in tool.__doc__


@pytest.mark.asyncio
async def test_unknown_agent_is_rejected_before_detaching(manager):
    """A bad name must fail at call time, not at GetDelegationResult time."""
    manager.get_agent_definition.return_value = None
    manager.scan.return_value = [
        SubAgentDefinition(
            name="test-agent",
            path="path",
            description="A test agent",
            system_prompt="prompt",
        )
    ]
    delegate = create_background_delegate_tool(manager)

    result = await delegate(
        agent_name="test-agnt",
        deliverable="a result",
        task="task",
        non_goals=[],
    )

    assert "Did you mean 'test-agent'?" in result
    # No handle was minted, so the model cannot poll for a run that never began.
    assert "Handle" not in result


@pytest.mark.asyncio
async def test_name_check_does_not_build_the_agent(manager):
    """Validation uses the definition lookup, not a full agent build.

    ``create_agent`` runs every tool factory, resolves the model, and composes
    the system prompt — and ``run_agent_task`` calls it again in the
    coroutine. Validating with it would build twice and put the first build on
    the caller's turn, which is the wait this tool exists to avoid.
    """
    delegate = create_background_delegate_tool(manager)

    with patch(
        "zrb.llm.tool.delegate_background.run_agent_task",
        side_effect=AsyncMock(return_value=AgentTaskResult("a", "done", None)),
    ):
        result = await delegate(
            agent_name="test-agent",
            deliverable="a result",
            task="task",
            non_goals=[],
        )

    assert "Handle" in result
    manager.get_agent_definition.assert_called_once_with("test-agent")
    manager.create_agent.assert_not_called()


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
    with (
        patch("zrb.llm.tool.delegate_background.run_agent_task", side_effect=slow_task),
        patch(
            "zrb.llm.tool.delegate_background.get_current_ui", return_value=MagicMock()
        ),
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
    with (
        patch("zrb.llm.tool.delegate_background.run_agent_task", side_effect=boom),
        patch(
            "zrb.llm.tool.delegate_background.get_current_ui", return_value=MagicMock()
        ),
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
    mode, and auto-approves tool calls (yolo=True) so background agents never
    block. Deny rules in the permission policy still block at execution time."""
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
        with (
            patch(
                "zrb.llm.tool.delegate_background.run_agent_task",
                side_effect=capture_env,
            ),
            patch(
                "zrb.llm.tool.delegate_background.get_current_ui",
                return_value=MagicMock(),
            ),
        ):
            await delegate("agent", "deliver", "do it", [])
            for _ in range(5):
                await asyncio.sleep(0)
    finally:
        current_approval_channel.reset(tok)

    assert captured["channel"] is sentinel_channel  # inherited, not dropped
    assert captured["interactive"] is True  # not forced off
    assert captured["forced_yolo"] is True  # auto-approve background tool calls


@pytest.mark.asyncio
async def test_cancel_all_clears_running_tasks(manager):
    release = asyncio.Event()

    async def slow(*args, **kwargs):
        await release.wait()
        return AgentTaskResult("agent", "x", None)

    delegate = create_background_delegate_tool(manager)
    with (
        patch("zrb.llm.tool.delegate_background.run_agent_task", side_effect=slow),
        patch(
            "zrb.llm.tool.delegate_background.get_current_ui", return_value=MagicMock()
        ),
    ):
        msg = await delegate("agent", "deliver", "do it", [])
    handle = msg.split("Handle:")[1].split(".")[0].strip()

    get_background_registry().cancel_all()
    # Handle is gone after cancel_all.
    result = await create_get_delegation_result_tool()(handle)
    assert "Unknown handle" in result
    release.set()


@pytest.mark.asyncio
async def test_get_result_wait_returns_on_completion(manager):
    """wait=N returns the instant the agent finishes, not after the full N."""
    release = asyncio.Event()

    async def gated(*args, **kwargs):
        await release.wait()
        return AgentTaskResult("agent", "finished payload", None)

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

        # Release shortly after starting the wait; a 5s budget should return
        # as soon as the task completes.
        async def _release_soon():
            await asyncio.sleep(0.05)
            release.set()

        asyncio.ensure_future(_release_soon())
        result = await asyncio.wait_for(get_result(handle, wait=5), timeout=2)
    assert "finished payload" in result


@pytest.mark.asyncio
async def test_get_result_strips_ansi_from_buffered_transcript(manager):
    """The buffered sub-agent transcript BufferedUI feeds into the poll result
    carries muted-styling ANSI codes (for its own live-viewer pane) — those
    must not leak into the parent model's context, which doesn't render
    escape codes."""

    async def with_styled_output(*args, **kwargs):
        kwargs["ui"].append_to_output("🧰 call_1 | SomeTool", kind="tool_call")
        return AgentTaskResult("agent", "done", None)

    delegate = create_background_delegate_tool(manager)
    get_result = create_get_delegation_result_tool()
    with (
        patch(
            "zrb.llm.tool.delegate_background.run_agent_task",
            side_effect=with_styled_output,
        ),
        patch(
            "zrb.llm.tool.delegate_background.get_current_ui", return_value=MagicMock()
        ),
    ):
        msg = await delegate("agent", "deliver", "do it", [])
        handle = msg.split("Handle:")[1].split(".")[0].strip()
        result = await asyncio.wait_for(get_result(handle, wait=2), timeout=3)

    assert "🧰 call_1 | SomeTool" in result
    assert "done" in result
    assert "\033[" not in result


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
