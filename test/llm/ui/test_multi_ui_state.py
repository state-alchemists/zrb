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
    ui.cancel_pending_confirmations = MagicMock()
    # Mock some expected properties/methods that MultiUI might delegate to
    ui.tool_call_handler = MagicMock()
    ui.tool_call_handler.handle = AsyncMock(return_value="Approved 1")
    # Explicit non-mock state so _stream_ai_response's plan-mode sync and
    # snapshot path behave as they would with a real UI (a MagicMock would be
    # truthy and flip the global agent-mode ContextVar, polluting other tests).
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


def test_multi_ui_invalidate_all(multi_ui, child_ui_1, child_ui_2):
    multi_ui.invalidate_all_uis()
    child_ui_1.invalidate_ui.assert_called_once()
    child_ui_2.invalidate_ui.assert_called_once()


@pytest.mark.asyncio
async def test_multi_ui_process_messages_loop_no_busy_wait(multi_ui):
    # Regression: this loop used to busy-wait via `while ...: await
    # asyncio.sleep(0.1)` between jobs instead of awaiting the previous task
    # directly — the exact pattern base/ui.py's twin loop was fixed to avoid.
    real_sleep = asyncio.sleep
    sleep_delays = []

    async def tracking_sleep(delay, *a, **kw):
        sleep_delays.append(delay)
        return await real_sleep(0, *a, **kw)

    llm_task = MagicMock()
    llm_task.async_run = AsyncMock(return_value="AI Output")

    with patch("zrb.llm.ui.multi_ui.asyncio.sleep", side_effect=tracking_sleep):
        multi_ui.submit_user_message(llm_task, "first")
        multi_ui.submit_user_message(llm_task, "second")

        task = asyncio.create_task(multi_ui.process_messages_loop())
        # Wait for both queued jobs to be marked done rather than sleeping a
        # fixed wall-clock delay — under load, a fixed sleep can elapse before
        # the second job finishes, making the assertion below flaky.
        await asyncio.wait_for(multi_ui.message_queue.join(), timeout=5)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert 0.1 not in sleep_delays
    # Both queued jobs ran: the second wasn't stuck behind a poll loop that
    # never observed the first task settle.
    assert llm_task.async_run.call_count == 2


@pytest.mark.asyncio
async def test_multi_ui_submit_message_and_stream(multi_ui):
    llm_task = MagicMock()
    llm_task.async_run = AsyncMock(return_value="AI Output")

    multi_ui.submit_user_message(llm_task, "user query")

    # Start message processor loop manually for test
    task = asyncio.create_task(multi_ui.process_messages_loop())

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


def test_multi_ui_submit_message_steers_into_live_run_context(multi_ui):
    """A message sent while a turn is live is delivered into that turn
    instead of queuing (ADR-0078)."""
    llm_task = MagicMock()
    multi_ui.active_run_context = MagicMock()

    multi_ui.submit_user_message(llm_task, "steer me")

    multi_ui.active_run_context.enqueue.assert_called_once_with(
        "steer me", priority="asap"
    )
    assert multi_ui.message_queue.qsize() == 0


def test_multi_ui_submit_message_falls_back_to_queue_without_active_run_context(
    multi_ui,
):
    """No live turn (the default) keeps the existing queue behavior."""
    llm_task = MagicMock()
    assert multi_ui.active_run_context is None

    multi_ui.submit_user_message(llm_task, "later")

    assert multi_ui.message_queue.qsize() == 1


def test_multi_ui_submit_message_falls_back_to_queue_when_enqueue_raises(multi_ui):
    """A run that finished between the check and the call must not lose the
    message -- it falls back to the queue instead of being dropped."""
    llm_task = MagicMock()
    live_run = MagicMock()
    live_run.enqueue.side_effect = RuntimeError("run already finished")
    multi_ui.active_run_context = live_run

    multi_ui.submit_user_message(llm_task, "steer me")
    assert multi_ui.message_queue.qsize() == 1


def test_multi_ui_submit_message_uses_own_llm_task(multi_ui):
    """Public `submit_message` (no llm_task argument) forwards to the shared
    queue path with the queue's own task — the seam sub-agent continuation
    code uses to hand the main agent a synthesized report."""
    llm_task = MagicMock()
    multi_ui.set_llm_task(llm_task)
    with patch.object(multi_ui, "submit_user_message") as mock_submit:
        multi_ui.submit_message("report text")
    mock_submit.assert_called_once_with(llm_task, "report text")


@pytest.mark.asyncio
async def test_multi_ui_confirm_tool_execution(multi_ui, child_ui_1):
    mock_call = MagicMock()

    # Test fallback to first UI's handler
    res = await multi_ui.confirm_tool_execution(mock_call)
    assert res == "Approved 1"

    # Test with multi_ui handler
    handler = MagicMock()
    handler.handle = AsyncMock(return_value="Approved Multi")
    multi_ui.set_tool_call_handler(handler)
    res2 = await multi_ui.confirm_tool_execution(mock_call)
    assert res2 == "Approved Multi"

    # Test with approval channel
    multi_ui.set_tool_call_handler(None)
    channel = MagicMock()
    result = MagicMock()
    result.to_pydantic_result.return_value = "Approved Channel"
    channel.request_approval = AsyncMock(return_value=result)
    multi_ui.set_approval_channel(channel)
    res3 = await multi_ui.confirm_tool_execution(mock_call)
    assert res3 == "Approved Channel"


def test_multi_ui_on_exit(multi_ui, child_ui_1):
    child_ui_1.on_exit = MagicMock()
    multi_ui.on_exit()
    child_ui_1.on_exit.assert_called_once()
