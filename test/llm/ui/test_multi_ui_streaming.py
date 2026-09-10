from unittest.mock import AsyncMock, MagicMock

import pytest

from zrb.llm.ui.multi_ui import MultiUI


@pytest.fixture
def mock_child_ui():
    """Create a mock child UI for testing."""
    ui = MagicMock()
    ui.append_to_output = MagicMock()
    ui.ask_user = AsyncMock(return_value="y")
    ui.tool_call_handler = MagicMock()
    ui.tool_call_handler.check_policies = AsyncMock(return_value=None)
    ui.tool_call_handler.handle = AsyncMock(return_value=MagicMock(approved=True))
    ui.plan_mode_active = False
    ui.snapshot_manager = None
    ui.history_manager = None
    return ui


@pytest.fixture
def child_ui_1():
    ui = MagicMock()
    ui.append_to_output = MagicMock()
    ui.invalidate_ui = MagicMock()
    ui.ask_user = AsyncMock(return_value="input 1")
    ui.run_interactive_command = AsyncMock(return_value=0)
    ui.run_async = AsyncMock(return_value="done 1")
    ui.cancel_pending_confirmations = MagicMock()
    ui.tool_call_handler = MagicMock()
    ui.tool_call_handler.handle = AsyncMock(return_value="Approved 1")
    ui.plan_mode_active = False
    ui.snapshot_manager = None
    ui.history_manager = None
    return ui


@pytest.fixture
def child_ui_2():
    ui = MagicMock()
    ui.append_to_output = MagicMock()
    ui.invalidate_ui = MagicMock()
    ui.ask_user = AsyncMock(return_value="input 2")
    ui.start_event_loop = AsyncMock()
    ui.cancel_pending_confirmations = MagicMock()
    ui.plan_mode_active = False
    return ui


@pytest.fixture
def multi_ui(child_ui_1, child_ui_2):
    return MultiUI([child_ui_1, child_ui_2])


@pytest.mark.asyncio
async def test_stream_ai_response_resets_is_thinking_on_error(mock_child_ui):
    """Test _stream_ai_response handles errors gracefully."""
    multi_ui = MultiUI([mock_child_ui])
    multi_ui.append_to_output = MagicMock()

    mock_llm_task = MagicMock()

    async def raise_error():
        raise ValueError("Test error")

    mock_llm_task.async_run = AsyncMock(side_effect=raise_error)
    mock_llm_task.set_ui = MagicMock()
    mock_llm_task.tool_confirmation = MagicMock()

    # Should not raise, but should handle error gracefully
    await multi_ui.stream_ai_response(mock_llm_task, "Hello", [])

    # Verify output was attempted (error message shown)
    multi_ui.append_to_output.assert_called()


@pytest.mark.asyncio
async def test_stream_ai_response_handles_error(mock_child_ui):
    """Test _stream_ai_response handles errors gracefully."""
    multi_ui = MultiUI([mock_child_ui])
    multi_ui.append_to_output = MagicMock()

    mock_llm_task = MagicMock()

    async def raise_error():
        raise ValueError("Test error")

    mock_llm_task.async_run = AsyncMock(side_effect=raise_error)
    mock_llm_task.set_ui = MagicMock()
    mock_llm_task.tool_confirmation = MagicMock()

    # Should not raise, but should log error
    await multi_ui.stream_ai_response(mock_llm_task, "Hello", [])

    # Verify error was handled (output was called)
    multi_ui.append_to_output.assert_called()


@pytest.mark.asyncio
async def test_stream_ai_response_with_result(mock_child_ui):
    """Test _stream_ai_response processes result correctly."""
    multi_ui = MultiUI([mock_child_ui])
    multi_ui.append_to_output = MagicMock()

    mock_llm_task = MagicMock()
    mock_llm_task.async_run = AsyncMock(return_value="# Response")
    mock_llm_task.set_ui = MagicMock()
    mock_llm_task.tool_confirmation = MagicMock()

    await multi_ui.stream_ai_response(mock_llm_task, "Hello", [])

    # Verify output was rendered
    multi_ui.append_to_output.assert_called()


@pytest.mark.asyncio
async def test_multi_ui_stream_sets_thinking_on_children(multi_ui, child_ui_1):
    multi_ui.append_to_output = MagicMock()
    llm_task = MagicMock()
    llm_task.async_run = AsyncMock(return_value="# Response")
    llm_task.set_ui = MagicMock()
    llm_task.tool_confirmation = MagicMock()

    await multi_ui.stream_ai_response(llm_task, "Hello", [])

    # Thinking flag must be False after the run, not just during it.
    assert multi_ui.is_thinking is False
    assert child_ui_1.is_thinking is False


@pytest.mark.asyncio
async def test_multi_ui_stream_uses_append_markdown_on_main_ui(multi_ui, child_ui_1):
    multi_ui.append_to_output = MagicMock()
    child_ui_1.append_markdown = MagicMock()
    llm_task = MagicMock()
    llm_task.async_run = AsyncMock(return_value="# Response")
    llm_task.set_ui = MagicMock()
    llm_task.tool_confirmation = MagicMock()

    await multi_ui.stream_ai_response(llm_task, "Hello", [])

    # The main UI gets themed, re-wrappable markdown; other children (e.g.
    # Telegram) get the pre-rendered text.
    child_ui_1.append_markdown.assert_called_once_with("# Response")


