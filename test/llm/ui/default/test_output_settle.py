"""A text block a tool call ends is prose, not the answer.

`collapse_text_block` is for the turn's final reply: it hides the streamed copy
behind a `💬 Response (N chars)` hint because `BaseUI.stream_ai_response`
renders that answer separately. A block a following part ends is not that
answer, so `settle_text_block` rebuilds it in place and leaves it readable.
"""

from unittest.mock import MagicMock, patch

from pydantic_ai import ToolCallPart
from pydantic_ai.messages import TextPart

from zrb.llm.agent.run.setup import setup_print_and_events
from zrb.llm.ui.base.confirmation_state import BaseUIConfirmationState
from zrb.llm.ui.default.output import UIOutput
from zrb.util.cli.style import remove_style


class _RecordingBuffer:
    """A prompt_toolkit `Buffer` stand-in that really stores its document."""

    def __init__(self, output_field):
        self._output_field = output_field
        self.cursor_position = 0

    @property
    def text(self):
        return self._output_field.text

    def set_document(self, document, bypass_readonly=False):
        self._output_field.text = document.text
        self.cursor_position = document.cursor_position


class _OutputField:
    def __init__(self):
        self.text = ""
        self.buffer = _RecordingBuffer(self)


class SettleUI:
    """Stand-in UI composing the real `UIOutput`, with a buffer that stores text.

    Holds the state `UIOutput` reaches via `self._ui` (normally supplied by the
    default `UI`) and forwards everything else to the composed part.
    """

    def __init__(self):
        self.output_field = _OutputField()
        self.confirmation = BaseUIConfirmationState()
        self.rendered_blocks = []
        self.rendered_width = None
        self.pending_invalidate = False
        self.invalidate_task = None
        self.markdown_theme = None
        self.is_thinking = False
        self.output_part = UIOutput(self)

    @property
    def output_text(self):
        return self.output_field.text

    @property
    def is_application_built(self):
        return False

    def invalidate_ui(self):
        pass

    def __getattr__(self, name):
        output = self.__dict__.get("output_part")
        if output is None:
            raise AttributeError(name)
        return getattr(output, name)


def test_settle_text_block_renders_the_prose_in_place_of_the_stream():
    """An intermediate block is rebuilt from its own text, not collapsed."""
    ui = SettleUI()

    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.append_to_output("before\n", end="")
        ui.mark_text_block_start()
        ui.append_to_output("\n  💬 read **the file** first", end="", kind="streaming")
        ui.settle_text_block("read **the file** first")

    assert "💬 Response" not in ui.output_text
    # Markdown-rendered, not the raw source, and not the stream's indentation.
    assert "**the file**" not in ui.output_text
    assert remove_style(ui.output_text).endswith("\n\nread the file first")
    assert len(ui.rendered_blocks) == 1
    # Tracked for resize re-wrap: re-rendering the recorded source lands back on
    # exactly the span the block covers — the separator stays outside it.
    start, end, source, renderer = ui.rendered_blocks[0]
    assert source == "read **the file** first"
    assert renderer(source, None) == ui.output_text[start:end]


def test_settle_text_block_without_a_mark_is_a_noop():
    ui = SettleUI()
    ui.output_field.text = "no marked text block here"

    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.settle_text_block("response text")

    assert ui.output_text == "no marked text block here"
    assert ui.rendered_blocks == []


def test_a_text_tool_text_run_leaves_the_first_text_readable_in_full():
    """The reported turn: text -> tool call -> text.

    The first text used to become a `💬 Response (N chars)` placeholder, so
    reading the transcript meant scrolling up to find prose that was no longer
    there. It is prose written before acting, not the answer — the answer is
    the final block, which `BaseUI.stream_ai_response` renders once.
    """
    ui = SettleUI()
    # The production wiring, exactly as `run_agent` builds it.
    _print_fn, handler = setup_print_and_events(None, None, ui)

    with patch.object(ui.output_part, "schedule_invalidate"):
        opening = MagicMock()
        opening.part = TextPart(content="I need to read **the file** first.")
        handler.handle_part_start(opening)

        call = MagicMock()
        call.part = ToolCallPart(
            tool_name="Read", args={"path": "a.txt"}, tool_call_id="call_1"
        )
        handler.handle_part_start(call)
        handler.handle_tool_call(call)

        closing = MagicMock()
        closing.part = TextPart(content="I have verified the file.")
        handler.handle_part_start(closing)

        result = MagicMock()
        result.result.usage = MagicMock()
        handler.handle_run_result(result)

        streamed = ui.output_text
        # What `BaseUI.stream_ai_response` appends when the turn returns.
        ui.append_markdown("I have verified the file.")
        answered = ui.output_text

    # The first text is readable in full, markdown-rendered.
    assert "I need to read the file first." in remove_style(streamed)
    assert "**the file**" not in streamed
    # The answer is not in the transcript twice: once collapsed, once rendered.
    assert "I have verified the file." not in streamed
    assert "💬 Response" in streamed
    assert remove_style(answered).count("I have verified the file.") == 1
    assert remove_style(answered).count("I need to read") == 1


def test_a_spoken_block_leaves_no_marker_on_screen():
    """`<spoken>` marks what is read aloud. The block's own words are on screen
    like any other prose, and neither marker is, on the whole streamed and
    settled path — the answer's own render is `test_base_ui_spoken.py`'s."""
    ui = SettleUI()
    _print_fn, handler = setup_print_and_events(None, None, ui)

    with patch.object(ui.output_part, "schedule_invalidate"):
        opening = MagicMock()
        opening.part = TextPart(content="<spoken>😊 Reading the file.</spoken>")
        handler.handle_part_start(opening)

        call = MagicMock()
        call.part = ToolCallPart(
            tool_name="Read", args={"path": "a.txt"}, tool_call_id="call_1"
        )
        handler.handle_part_start(call)
        handler.handle_tool_call(call)

        result = MagicMock()
        result.result.usage = MagicMock()
        handler.handle_run_result(result)

    screen = remove_style(ui.output_text)
    assert "spoken" not in screen
    assert "😊 Reading the file." in screen
