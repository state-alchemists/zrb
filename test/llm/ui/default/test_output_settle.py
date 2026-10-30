"""A text block a tool call ends is prose, not the answer.

`collapse_text_block` is for the turn's final reply: it hides the streamed copy
behind a `💬 Response (N chars)` hint because `BaseUI.stream_ai_response`
renders that answer separately. A block a following part ends is not that
answer, so `settle_text_block` rebuilds it in place and leaves it readable.
"""

from unittest.mock import MagicMock, PropertyMock, patch

from pydantic_ai import ToolCallPart
from pydantic_ai.messages import TextPart

from zrb.llm.agent.run.setup import setup_print_and_events
from zrb.llm.ui.base.confirmation_state import BaseUIConfirmationState
from zrb.llm.ui.default.output import UIOutput
from zrb.llm.util.stream_response import CONTINUATION_PAD
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


def test_settle_text_block_keeps_the_marker_above_the_rendered_prose():
    """The marker stays as a header, and the prose is rendered underneath it."""
    ui = SettleUI()

    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.append_to_output("before\n", end="")
        ui.mark_text_block_start()
        ui.append_to_output("\n  💬 read **the file** first", end="", kind="streaming")
        ui.settle_text_block("read **the file** first")

    text = remove_style(ui.output_text)
    marker = "💬 Response (23 chars)"
    assert text.count(marker) == 1
    # The marker has a line to itself, and the prose starts on the next one.
    assert f"\n{marker}\n" in text
    assert text.endswith("\nread the file first")
    # Markdown-rendered under the marker, not the raw source, and not indented.
    assert "**the file**" not in text
    # One registration: the fold and the resize re-render share it, and the
    # painted form is the open one.
    assert len(ui.rendered_blocks) == 1
    start, end, source, _renderer = ui.rendered_blocks[0]
    from zrb.llm.ui.output_chunk import CollapsibleBlockSource

    assert isinstance(source, CollapsibleBlockSource)
    assert source.expanded is True
    assert remove_style(source.collapsed).endswith(marker)
    assert remove_style(source.full).endswith("\nread the file first")


def test_settled_prose_keeps_the_column_it_streamed_at():
    """The block settles in place, so its lines do not jump to the margin.

    The marker takes the line the icon led; the prose keeps the column its
    wrapped lines already had — the handler hands that column over, because a
    markdown renderer would read it as a code block if it came with the text.
    """
    ui = SettleUI()
    _print_fn, handler = setup_print_and_events(None, None, ui)
    continuation = f"{handler.indentation}{CONTINUATION_PAD}"

    with patch.object(ui.output_part, "schedule_invalidate"):
        opening = MagicMock()
        opening.part = TextPart(content="read the file first")
        handler.handle_part_start(opening)

        call = MagicMock()
        call.part = ToolCallPart(tool_name="Read", args={}, tool_call_id="c1")
        handler.handle_part_start(call)

    text = remove_style(ui.output_text)
    assert f"\n💬 Response (19 chars)\n{continuation}read the file first" in text


def test_settled_prose_wraps_inside_the_field_it_is_indented_into():
    """The render narrows by the indent, so no line runs past the field.

    Rendering at the full width and indenting afterwards leaves every wrapped
    line five columns too long: the terminal wraps it again, or clips it.
    """
    ui = SettleUI()
    _print_fn, handler = setup_print_and_events(None, None, ui)
    continuation = f"{handler.indentation}{CONTINUATION_PAD}"
    words = " ".join(f"word{index}" for index in range(40))

    with patch.object(ui.output_part, "schedule_invalidate"), patch.object(
        type(ui.output_part),
        "output_field_width",
        new_callable=PropertyMock,
        create=True,
        return_value=40,
    ):
        opening = MagicMock()
        opening.part = TextPart(content=words)
        handler.handle_part_start(opening)

        call = MagicMock()
        call.part = ToolCallPart(tool_name="Read", args={}, tool_call_id="c1")
        handler.handle_part_start(call)

    prose = [
        line
        for line in remove_style(ui.output_text).split("\n")
        if line.startswith(continuation)
    ]
    assert len(prose) > 1, "the text has to wrap for this to mean anything"
    assert all(len(line) <= 40 for line in prose)


def test_ctrl_o_folds_the_settled_prose_back_to_its_marker():
    """Painted open, so the prose reads at once; Ctrl+O folds it to the marker."""
    ui = SettleUI()

    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.append_to_output("before\n", end="")
        ui.mark_text_block_start()
        ui.append_to_output("\n  💬 read it", end="", kind="streaming")
        ui.settle_text_block("read it")

    ui.output_field.buffer.cursor_position = len(ui.output_text)
    assert ui.toggle_collapsible_block_at_cursor() is True
    folded = remove_style(ui.output_text)
    assert folded.endswith("💬 Response (7 chars)")
    assert "read it" not in folded

    ui.output_field.buffer.cursor_position = len(ui.output_text)
    assert ui.toggle_collapsible_block_at_cursor() is True
    assert remove_style(ui.output_text).endswith("\nread it")


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
