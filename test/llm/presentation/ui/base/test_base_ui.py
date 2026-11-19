"""The turn pipeline `BaseUI` drives, and the clocks it reports on the status bar.

A message reaches the loop and becomes a call to the task; the answer lands in
`display.last_output`. Around that sit the seams a front end leans on — tool
confirmation, the two hook entry points, the system-info tick, the cwd display —
and the two timers: the working clock that covers one stretch of thinking and
resets only when thinking stops, and the tool-call clock that a concurrent
sibling must not clear. What happens to a message once it is queued is
`test_base_ui_queued_messages`.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.context.context import Context
from zrb.context.shared_context import SharedContext

from .base_ui_support import ConcreteUI


@pytest.mark.asyncio
async def test_submit_user_message_processing(base_ui):
    """Test that submitting a message eventually calls the LLM task."""
    base_ui.llm_task.async_run = AsyncMock(return_value="AI Response")

    with patch.object(
        base_ui, "stream_ai_response", new_callable=AsyncMock
    ) as mock_stream:
        base_ui.submit_user_message(base_ui.llm_task, "hello")

        # Start the loop task
        task = asyncio.create_task(base_ui.process_messages_loop())

        # Wait for the job to be picked up
        for _ in range(10):
            if mock_stream.called:
                break
            await asyncio.sleep(0.01)

        assert mock_stream.called
        task.cancel()


@pytest.mark.asyncio
async def test_stream_ai_response_updates_last_output(base_ui):
    """Verify that the AI response stream updates the public last_output property."""
    base_ui.llm_task.async_run = AsyncMock(return_value="AI Response")

    await base_ui.stream_ai_response(base_ui.llm_task, "user message")

    assert base_ui.display.last_output == "AI Response"


@pytest.mark.asyncio
async def test_confirm_tool_execution_delegation(base_ui):
    """Tool confirmation delegates to the internal handler via ``handle``."""
    mock_call = MagicMock()
    # tool_call_handler is public
    base_ui.tool_call_handler.handle = AsyncMock(return_value="Approved")

    # _confirm_tool_execution is protected but part of the UI protocol implementation
    res = await base_ui.confirm_tool_execution(mock_call)
    assert res == "Approved"


def test_execute_hook_observable(base_ui):
    """Test execute_hook by mocking the global hook manager."""
    from zrb.llm.capabilities.hook.contracts.types import HookEvent

    with patch(
        "zrb.llm.capabilities.hook.manager.manager.hook_manager.execute_hooks",
        new_callable=AsyncMock,
    ) as mock_exec:
        base_ui.execute_hook(HookEvent.NOTIFICATION, {"msg": "hi"})
        assert mock_exec.called


@pytest.mark.asyncio
async def test_execute_hook_blocking_returns_results(base_ui):
    """execute_hook_blocking awaits the manager and returns its results."""
    from zrb.llm.capabilities.hook.contracts.types import HookEvent

    sentinel = ["result"]
    with patch(
        "zrb.llm.capabilities.hook.manager.manager.hook_manager.execute_hooks",
        new_callable=AsyncMock,
    ) as mock_exec:
        mock_exec.return_value = sentinel
        results = await base_ui.execute_hook_blocking(
            HookEvent.PRE_COMMAND, {"command": "/save"}, command_name="/save"
        )
        assert results is sentinel
        assert mock_exec.call_args.args[0] == HookEvent.PRE_COMMAND
        assert mock_exec.call_args.kwargs["command_name"] == "/save"


@pytest.mark.asyncio
async def test_execute_hook_blocking_uses_the_task_hook_manager(base_ui):
    """A PreCommand hook registered on the task's own manager can block."""
    from zrb.llm.capabilities.hook.contracts.types import HookEvent

    base_ui.llm_task.hook_manager = MagicMock()
    base_ui.llm_task.hook_manager.execute_hooks = AsyncMock(return_value=["mine"])

    result = await base_ui.execute_hook_blocking(HookEvent.PRE_COMMAND, {})

    assert result == ["mine"]


