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


def test_multi_ui_init(multi_ui, child_ui_1, child_ui_2):
    assert child_ui_1.multi_ui_parent is multi_ui
    assert child_ui_2.multi_ui_parent is multi_ui
    # multi_ui.main_ui is a property
    assert multi_ui.main_ui is child_ui_1


def test_multi_ui_append_to_output(multi_ui, child_ui_1, child_ui_2):
    multi_ui.append_to_output("test", kind="progress")
    child_ui_1.append_to_output.assert_called_with(
        "test", sep=" ", end="\n", file=None, flush=False, kind="progress"
    )
    child_ui_2.append_to_output.assert_called_with(
        "test", sep=" ", end="\n", file=None, flush=False, kind="progress"
    )


def test_multi_ui_accumulate_usage_forwards_to_children(
    multi_ui, child_ui_1, child_ui_2
):
    child_ui_1.accumulate_usage = MagicMock()
    child_ui_2.accumulate_usage = MagicMock()

    usage = MagicMock()
    context_usage = MagicMock()
    multi_ui.accumulate_usage(usage, context_usage)

    child_ui_1.accumulate_usage.assert_called_once_with(usage, context_usage)
    child_ui_2.accumulate_usage.assert_called_once_with(usage, context_usage)


def test_multi_ui_accumulate_usage_skips_children_without_method(multi_ui):
    # Children without accumulate_usage are silently skipped.
    no_method_child = MagicMock()
    del no_method_child.accumulate_usage
    multi_ui = MultiUI([no_method_child])

    # Should not raise
    multi_ui.accumulate_usage(MagicMock())


def test_multi_ui_accumulate_usage_swallows_child_errors(multi_ui, child_ui_1):
    bad_child = MagicMock()
    bad_child.accumulate_usage = MagicMock(side_effect=RuntimeError("bad"))
    good_child = MagicMock()
    good_child.accumulate_usage = MagicMock()
    multi_ui = MultiUI([bad_child, good_child])

    # Should not raise even though bad_child throws
    multi_ui.accumulate_usage(MagicMock())

    good_child.accumulate_usage.assert_called_once()


def test_multi_ui_set_thinking_mirrors_to_children(multi_ui, child_ui_1, child_ui_2):
    multi_ui.set_thinking(True)
    assert multi_ui.is_thinking is True
    assert child_ui_1.is_thinking is True
    assert child_ui_2.is_thinking is True

    multi_ui.set_thinking(False)
    assert multi_ui.is_thinking is False
    assert child_ui_1.is_thinking is False
    assert child_ui_2.is_thinking is False


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


@pytest.mark.asyncio
async def test_multi_ui_ask_user_race(multi_ui, child_ui_1, child_ui_2):
    # Make child_ui_1 slower
    async def slow_ask(*args, **kwargs):
        await asyncio.sleep(0.1)
        return "input 1"

    child_ui_1.ask_user = slow_ask

    # Make child_ui_2 faster
    async def fast_ask(*args, **kwargs):
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
