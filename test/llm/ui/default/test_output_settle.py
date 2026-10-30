"""A text block a tool call ends is prose, not the answer.

`collapse_text_block` is for the turn's final reply: it hides the streamed copy
behind a `💬 Response (N chars)` hint because `BaseUI.stream_ai_response`
renders that answer separately. A block a following part ends is not that
answer, so `settle_text_block` rebuilds it in place and leaves it readable.
"""

import os
from unittest.mock import MagicMock, PropertyMock, patch

from pydantic_ai import ToolCallPart
from pydantic_ai.messages import TextPart

from zrb.llm.agent.run.setup import setup_print_and_events
from zrb.llm.ui.base.confirmation_state import BaseUIConfirmationState
from zrb.llm.ui.base.ui import BaseUI
from zrb.llm.ui.default.output import UIOutput
from zrb.llm.util.stream_response import CONTINUATION_PAD, DEFAULT_STREAM_INDENTATION
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

    # The real `/btw` entry point, bound onto this stand-in so the transcript
    # test drives the code that runs in the chat instead of a copy of it.
    end_side_question = BaseUI.end_side_question

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
    column = DEFAULT_STREAM_INDENTATION
    assert text.count(marker) == 1
    # The marker has a line to itself, and the prose starts on the next one.
    assert f"\n{marker}\n" in text
    assert text.endswith(f"\n{column}read the file first")
    # Markdown-rendered under the marker, not the raw source, and in the column
    # the run's wrapped lines sit at.
    assert "**the file**" not in text
    # One registration: the fold and the resize re-render share it, and the
    # painted form is the open one.
    assert len(ui.rendered_blocks) == 1
    start, end, source, _renderer = ui.rendered_blocks[0]
    from zrb.llm.ui.output_chunk import CollapsibleBlockSource

    assert isinstance(source, CollapsibleBlockSource)
    assert source.expanded is True
    assert remove_style(source.collapsed).endswith(marker)
    assert remove_style(source.full).endswith(f"\n{column}read the file first")


def test_the_answer_keeps_the_column_the_run_streams_at():
    """The answer is appended where the streamed copy sat, not at the margin.

    The marker above it is the copy that collapsed, so an answer rendered at
    the margin jumps five columns left exactly when the turn ends — the block
    the reader was reading moves under them.
    """
    ui = SettleUI()
    _print_fn, handler = setup_print_and_events(None, None, ui)
    continuation = f"{handler.indentation}{CONTINUATION_PAD}"

    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.append_to_output("\n🤖 11:47 >>\n")
        ui.append_answer("Reading the file first.\n\nThen decide.")

    text = remove_style(ui.output_text)
    assert f"\n{continuation}Reading the file first." in text
    assert f"\n{continuation}Then decide." in text
    # Registered for re-rendering, so a resize keeps the column instead of
    # dropping the answer back to the margin.
    assert len(ui.rendered_blocks) == 1


def test_an_answer_lands_in_the_default_column_before_any_run_reports_one():
    """A replayed answer has no run behind it, and still sits in the column.

    `/load` replays a stored reply through `append_answer` while the session has
    not run yet, so nothing has reported a column. A transcript that starts at
    the margin draws every resumed answer five columns left of the one a live
    turn drew, which is the layout difference the funnel exists to remove.
    """
    ui = SettleUI()  # no handler, no run: nothing has set a column
    column = DEFAULT_STREAM_INDENTATION
    assert column == "     ", "the default layout's column is five spaces"

    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.append_to_output("\n🤖 11:47 >>\n")
        ui.append_answer("Resumed answer.\n\nSecond paragraph.")

    text = remove_style(ui.output_text)
    assert f"\n{column}Resumed answer." in text
    assert f"\n{column}Second paragraph." in text

    # A run that does report its own column still wins over the default.
    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.set_stream_indentation("       ")
        ui.append_answer("A deeper run's answer.")

    assert "\n       A deeper run's answer." in remove_style(ui.output_text)


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
    assert remove_style(ui.output_text).endswith(f"\n{DEFAULT_STREAM_INDENTATION}read it")


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


# A turn wide enough to wrap, narrow enough that the wrap is worth checking.
TURN_COLUMNS = 60
TURN_WIDTH = TURN_COLUMNS - 4  # what `output_field_width` subtracts
INTERMEDIATE = (
    "Let me look at the file before answering, because the answer depends on "
    "what it says, and a guess would be worse than a moment's wait."
)
ANSWER = (
    "The file is the answer.\n"
    "\n"
    "| name | value |\n"
    "| --- | --- |\n"
    "| alpha | one |\n"
    "\n"
    "```\n"
    "print('one indent, not two')\n"
    "```\n"
)
SIDE_ANSWER = "The side answer lands under its own header."
_MARKER_GLYPHS = ("🤖", "💭", "💬", "🔄", "⏳", "◌")


def test_a_whole_turn_keeps_every_prose_line_in_the_column(monkeypatch):
    """One rule for every piece of run prose, checked on the finished transcript.

    Driven through the real wiring — the handler for the block a tool call ends,
    and the entry points the answer, a `/btw` reply and a replay all use — rather
    than one assertion per path: a path added later that skips the funnel shows
    up here as a line at the margin, which is the failure the per-path tests
    could not see.
    """
    import zrb.llm.ui.default.output as output_module

    monkeypatch.setattr(
        output_module,
        "get_terminal_size",
        lambda *args, **kwargs: os.terminal_size((TURN_COLUMNS, 24)),
    )
    ui = SettleUI()
    _print_fn, handler = setup_print_and_events(None, None, ui)
    column = f"{handler.indentation}{CONTINUATION_PAD}"

    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.append_to_output("\n🤖 11:47 >>\n")
        opening = MagicMock()
        opening.part = TextPart(content=INTERMEDIATE)
        handler.handle_part_start(opening)
        call = MagicMock()
        call.part = ToolCallPart(tool_name="Read", args={}, tool_call_id="c1")
        handler.handle_part_start(call)
        ui.append_to_output("\n")
        ui.append_answer(ANSWER)
        ui.end_side_question(SIDE_ANSWER)

    text = remove_style(ui.output_text)
    prose = [
        line
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith(_MARKER_GLYPHS)
    ]
    assert prose, "the scripted turn produced no prose to check"
    for line in prose:
        assert line.startswith(column), f"run prose left the column: {line!r}"
        assert len(line) <= TURN_WIDTH, (
            f"line runs past the field ({len(line)} > {TURN_WIDTH}): {line!r}"
        )
    # A plain paragraph starts *exactly* at the column: a double indent passes a
    # bare `startswith` and fails here.
    assert f"{column}The file is the answer." in text
