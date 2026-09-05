import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

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


def test_submit_user_message_queues_job(mock_child_ui):
    """Test _submit_user_message queues a job."""
    multi_ui = MultiUI([mock_child_ui])
    mock_task = MagicMock()

    multi_ui.submit_user_message(mock_task, "Hello world")

    # Verify through public behavior - message was broadcast
    mock_child_ui.append_to_output.assert_called()


@pytest.mark.asyncio
async def test_submit_user_message_broadcasts(mock_child_ui):
    """Test _submit_user_message broadcasts to all UIs."""
    multi_ui = MultiUI([mock_child_ui])
    multi_ui.append_to_output = MagicMock()

    mock_task = MagicMock()

    multi_ui.submit_user_message(mock_task, "Hello world")

    # Verify broadcast was called
    multi_ui.append_to_output.assert_called()


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
