import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.ui.multi_ui import MultiUI


@pytest.fixture
def child_ui_1():
    ui = MagicMock()
    ui.append_to_output = MagicMock()
    ui.invalidate_ui = MagicMock()
    ui.ask_user = AsyncMock(return_value="input 1")
    ui.run_interactive_command = AsyncMock(return_value=0)
    ui.run_async = AsyncMock(return_value="done 1")
    ui._cancel_pending_confirmations = MagicMock()
    # Mock some expected properties/methods that MultiUI might delegate to
    ui.tool_call_handler = MagicMock()
    ui.tool_call_handler.handle = AsyncMock(return_value="Approved 1")
    return ui


@pytest.fixture
def child_ui_2():
    ui = MagicMock()
    ui.append_to_output = MagicMock()
    ui.invalidate_ui = MagicMock()
    ui.ask_user = AsyncMock(return_value="input 2")
    ui.start_event_loop = AsyncMock()
    ui._cancel_pending_confirmations = MagicMock()
    return ui


@pytest.fixture
def multi_ui(child_ui_1, child_ui_2):
    return MultiUI([child_ui_1, child_ui_2])


def test_multi_ui_init(multi_ui, child_ui_1, child_ui_2):
    assert child_ui_1._multi_ui_parent is multi_ui
    assert child_ui_2._multi_ui_parent is multi_ui
    # multi_ui._main_ui is a property
    assert multi_ui._main_ui is child_ui_1


def test_multi_ui_append_to_output(multi_ui, child_ui_1, child_ui_2):
    multi_ui.append_to_output("test", kind="progress")
    child_ui_1.append_to_output.assert_called_with(
        "test", sep=" ", end="\n", file=None, flush=False, kind="progress"
    )
    child_ui_2.append_to_output.assert_called_with(
        "test", sep=" ", end="\n", file=None, flush=False, kind="progress"
    )


@pytest.mark.asyncio
async def test_multi_ui_ask_user_race(multi_ui, child_ui_1, child_ui_2):
    # Make child_ui_1 slower
    async def slow_ask(*args):
        await asyncio.sleep(0.1)
        return "input 1"

    child_ui_1.ask_user = slow_ask

    # Make child_ui_2 faster
    async def fast_ask(*args):
        await asyncio.sleep(0.01)
        return "input 2"

    child_ui_2.ask_user = fast_ask

    res = await multi_ui.ask_user("prompt")
    assert res == "input 2"


@pytest.mark.asyncio
async def test_multi_ui_run_async(multi_ui, child_ui_1, child_ui_2):
    multi_ui.set_llm_task(MagicMock())
    child_ui_1.last_output = "Final Output"

    res = await multi_ui.run_async()

    assert res == "Final Output"
    child_ui_1.run_async.assert_called_once()
    child_ui_2.start_event_loop.assert_called_once()


@pytest.mark.asyncio
async def test_multi_ui_run_interactive_command(multi_ui, child_ui_1):
    res = await multi_ui.run_interactive_command("ls")
    assert res == 0
    child_ui_1.run_interactive_command.assert_called_with("ls", shell=False)


def test_multi_ui_invalidate_all(multi_ui, child_ui_1, child_ui_2):
    multi_ui.invalidate_all_uis()
    child_ui_1.invalidate_ui.assert_called_once()
    child_ui_2.invalidate_ui.assert_called_once()


@pytest.mark.asyncio
async def test_multi_ui_submit_message_and_stream(multi_ui):
    llm_task = MagicMock()
    llm_task.async_run = AsyncMock(return_value="AI Output")

    multi_ui._submit_user_message(llm_task, "user query")

    # Start message processor loop manually for test
    task = asyncio.create_task(multi_ui._process_messages_loop())

    # Wait for processing
    await asyncio.sleep(0.05)

    # _last_result_data is internal, but last_output property should reflect it
    # We'll check via mock side effect or just by calling it
    llm_task.async_run.assert_called_once()

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_multi_ui_confirm_tool_execution(multi_ui, child_ui_1):
    mock_call = MagicMock()

    # Test fallback to first UI's handler
    res = await multi_ui._confirm_tool_execution(mock_call)
    assert res == "Approved 1"

    # Test with multi_ui handler
    handler = MagicMock()
    handler.handle = AsyncMock(return_value="Approved Multi")
    multi_ui.set_tool_call_handler(handler)
    res2 = await multi_ui._confirm_tool_execution(mock_call)
    assert res2 == "Approved Multi"

    # Test with approval channel
    multi_ui.set_tool_call_handler(None)
    channel = MagicMock()
    result = MagicMock()
    result.to_pydantic_result.return_value = "Approved Channel"
    channel.request_approval = AsyncMock(return_value=result)
    multi_ui.set_approval_channel(channel)
    res3 = await multi_ui._confirm_tool_execution(mock_call)
    assert res3 == "Approved Channel"


def test_multi_ui_on_exit(multi_ui, child_ui_1):
    child_ui_1.on_exit = MagicMock()
    multi_ui.on_exit()
    child_ui_1.on_exit.assert_called_once()