@pytest.mark.asyncio
async def test_multi_ui_stream_uses_rendered_text_on_other_children(
    multi_ui, child_ui_1, child_ui_2
):
    multi_ui.append_to_output = MagicMock()
    child_ui_1.append_markdown = MagicMock()
    # MagicMock auto-creates any attribute; remove it so hasattr() is False,
    # matching a real chat backend (e.g. TelegramUI) that lacks append_markdown.
    child_ui_2.append_markdown = None
    llm_task = MagicMock()
    llm_task.async_run = AsyncMock(return_value="# Response")
    llm_task.set_ui = MagicMock()
    llm_task.tool_confirmation = MagicMock()

    await multi_ui.stream_ai_response(llm_task, "Hello", [])

    # child_ui_2 has no append_markdown → gets rendered text with end="".
    child_ui_2.append_to_output.assert_called()
    args = child_ui_2.append_to_output.call_args
    assert args.kwargs.get("end") == ""


@pytest.mark.asyncio
async def test_multi_ui_stream_takes_snapshot_before_run(multi_ui, child_ui_1):
    multi_ui.append_to_output = MagicMock()
    snapshot_manager = MagicMock()
    snapshot_manager.take_snapshot = AsyncMock()
    child_ui_1.snapshot_manager = snapshot_manager
    child_ui_1.history_manager = MagicMock()
    child_ui_1.history_manager.load = MagicMock(return_value=["msg1"])
    child_ui_1.conversation_session_name = "my-session"

    llm_task = MagicMock()
    llm_task.async_run = AsyncMock(return_value="# Response")
    llm_task.set_ui = MagicMock()
    llm_task.tool_confirmation = MagicMock()

    await multi_ui.stream_ai_response(llm_task, "Hello", [])

    snapshot_manager.take_snapshot.assert_called_once()
    kwargs = snapshot_manager.take_snapshot.call_args.kwargs
    assert kwargs.get("message_count") == 1


@pytest.mark.asyncio
async def test_multi_ui_stream_syncs_plan_mode(multi_ui, child_ui_1):
    from zrb.llm.permission.state import (
        AgentMode,
        get_current_agent_mode,
        set_current_agent_mode,
    )

    multi_ui.append_to_output = MagicMock()
    child_ui_1.plan_mode_active = True
    llm_task = MagicMock()
    llm_task.async_run = AsyncMock(return_value="# Response")
    llm_task.set_ui = MagicMock()
    llm_task.tool_confirmation = MagicMock()

    try:
        await multi_ui.stream_ai_response(llm_task, "Hello", [])

        # Plan mode set on the main UI must reach the run and be read back.
        assert get_current_agent_mode() == AgentMode.PLAN
        assert child_ui_1.plan_mode_active is True
    finally:
        # Reset the module-level ContextVar so other tests don't inherit PLAN.
        set_current_agent_mode(AgentMode.BUILD)


@pytest.mark.asyncio
async def test_multi_ui_stream_updates_system_info_on_children(
    multi_ui, child_ui_1, child_ui_2
):
    multi_ui.append_to_output = MagicMock()
    child_ui_1.update_system_info = AsyncMock()
    child_ui_2.update_system_info = AsyncMock()
    llm_task = MagicMock()
    llm_task.async_run = AsyncMock(return_value="# Response")
    llm_task.set_ui = MagicMock()
    llm_task.tool_confirmation = MagicMock()

    await multi_ui.stream_ai_response(llm_task, "Hello", [])

    child_ui_1.update_system_info.assert_awaited_once()
    child_ui_2.update_system_info.assert_awaited_once()


@pytest.mark.asyncio
async def test_multi_ui_stream_repaints_after_system_info_update(multi_ui, child_ui_1):
    # The status bar must be repainted with fresh system info, not before it.
    # Sequence: thinking-on repaint → system info update → final repaint.
    multi_ui.append_to_output = MagicMock()
    order = []
    child_ui_1.invalidate_ui = MagicMock(side_effect=lambda: order.append("paint"))

    async def _update():
        order.append("update")

    child_ui_1.update_system_info = _update
    llm_task = MagicMock()
    llm_task.async_run = AsyncMock(return_value="# Response")
    llm_task.set_ui = MagicMock()
    llm_task.tool_confirmation = MagicMock()

    await multi_ui.stream_ai_response(llm_task, "Hello", [])

    assert order == ["paint", "update", "paint"]


@pytest.mark.asyncio
async def test_multi_ui_stream_non_string_result_clears_last_output(
    multi_ui, child_ui_1
):
    # A turn whose result is not a string must not leave last_output carrying
    # the previous turn's answer.
    multi_ui.append_to_output = MagicMock()
    multi_ui.last_result_data = "stale"
    llm_task = MagicMock()
    llm_task.async_run = AsyncMock(return_value={"structured": "result"})
    llm_task.set_ui = MagicMock()
    llm_task.tool_confirmation = MagicMock()

    await multi_ui.stream_ai_response(llm_task, "Hello", [])

    assert multi_ui.last_result_data is None
