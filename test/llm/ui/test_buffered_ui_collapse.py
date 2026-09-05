"""Tests for `zrb.llm.ui.buffered_ui`.

Split out of `test/llm/tool/test_delegate_tool.py` in 2.58.0, when `BufferedUI`
moved out of the tool module it was embedded in. `delegate` is still its only
caller, but the mirror rule puts a test at its source's path.
"""

from unittest.mock import MagicMock

from zrb.llm.ui.buffered_ui import BufferedUI


def test_append_toggle_block_shows_collapsed_by_default():
    ui = BufferedUI(MagicMock())

    ui.append_toggle_block("short", "much longer full text")

    assert "short" in ui.get_buffered_output()
    assert "much longer full text" not in ui.get_buffered_output()
    assert len(ui.rendered_blocks) == 1


def test_append_toggle_block_skips_tracking_when_variants_match():
    ui = BufferedUI(MagicMock())

    ui.append_toggle_block("same", "same")

    assert ui.get_buffered_output() == "same"
    assert ui.rendered_blocks == []


def test_toggle_collapsible_block_at_offset_expands_then_collapses():
    ui = BufferedUI(MagicMock())
    ui.append_toggle_block("short", "much longer full text")

    toggled = ui.toggle_collapsible_block_at_offset(len(ui.get_buffered_output()))
    expanded = ui.get_buffered_output()
    toggled_again = ui.toggle_collapsible_block_at_offset(len(ui.get_buffered_output()))
    collapsed_again = ui.get_buffered_output()

    assert toggled is True
    assert "much longer full text" in expanded
    assert toggled_again is True
    assert "short" in collapsed_again
    assert "much longer full text" not in collapsed_again


def test_toggle_collapsible_block_at_offset_returns_false_without_a_block():
    ui = BufferedUI(MagicMock())
    ui.append_to_output("plain text, no toggle blocks", end="")

    assert ui.toggle_collapsible_block_at_offset(5) is False


def test_toggle_collapsible_block_at_offset_shifts_later_blocks():
    """Toggling an earlier block must keep a later block's offsets correct."""
    ui = BufferedUI(MagicMock())
    ui.append_toggle_block("first", "first EXPANDED")
    ui.append_to_output("between", end="")
    ui.append_toggle_block("second", "second EXPANDED")

    second_block = ui.rendered_blocks[1]
    expected_second_text = ui.get_buffered_output()[second_block[0] : second_block[1]]

    toggled = ui.toggle_collapsible_block_at_offset(0)

    assert toggled is True
    assert (
        ui.get_buffered_output()[second_block[0] : second_block[1]]
        == expected_second_text
    )


def test_mark_and_collapse_thinking_block_wraps_the_streamed_span():
    """Thinking streams live (nothing withheld); collapse_thinking_block
    retroactively wraps that already-printed span, using the caller-supplied
    `full` text — same contract as UIOutput.collapse_thinking_block."""
    ui = BufferedUI(MagicMock())
    ui.append_to_output("before ", end="")
    ui.mark_thinking_block_start()
    ui.append_to_output("a long stream of live thinking text", end="")

    collapsed = ui.collapse_thinking_block(
        "🧠 Thought\n", "a long stream of live thinking text"
    )

    assert collapsed is True
    assert "a long stream of live thinking text" not in ui.get_buffered_output()
    assert "🧠 Thought" in ui.get_buffered_output()
    assert len(ui.rendered_blocks) == 1

    ui.toggle_collapsible_block_at_offset(len(ui.get_buffered_output()))
    assert ui.get_buffered_output().startswith("before ")
    assert "a long stream of live thinking text" in ui.get_buffered_output()


def test_collapse_thinking_block_ignores_buffer_mangled_by_carriage_return():
    """Regression: the passed-in `full` must win even when the *rendered*
    span no longer matches it (a stray \\r rewrote part of the live line via
    merge_output_chunk, the same function UIOutput.append_to_output uses)."""
    ui = BufferedUI(MagicMock())
    ui.mark_thinking_block_start()
    ui.append_to_output("first part\rsecond part", end="")
    assert "first part" not in ui.get_buffered_output()

    collapsed = ui.collapse_thinking_block("🧠 Thought\n", "first part second part")
    ui.toggle_collapsible_block_at_offset(len(ui.get_buffered_output()))

    assert collapsed is True
    assert "first part" in ui.get_buffered_output()
    assert "second part" in ui.get_buffered_output()


