"""Tests for `zrb.llm.ui.buffered_ui`.

Split out of `test/llm/tool/test_delegate_tool.py` in 2.58.0, when `BufferedUI`
moved out of the tool module it was embedded in. `delegate` is still its only
caller, but the mirror rule puts a test at its source's path.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.ui.buffered_ui import BufferedUI


# BufferedUI Tests
def test_buffered_ui_append_to_output():
    """Test BufferedUI buffers output correctly."""
    mock_wrapped = MagicMock()
    ui = BufferedUI(mock_wrapped, prefix="[AGENT] ")

    ui.append_to_output("Line 1")
    ui.append_to_output("Line 2")

    # Output should be buffered, not written yet
    # append_to_output adds end="\n" by default, so we get "Line 1\n" and "Line 2\n"
    buffered = ui.get_buffered_output()
    assert "Line 1" in buffered
    assert "Line 2" in buffered
    # Nothing should be written to wrapped UI yet
    assert mock_wrapped.append_to_output.call_count == 0


def test_buffered_ui_flush_to_parent():
    """Test BufferedUI flush_to_parent with prefix."""
    mock_wrapped = MagicMock()
    ui = BufferedUI(mock_wrapped, prefix="[AGENT] ")

    ui.append_to_output("Line 1\nLine 2")
    ui.flush_to_parent()

    # Should have called append_to_output with prefixed content
    assert mock_wrapped.append_to_output.call_count == 1
    # Check that the call contains the prefixed lines
    call_arg = mock_wrapped.append_to_output.call_args[0][0]
    assert "[AGENT]" in call_arg


def test_buffered_ui_clear_buffer():
    """Test BufferedUI clear_buffer clears output."""
    mock_wrapped = MagicMock()
    ui = BufferedUI(mock_wrapped, prefix="[AGENT] ")

    ui.append_to_output("Some content")
    assert "Some content" in ui.get_buffered_output()

    ui.clear_buffer()
    assert ui.get_buffered_output() == ""


@pytest.mark.asyncio
async def test_buffered_ui_ask_user():
    """Test BufferedUI ask_user forwards to parent with prefix."""
    mock_wrapped = MagicMock()
    mock_wrapped.ask_user = AsyncMock(return_value="user response")
    ui = BufferedUI(mock_wrapped, prefix="[AGENT] ")

    result = await ui.ask_user("What should I do?")

    assert result == "user response"
    mock_wrapped.ask_user.assert_called_once()
    # Check prefix was added
    call_arg = mock_wrapped.ask_user.call_args[0][0]
    assert "[AGENT]" in call_arg
    assert "What should I do?" in call_arg


@pytest.mark.asyncio
async def test_buffered_ui_ask_user_no_prefix():
    """Test BufferedUI ask_user without prefix."""
    mock_wrapped = MagicMock()
    mock_wrapped.ask_user = AsyncMock(return_value="response")
    ui = BufferedUI(mock_wrapped, prefix="")

    result = await ui.ask_user("Question?")

    assert result == "response"
    # No prefix should be added
    mock_wrapped.ask_user.assert_called_with("Question?", agent_id=None)


@pytest.mark.asyncio
async def test_buffered_ui_ask_user_does_not_flush_the_buffer():
    """Only the approval prompt itself reaches main -- ask_user must not dump
    the sub-agent's preceding buffered output alongside it."""
    mock_wrapped = MagicMock()
    mock_wrapped.ask_user = AsyncMock(return_value="user response")
    ui = BufferedUI(mock_wrapped, prefix="[AGENT] ")
    ui.append_to_output("buffered search result")

    await ui.ask_user("Approve this?")

    # ask_user itself is the only call — no separate flush call beforehand.
    mock_wrapped.ask_user.assert_called_once()
    assert ui.get_buffered_output() == "buffered search result\n"


@pytest.mark.asyncio
async def test_buffered_ui_ask_user_choice_forwards_without_flushing():
    """ask_user_choice forwards the prompt to parent, but does NOT flush the
    buffer first -- only the approval prompt itself reaches main; the
    sub-agent's routine buffered output stays in its own buffer, visible only
    by navigating into that sub-agent's live view."""
    mock_wrapped = MagicMock()
    mock_wrapped.ask_user_choice = AsyncMock(return_value="option-a")
    ui = BufferedUI(mock_wrapped, prefix="[AGENT] ")
    ui.append_to_output("buffered line")

    spec = MagicMock()
    result = await ui.ask_user_choice(spec)

    assert result == "option-a"
    mock_wrapped.ask_user_choice.assert_awaited_once_with(spec, agent_id=None)
    mock_wrapped.append_to_output.assert_not_called()
    # The buffered content is untouched, still available for on-demand viewing.
    assert ui.get_buffered_output() == "buffered line\n"


