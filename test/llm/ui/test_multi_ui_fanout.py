import asyncio
from unittest.mock import AsyncMock, MagicMock

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


def test_multi_ui_record_tool_call_block_uses_child_recorder_when_supported(
    multi_ui, child_ui_1, child_ui_2
):
    """A toggle-capable child (the default TUI) gets real tracking; a child
    without that support (Telegram/SSE-shaped) still gets the collapsed line
    via a plain append_to_output — exactly what it would have received via
    `fprint` before this feature existed."""
    child_ui_1.record_tool_call_block = MagicMock()
    del child_ui_2.record_tool_call_block

    multi_ui.record_tool_call_block("collapsed", "full")

    child_ui_1.record_tool_call_block.assert_called_once_with("collapsed", "full")
    child_ui_1.append_to_output.assert_not_called()
    child_ui_2.append_to_output.assert_called_once_with(
        "collapsed", end="", kind="tool_call"
    )


def test_multi_ui_record_tool_call_block_falls_back_when_no_child_supports_it(
    multi_ui, child_ui_1, child_ui_2
):
    """Dual-mode with no toggle-capable child at all (e.g. paired with a
    non-default UI): every child must still receive the collapsed line, not
    silence — this is the regression the fan-out-or-fallback design exists
    to prevent."""
    del child_ui_1.record_tool_call_block
    del child_ui_2.record_tool_call_block

    multi_ui.record_tool_call_block("collapsed", "full")

    child_ui_1.append_to_output.assert_called_once_with(
        "collapsed", end="", kind="tool_call"
    )
    child_ui_2.append_to_output.assert_called_once_with(
        "collapsed", end="", kind="tool_call"
    )


def test_multi_ui_record_tool_call_block_swallows_child_errors(
    multi_ui, child_ui_1, child_ui_2
):
    del child_ui_1.record_tool_call_block
    child_ui_1.append_to_output = MagicMock(side_effect=RuntimeError("bad"))
    child_ui_2.record_tool_call_block = MagicMock()

    # Should not raise even though child_ui_1's append_to_output throws
    multi_ui.record_tool_call_block("collapsed", "full")

    child_ui_2.record_tool_call_block.assert_called_once_with("collapsed", "full")


def test_multi_ui_mark_thinking_block_start_forwards_to_supporting_children(
    multi_ui, child_ui_1, child_ui_2
):
    child_ui_1.mark_thinking_block_start = MagicMock()
    del child_ui_2.mark_thinking_block_start  # e.g. Telegram/SSE, no toggle support

    # Must not raise for the child that doesn't support it.
    multi_ui.mark_thinking_block_start()

    child_ui_1.mark_thinking_block_start.assert_called_once_with()


def test_multi_ui_collapse_thinking_block_forwards_to_supporting_children(
    multi_ui, child_ui_1, child_ui_2
):
    child_ui_1.collapse_thinking_block = MagicMock()
    del child_ui_2.collapse_thinking_block

    multi_ui.collapse_thinking_block("🧠 Thought\n", "the full thought")

    child_ui_1.collapse_thinking_block.assert_called_once_with(
        "🧠 Thought\n", "the full thought"
    )


def test_multi_ui_thinking_hooks_swallow_child_errors(multi_ui, child_ui_1, child_ui_2):
    child_ui_1.mark_thinking_block_start = MagicMock(side_effect=RuntimeError("bad"))
    child_ui_2.mark_thinking_block_start = MagicMock()

    # Should not raise even though child_ui_1 throws.
    multi_ui.mark_thinking_block_start()

    child_ui_2.mark_thinking_block_start.assert_called_once()


def test_multi_ui_mark_text_block_start_forwards_to_supporting_children(
    multi_ui, child_ui_1, child_ui_2
):
    child_ui_1.mark_text_block_start = MagicMock()
    del child_ui_2.mark_text_block_start  # e.g. Telegram/SSE, no toggle support

    # Must not raise for the child that doesn't support it.
    multi_ui.mark_text_block_start()

    child_ui_1.mark_text_block_start.assert_called_once_with()


def test_multi_ui_collapse_text_block_forwards_to_supporting_children(
    multi_ui, child_ui_1, child_ui_2
):
    child_ui_1.collapse_text_block = MagicMock()
    del child_ui_2.collapse_text_block

    multi_ui.collapse_text_block("💬 Response\n", "the full response")

    child_ui_1.collapse_text_block.assert_called_once_with(
        "💬 Response\n", "the full response"
    )


def test_multi_ui_text_hooks_swallow_child_errors(multi_ui, child_ui_1, child_ui_2):
    child_ui_1.mark_text_block_start = MagicMock(side_effect=RuntimeError("bad"))
    child_ui_2.mark_text_block_start = MagicMock()

    # Should not raise even though child_ui_1 throws.
    multi_ui.mark_text_block_start()

    child_ui_2.mark_text_block_start.assert_called_once()


def test_multi_ui_update_tool_prepare_forwards_to_supporting_children(
    multi_ui, child_ui_1, child_ui_2
):
    child_ui_1.update_tool_prepare = MagicMock()
    del child_ui_2.update_tool_prepare  # e.g. Telegram/SSE, no toggle support

    multi_ui.update_tool_prepare("call_1", "🔄 Prepare tool parameters...")

    child_ui_1.update_tool_prepare.assert_called_once_with(
        "call_1", "🔄 Prepare tool parameters..."
    )


def test_multi_ui_update_tool_prepare_swallows_child_errors(
    multi_ui, child_ui_1, child_ui_2
):
    child_ui_1.update_tool_prepare = MagicMock(side_effect=RuntimeError("bad"))
    child_ui_2.update_tool_prepare = MagicMock()

    multi_ui.update_tool_prepare("call_1", "🔄 Prepare tool parameters...")

    child_ui_2.update_tool_prepare.assert_called_once()


def test_multi_ui_update_shell_output_forwards_to_supporting_children(
    multi_ui, child_ui_1, child_ui_2
):
    child_ui_1.update_shell_output = MagicMock()
    del child_ui_2.update_shell_output  # e.g. Telegram/SSE

    multi_ui.update_shell_output("cmd_1", "line one")

    child_ui_1.update_shell_output.assert_called_once_with("cmd_1", "line one")


def test_multi_ui_finish_shell_output_forwards_to_supporting_children(
    multi_ui, child_ui_1, child_ui_2
):
    child_ui_1.finish_shell_output = MagicMock()
    del child_ui_2.finish_shell_output

    multi_ui.finish_shell_output("cmd_1", "🖥️ Output", "the full output")

    child_ui_1.finish_shell_output.assert_called_once_with(
        "cmd_1", "🖥️ Output", "the full output"
    )


def test_multi_ui_shell_output_hooks_swallow_child_errors(
    multi_ui, child_ui_1, child_ui_2
):
    child_ui_1.update_shell_output = MagicMock(side_effect=RuntimeError("bad"))
    child_ui_2.update_shell_output = MagicMock()

    multi_ui.update_shell_output("cmd_1", "line one")

    child_ui_2.update_shell_output.assert_called_once()


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
