"""Verify held main-agent output replay after confirmation."""

import asyncio
from unittest.mock import patch

import pytest

from zrb.llm.ui.base.confirmation_state import BaseUIConfirmationState
from zrb.llm.ui.default.confirmation import UIConfirmation
from zrb.llm.ui.default.output import UIOutput
from zrb.util.cli.style import stylize_muted


class TextBuffer:
    """A prompt_toolkit `Buffer` stand-in that really stores its document."""

    def __init__(self):
        self.text = ""
        self.cursor_position = 0

    def set_document(self, document, bypass_readonly=False):
        self.text = document.text
        self.cursor_position = document.cursor_position


class TextOutputField:
    def __init__(self):
        self.buffer = TextBuffer()

    @property
    def text(self):
        return self.buffer.text


class StreamingConfirmationUI:
    """Holds the state both parts reach via `self._ui` (normally supplied by
    the default `UI`), with the main agent mid-stream."""

    def __init__(self):
        self.confirmation = BaseUIConfirmationState()
        self.output_field = TextOutputField()
        self.is_thinking = True
        self.rendered_blocks = []
        self.pending_invalidate = False
        self.invalidate_task = None
        self.output_part = UIOutput(self)
        self.confirmation_part = UIConfirmation(self)

    @property
    def output_text(self):
        return self.output_field.text

    def append_to_output(self, *values, **kwargs):
        self.output_part.append_to_output(*values, **kwargs)

    def resolve_current(self, text, echo):
        return self.confirmation_part.resolve_current(text, echo)

    def begin_choice(self, spec):
        pass

    def end_choice(self):
        pass

    def invalidate_ui(self):
        pass


@pytest.mark.asyncio
async def test_answer_echo_lands_before_output_held_during_the_confirmation():
    """The answer belongs right after its prompt. Main-agent output held while
    the prompt was pending is replayed after it, never in front of it."""
    ui = StreamingConfirmationUI()

    with patch("prompt_toolkit.application.get_app"):
        ui.append_to_output("The answer is", end="", kind="streaming")
        task = asyncio.create_task(ui.confirmation_part.ask_user("\nApprove? "))
        await asyncio.sleep(0)
        ui.append_to_output(" forty", end="", kind="streaming")
        ui.confirmation_part.submit_user_answer("y")
        assert await task == "y"

    assert ui.output_text.startswith("The answer is\nApprove? y\n")


@pytest.mark.asyncio
async def test_held_output_replays_as_written_into_the_open_block(monkeypatch):
    """Held chunks replay with their own `end` and `kind`: a streamed chunk
    rejoins its open response block (and collapses with it), a tool line
    keeps its muted style, and no newline is inserted between chunks."""
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("FORCE_COLOR", "1")
    ui = StreamingConfirmationUI()

    with patch("prompt_toolkit.application.get_app"):
        ui.output_part.mark_text_block_start()
        ui.append_to_output("The answer is", end="", kind="streaming")
        task = asyncio.create_task(ui.confirmation_part.ask_user("\nApprove? "))
        await asyncio.sleep(0)
        ui.append_to_output(" forty", end="", kind="streaming")
        ui.append_to_output("Read a.txt", kind="tool_call")
        ui.confirmation_part.submit_user_answer("y")
        assert await task == "y"
    ui.append_to_output("-two.", end="", kind="streaming")
    collapsed = ui.output_part.collapse_text_block(
        "[Response]", "The answer is forty-two."
    )

    assert collapsed is True
    assert ui.output_text == (
        stylize_muted("[Response]")
        + "\nApprove? "
        + "y\n"
        + stylize_muted("Read a.txt\n")
    )
