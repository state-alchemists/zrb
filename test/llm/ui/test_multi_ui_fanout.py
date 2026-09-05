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


def test_append_to_output_broadcasts(mock_child_ui):
    """Test that append_to_output broadcasts to all child UIs."""
    other_ui = MagicMock()
    other_ui.append_to_output = MagicMock()
    multi_ui = MultiUI([mock_child_ui, other_ui])

    multi_ui.append_to_output("Test message")

    mock_child_ui.append_to_output.assert_called_once()
    other_ui.append_to_output.assert_called_once()


def test_append_to_output_handles_exception(mock_child_ui):
    """Test append_to_output handles exceptions from child UIs."""
    mock_child_ui.append_to_output = MagicMock(side_effect=Exception("Test"))
    multi_ui = MultiUI([mock_child_ui])

    # Should not raise
    multi_ui.append_to_output("Test message")


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


class TestMultiUIReplayHistory:
    """Tests for MultiUI broadcasting replay to child UIs."""

    def test_replay_history_broadcasts_to_children(self):
        """MultiUI.replay_history must call replay_history on every child."""
        child_a = MagicMock()
        child_b = MagicMock()
        multi_ui = MultiUI([child_a, child_b])

        messages = ["m1", "m2"]
        multi_ui.replay_history(messages)

        child_a.replay_history.assert_called_once_with(messages)
        child_b.replay_history.assert_called_once_with(messages)

    def test_replay_history_skips_children_without_method(self):
        """Children missing replay_history are silently skipped."""

        class NoReplayChild:
            def __init__(self):
                self._multi_ui_parent = None

        child = NoReplayChild()
        # Should not raise
        MultiUI([child]).replay_history(["m1"])

    def test_replay_history_swallows_child_errors(self):
        """A child raising must not break the broadcast to other children."""
        bad_child = MagicMock()
        bad_child.replay_history.side_effect = RuntimeError("bad")
        good_child = MagicMock()

        multi_ui = MultiUI([bad_child, good_child])
        # Should not raise even though bad_child throws
        multi_ui.replay_history(["m1"])

        good_child.replay_history.assert_called_once_with(["m1"])
