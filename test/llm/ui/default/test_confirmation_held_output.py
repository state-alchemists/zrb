"""Main-agent output held while a confirmation is pending, and its replay.

Composes the real `UIOutput` and `UIConfirmation` over a buffer that stores
text, so the hold and the replay both run through the real append path.
"""

import asyncio
from unittest.mock import patch

import pytest

from zrb.llm.ui.base.confirmation_state import BaseUIConfirmationState
from zrb.llm.ui.default.confirmation import UIConfirmation
from zrb.llm.ui.default.output import UIOutput


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