def test_collapse_thinking_block_without_a_mark_is_a_noop():
    ui = BufferedUI(MagicMock())
    ui.append_to_output("no marked thinking block here", end="")

    assert ui.collapse_thinking_block("🧠 Thought\n", "thinking text") is False
    assert ui.get_buffered_output() == "no marked thinking block here"


def test_collapse_thinking_block_without_full_text_is_a_noop():
    ui = BufferedUI(MagicMock())
    ui.mark_thinking_block_start()

    assert ui.collapse_thinking_block("🧠 Thought\n", "") is False


def test_toggle_collapsible_block_at_offset_leaves_state_unchanged_on_stale_span():
    """A stale recorded span must not flip `expanded` or move the tracked
    offsets — a later toggle should retry cleanly, not work from corrupted
    bookkeeping."""
    ui = BufferedUI(MagicMock())
    ui.append_toggle_block("short", "much longer full text")

    block = ui.rendered_blocks[0]
    block[1] = len(ui.get_buffered_output()) + 100  # simulate a stale span

    result = ui.toggle_collapsible_block_at_offset(len(ui.get_buffered_output()))

    assert result is False
    assert block[2].expanded is False
    assert "much longer full text" not in ui.get_buffered_output()


def test_clear_buffer_resets_toggle_state():
    ui = BufferedUI(MagicMock())
    ui.mark_thinking_block_start()
    ui.append_toggle_block("short", "full")

    ui.clear_buffer()

    assert ui.rendered_blocks == []
    # No leftover mark survives the clear: collapsing without a fresh
    # mark_thinking_block_start() call afterward must be a no-op.
    assert ui.collapse_thinking_block("🧠 Thought\n", "some text") is False


def test_mark_and_collapse_text_block_wraps_the_streamed_span():
    """mark_text_block_start/collapse_text_block are the final-text
    counterpart to the thinking pair — same mechanics, reused via
    _collapse_collapsible_block."""
    ui = BufferedUI(MagicMock())
    ui.append_to_output("before ", end="")
    ui.mark_text_block_start()
    ui.append_to_output("the assistant's streamed final response", end="")

    collapsed = ui.collapse_text_block(
        "💬 Response\n", "the assistant's streamed final response"
    )

    assert collapsed is True
    assert "the assistant's streamed final response" not in ui.get_buffered_output()
    assert "💬 Response" in ui.get_buffered_output()
    assert len(ui.rendered_blocks) == 1

    ui.toggle_collapsible_block_at_offset(len(ui.get_buffered_output()))
    assert ui.get_buffered_output().startswith("before ")
    assert "the assistant's streamed final response" in ui.get_buffered_output()


def test_collapse_text_block_without_a_mark_is_a_noop():
    ui = BufferedUI(MagicMock())
    ui.append_to_output("no marked text block here", end="")

    assert ui.collapse_text_block("💬 Response\n", "response text") is False
    assert ui.get_buffered_output() == "no marked text block here"


def test_clear_buffer_resets_toggle_state_for_text_block_too():
    ui = BufferedUI(MagicMock())
    ui.mark_text_block_start()
    ui.append_toggle_block("short", "full")

    ui.clear_buffer()

    assert ui.rendered_blocks == []
    assert ui.collapse_text_block("💬 Response\n", "some text") is False


def test_update_tool_prepare_second_call_replaces_in_place():
    ui = BufferedUI(MagicMock())

    ui.update_tool_prepare("call_1", "🔄 Prepare tool parameters...")
    ui.update_tool_prepare("call_1", "🔄 Prepare tool parameters ⠋")

    assert ui.get_buffered_output().count("Prepare tool parameters") == 1
    assert "⠋" in ui.get_buffered_output()


def test_update_tool_prepare_empty_text_erases_and_stops_tracking():
    ui = BufferedUI(MagicMock())

    ui.update_tool_prepare("call_1", "🔄 Prepare tool parameters...")
    ui.update_tool_prepare("call_1", "")

    assert "Prepare tool parameters" not in ui.get_buffered_output()
    ui.update_tool_prepare("call_1", "")  # second erase must be a no-op


