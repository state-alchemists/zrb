"""Tests for `zrb.llm.ui.buffered_ui`.

Split out of `test/llm/tool/test_delegate_tool.py` in 2.58.0, when `BufferedUI`
moved out of the tool module it was embedded in. `delegate` is still its only
caller, but the mirror rule puts a test at its source's path.
"""

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
    mock_wrapped.ask_user.assert_called_with("Question?")


@pytest.mark.asyncio
async def test_buffered_ui_ask_user_choice_flushes_and_forwards():
    """ask_user_choice flushes buffered output first, then forwards to parent."""
    mock_wrapped = MagicMock()
    mock_wrapped.ask_user_choice = AsyncMock(return_value="option-a")
    ui = BufferedUI(mock_wrapped, prefix="[AGENT] ")
    ui.append_to_output("buffered line")

    spec = MagicMock()
    result = await ui.ask_user_choice(spec)

    assert result == "option-a"
    mock_wrapped.ask_user_choice.assert_awaited_once_with(spec)
    # Buffered output was flushed to the parent before asking.
    mock_wrapped.append_to_output.assert_called()


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


def test_buffered_ui_stream_to_parent_prefixes_and_feeds_activity():
    """stream_to_parent bypasses the buffer, prefixes each non-empty line, and
    routes to the activity registry when an id is set."""
    mock_wrapped = MagicMock()
    ui = BufferedUI(mock_wrapped, prefix="[AGENT] ")
    ui.set_activity_id("agent-xyz")

    with patch("zrb.llm.ui.buffered_ui.agent_activity_registry") as reg:
        ui.stream_to_parent("first\nsecond")

    reg.update.assert_called_once()
    mock_wrapped.append_to_output.assert_called_once()
    streamed = mock_wrapped.append_to_output.call_args[0][0]
    assert "[AGENT] first" in streamed
    assert "[AGENT] second" in streamed
    # Streaming is immediate: nothing was left in the buffer.
    assert ui.get_buffered_output() == ""