@pytest.mark.asyncio
async def test_update_system_info_loop(base_ui):
    """Test that the system info loop periodically calls update_system_info."""
    with (
        patch.object(
            base_ui, "update_system_info", new_callable=AsyncMock
        ) as mock_update,
        patch("zrb.llm.presentation.ui.base.ui.CFG") as mock_cfg,
    ):

        mock_cfg.LLM_UI_STATUS_INTERVAL = 1  # 1ms
        mock_cfg.LLM_UI_LONG_STATUS_INTERVAL = 1  # 1ms
        task = asyncio.create_task(base_ui.update_system_info_loop())

        # Wait for a few iterations
        await asyncio.sleep(0.05)

        assert mock_update.call_count >= 1

        # Cleanup
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def test_get_cwd_display_logic(base_ui):
    """Test the get_cwd_display logic."""
    import os

    cwd = os.getcwd()
    # We test the method directly as it's part of the subclassing API
    res = base_ui.get_cwd_display()
    if cwd.startswith(os.path.expanduser("~")):
        assert res.startswith("~")
    else:
        assert res == cwd


def test_working_timer_starts_and_resets_with_thinking_state():
    """The status bar timer covers only the current working period."""
    ctx = Context(SharedContext(), "test", 0, "")
    ui = ConcreteUI(ctx=ctx, llm_task=MagicMock(), history_manager=MagicMock())
    assert ui.working_started_at is None

    with patch(
        "zrb.llm.presentation.ui.base.status_bar.time.monotonic", return_value=12345.0
    ):
        ui.is_thinking = True
    assert ui.working_started_at == 12345.0

    with patch(
        "zrb.llm.presentation.ui.base.status_bar.time.monotonic", return_value=99999.0
    ):
        ui.is_thinking = True
    assert ui.working_started_at == 12345.0

    ui.is_thinking = False
    assert ui.working_started_at is None


def test_start_tool_call_records_the_running_tool(base_ui):
    """`start_tool_call` captures the tool name, id and a monotonic start time."""
    with patch(
        "zrb.llm.presentation.ui.base.status_bar.time.monotonic", return_value=999.0
    ):
        base_ui.start_tool_call("Shell", "call_1")

    running = base_ui.running_tool
    assert running is not None
    assert running.tool_name == "Shell"
    assert running.tool_call_id == "call_1"
    assert running.started_at == 999.0


def test_end_tool_call_clears_the_running_tool(base_ui):
    """`end_tool_call` takes the running-tool timer off the status bar."""
    base_ui.start_tool_call("Shell", "call_1")
    assert base_ui.running_tool is not None

    base_ui.end_tool_call("call_1")

    assert base_ui.running_tool is None


def test_end_tool_call_keeps_a_still_running_different_call(base_ui):
    """A completed call clears only its own timer, not a concurrent sibling's."""
    base_ui.start_tool_call("Shell", "call_1")
    base_ui.start_tool_call("WebSearch", "call_2")

    base_ui.end_tool_call("call_1")  # call_1 finished first

    running = base_ui.running_tool
    assert running is not None
    assert running.tool_name == "WebSearch"
    assert running.tool_call_id == "call_2"

    base_ui.end_tool_call("call_2")
    assert base_ui.running_tool is None


def test_end_tool_call_keeps_an_older_call_when_a_newer_one_finishes_first(base_ui):
    """A call that finishes out of order clears only itself, never an older one."""
    base_ui.start_tool_call("Shell", "call_1")
    base_ui.start_tool_call("WebSearch", "call_2")

    base_ui.end_tool_call("call_2")  # call_2 finished first

    running = base_ui.running_tool
    assert running is not None
    assert running.tool_name == "Shell"
    assert running.tool_call_id == "call_1"

    base_ui.end_tool_call("call_1")
    assert base_ui.running_tool is None