def test_update_tool_prepare_keeps_each_tool_calls_own_line_independent():
    """Regression: two tool calls preparing arguments concurrently must never
    corrupt each other's line — the bug the old `\\r`-erase-last-line trick
    had. Erasing the first must shift, not invalidate, the second's span."""
    ui = BufferedUI(MagicMock())

    ui.update_tool_prepare("call_A", "🔄 Prepare tool parameters...")
    ui.update_tool_prepare("call_B", "🔄 Prepare tool parameters...")
    ui.update_tool_prepare("call_A", "")
    ui.append_toggle_block("🧰 call_A | ToolA {}", "🧰 call_A | ToolA {}")
    ui.update_tool_prepare("call_B", "")

    assert "Prepare tool parameters" not in ui.get_buffered_output()
    assert "call_A | ToolA" in ui.get_buffered_output()


def test_clear_buffer_resets_tool_prepare_spans():
    ui = BufferedUI(MagicMock())
    ui.update_tool_prepare("call_1", "🔄 Prepare tool parameters...")

    ui.clear_buffer()

    # No leftover span survives the clear: a stray update for the same key
    # must start fresh (append) rather than try to replace a now-meaningless
    # offset into the cleared buffer.
    ui.update_tool_prepare("call_1", "🔄 Prepare tool parameters ⠋")
    assert ui.get_buffered_output().count("Prepare tool parameters") == 1


def test_update_shell_output_second_call_replaces_with_the_grown_text():
    ui = BufferedUI(MagicMock())

    ui.update_shell_output("cmd_1", "line one")
    ui.update_shell_output("cmd_1", "line one\nline two")

    assert ui.get_buffered_output().count("line one") == 1
    assert "line two" in ui.get_buffered_output()


def test_finish_shell_output_collapses_and_registers_for_toggle():
    ui = BufferedUI(MagicMock())
    ui.append_to_output("before ", end="")
    ui.update_shell_output("cmd_1", "line one\nline two")

    collapsed = ui.finish_shell_output("cmd_1", "🖥️ Output", "line one\nline two")

    assert collapsed is True
    assert "line one" not in ui.get_buffered_output()
    assert "🖥️ Output" in ui.get_buffered_output()
    assert len(ui.rendered_blocks) == 1

    ui.toggle_collapsible_block_at_offset(len(ui.get_buffered_output()))
    assert ui.get_buffered_output().startswith("before ")
    assert "line one" in ui.get_buffered_output()


def test_finish_shell_output_without_any_update_is_a_noop():
    ui = BufferedUI(MagicMock())
    ui.append_to_output("no shell output line here", end="")

    assert ui.finish_shell_output("cmd_1", "🖥️ Output", "text") is False
    assert ui.get_buffered_output() == "no shell output line here"


def test_shell_output_keeps_each_commands_own_line_independent_while_growing():
    """Regression, the actual bug reported: two shell commands running in
    parallel had their interleaved live output collapse into ONE block,
    silently swallowing one command's lines. Each `update_shell_output`
    call replaces exactly that command's own span, the same way
    `update_tool_prepare` already handles interleaved argument streams."""
    ui = BufferedUI(MagicMock())

    ui.update_shell_output("cmd_A", "dog 1")
    ui.update_shell_output("cmd_B", "cat 1")
    ui.update_shell_output("cmd_A", "dog 1\ndog 2")
    ui.update_shell_output("cmd_B", "cat 1\ncat 2")
    finished_a = ui.finish_shell_output("cmd_A", "🖥️ A", "dog 1\ndog 2")
    finished_b = ui.finish_shell_output("cmd_B", "🖥️ B", "cat 1\ncat 2")

    assert finished_a is True
    assert finished_b is True
    assert "dog" not in ui.get_buffered_output()
    assert "cat" not in ui.get_buffered_output()
    assert "🖥️ A" in ui.get_buffered_output() and "🖥️ B" in ui.get_buffered_output()
    assert len(ui.rendered_blocks) == 2
    fulls = {block[2].full for block in ui.rendered_blocks}
    assert any("dog 1" in f and "dog 2" in f for f in fulls)
    assert any("cat 1" in f and "cat 2" in f for f in fulls)


def test_clear_buffer_resets_shell_output_spans():
    ui = BufferedUI(MagicMock())
    ui.update_shell_output("cmd_1", "text")

    ui.clear_buffer()

    assert ui.finish_shell_output("cmd_1", "🖥️ Output", "text") is False