@pytest.mark.asyncio
async def test_buffered_ui_ask_user_stamps_own_agent_id():
    """ask_user tags the request with this instance's own agent id, so the
    root confirmation queue can route an answer back to whichever agent's
    live view the user is looking at."""
    mock_wrapped = MagicMock()
    mock_wrapped.ask_user = AsyncMock(return_value="user response")
    ui = BufferedUI(mock_wrapped)
    ui.set_activity_id("agent-123")

    await ui.ask_user("Approve?")

    assert mock_wrapped.ask_user.call_args.kwargs["agent_id"] == "agent-123"


@pytest.mark.asyncio
async def test_buffered_ui_ask_user_preserves_nested_agent_id():
    """A nested delegation (a sub-agent's own sub-agent) must not relabel the
    request as belonging to the intermediate layer -- the originating agent's
    id is preserved all the way to the root queue."""
    mock_wrapped = MagicMock()
    mock_wrapped.ask_user = AsyncMock(return_value="user response")
    ui = BufferedUI(mock_wrapped)
    ui.set_activity_id("intermediate-agent")

    await ui.ask_user("Approve?", agent_id="deepest-agent")

    assert mock_wrapped.ask_user.call_args.kwargs["agent_id"] == "deepest-agent"


@pytest.mark.asyncio
async def test_buffered_ui_ask_user_choice_stamps_own_agent_id():
    mock_wrapped = MagicMock()
    mock_wrapped.ask_user_choice = AsyncMock(return_value="option-a")
    ui = BufferedUI(mock_wrapped)
    ui.set_activity_id("agent-123")

    spec = MagicMock()
    await ui.ask_user_choice(spec)

    assert mock_wrapped.ask_user_choice.call_args.kwargs["agent_id"] == "agent-123"


@pytest.mark.asyncio
async def test_buffered_ui_shared_lock_does_not_block_sibling_enqueue():
    """Regression: a shared lock across fan-out sibling agents (delegate.py's
    `_run_parallel`) must not serialize the ENTIRE approval round-trip -- only
    the synchronous parent-transcript write may briefly contend for it. Each
    sibling's wait for the human's answer must happen outside the lock, so a
    sibling whose own request arrives second can still reach the shared
    confirmation queue (and be answered) while the first sibling's request is
    still unresolved. Previously the lock wrapped the whole call, so the
    second sibling never even reached `ask_user` on the wrapped UI until the
    first was answered -- picking it via the sub-agent picker had nothing of
    its own to resolve yet."""

    class SlowWrappedUI:
        def __init__(self):
            self.calls = []
            self.futures = {}

        def append_to_output(self, *args, **kwargs):
            pass

        async def ask_user(self, prompt, agent_id=None):
            self.calls.append(agent_id)
            fut = asyncio.get_running_loop().create_future()
            self.futures[agent_id] = fut
            return await fut

    wrapped = SlowWrappedUI()
    lock = asyncio.Lock()
    ui_a = BufferedUI(wrapped, shared_lock=lock)
    ui_a.set_activity_id("a")
    ui_b = BufferedUI(wrapped, shared_lock=lock)
    ui_b.set_activity_id("b")

    task_a = asyncio.create_task(ui_a.ask_user("", output_to_parent="approve a?"))
    await asyncio.sleep(0.01)
    task_b = asyncio.create_task(ui_b.ask_user("", output_to_parent="approve b?"))
    await asyncio.sleep(0.01)

    # Both siblings reached the wrapped UI's ask_user -- neither blocked
    # waiting on the shared lock for the other's still-pending answer.
    assert set(wrapped.calls) == {"a", "b"}

    # The second sibling ("b") can be answered before the first ("a").
    wrapped.futures["b"].set_result("y")
    assert await task_b == "y"
    assert not task_a.done()

    wrapped.futures["a"].set_result("y")
    assert await task_a == "y"


@pytest.mark.asyncio
async def test_buffered_ui_run_interactive_command_forwards():
    """run_interactive_command passes straight through to the wrapped UI."""
    mock_wrapped = MagicMock()
    mock_wrapped.run_interactive_command = AsyncMock(return_value="cmd-output")
    ui = BufferedUI(mock_wrapped)

    result = await ui.run_interactive_command("ls", shell=True)

    assert result == "cmd-output"
    mock_wrapped.run_interactive_command.assert_awaited_once_with("ls", True)


@pytest.mark.asyncio
async def test_buffered_ui_run_async_forwards():
    """run_async passes straight through to the wrapped UI."""
    mock_wrapped = MagicMock()
    mock_wrapped.run_async = AsyncMock(return_value="async-result")
    ui = BufferedUI(mock_wrapped)

    result = await ui.run_async()

    assert result == "async-result"
    mock_wrapped.run_async.assert_awaited_once()


def test_buffered_ui_flush_to_parent_without_prefix():
    """With no prefix, flush writes the raw buffered output verbatim."""
    mock_wrapped = MagicMock()
    ui = BufferedUI(mock_wrapped, prefix="")
    ui.append_to_output("raw line")

    ui.flush_to_parent()

    mock_wrapped.append_to_output.assert_called_once()
    assert mock_wrapped.append_to_output.call_args[0][0] == "raw line\n"


def test_buffered_ui_yolo_delegates_to_wrapped():
    """yolo reads through to the wrapped UI when it exposes the attribute."""

    class _Parent:
        yolo = True

    ui = BufferedUI(_Parent())
    assert ui.yolo is True


def test_buffered_ui_yolo_defaults_false_when_absent():
    """yolo defaults to False when the wrapped UI has no yolo attribute."""

    class _Parent:
        pass

    ui = BufferedUI(_Parent())
    assert ui.yolo is False


def test_buffered_ui_append_to_output_updates_activity_registry():
    """When an activity id is set, buffered writes also feed the activity panel."""
    mock_wrapped = MagicMock()
    ui = BufferedUI(mock_wrapped)
    ui.set_activity_id("agent-123")

    with patch("zrb.llm.ui.buffered_ui.agent_activity_registry") as reg:
        ui.append_to_output("line")

    reg.update.assert_called_once()
    assert reg.update.call_args[0][0] == "agent-123"


def test_buffered_ui_stream_to_parent_routes_into_own_buffer():
    """stream_to_parent no longer bypasses straight to the parent UI -- that
    was the noise-in-main bug (interim status notices leaking sub-agent
    chatter into the main transcript). It now lands in this sub-agent's own
    buffer (visible on demand, via get_buffered_output/entering its live
    view) and still feeds the activity registry, but must not touch the
    wrapped parent UI at all."""
    mock_wrapped = MagicMock()
    ui = BufferedUI(mock_wrapped, prefix="[AGENT] ")
    ui.set_activity_id("agent-xyz")

    with patch("zrb.llm.ui.buffered_ui.agent_activity_registry") as reg:
        ui.stream_to_parent("first\nsecond")

    reg.update.assert_called_once()
    mock_wrapped.append_to_output.assert_not_called()
    assert ui.get_buffered_output() == "first\nsecond\n"


def test_buffered_ui_passes_its_session_id_to_activity_updates():
    """Item 4, Phase D: the session that started this delegation must scope
    every activity-registry update, so a process hosting multiple sessions
    doesn't bleed one session's activity into another's."""
    mock_wrapped = MagicMock()
    ui = BufferedUI(mock_wrapped, session_id="session-42")
    ui.set_activity_id("agent-123")

    with patch("zrb.llm.ui.buffered_ui.agent_activity_registry") as reg:
        ui.append_to_output("line")
        ui.stream_to_parent("status")

    assert reg.update.call_args_list[0].kwargs["session_id"] == "session-42"
    assert reg.update.call_args_list[1].kwargs["session_id"] == "session-42"


def test_buffered_ui_defaults_to_empty_session_id():
    """No session_id passed -> default bucket, matching the pre-Phase-D
    single-session behavior every existing caller relies on."""
    mock_wrapped = MagicMock()
    ui = BufferedUI(mock_wrapped)
    ui.set_activity_id("agent-123")

    with patch("zrb.llm.ui.buffered_ui.agent_activity_registry") as reg:
        ui.append_to_output("line")

    assert reg.update.call_args.kwargs["session_id"] == ""


# --- Toggle-block tracking (Ctrl+O expand/collapse in the sub-agent view) --
# Independently scoped from UIOutput.rendered_blocks (the main transcript's) —
# see BufferedUI.append_toggle_block's docstring. Mirrors the coverage in
# test/llm/ui/default/test_output.py's own toggle-block tests.


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
    _merge_output_chunk, the same function UIOutput.append_to_output uses)."""
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
