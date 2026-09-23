"""Shared stand-in for the default UI's queued-message echo tests.

`MockEditingUI` composes the real `UIOutput` and `UIMessageEditing` over a
buffer that really stores text, so the offset bookkeeping those two keep is
exercised rather than mocked.
"""

from unittest.mock import MagicMock

import pytest

from zrb.llm.ui.base.confirmation_state import BaseUIConfirmationState
from zrb.llm.ui.default.message_editing import UIMessageEditing
from zrb.llm.ui.default.output import UIOutput


class MockEditingUI:
    """Stand-in UI composing the real `UIOutput` and `UIMessageEditing`.

    Holds the state both parts reach via `self._ui` (normally supplied by the
    default `UI`) and forwards everything else to whichever part defines it.
    """

    def __init__(self):
        self._output_field = MagicMock()
        self._output_field.text = ""
        self._output_field.buffer = _RecordingBuffer(self._output_field)
        self._input_field = MagicMock()
        self.confirmation = BaseUIConfirmationState()
        self.rendered_blocks = []
        self.rendered_width = None
        self.pending_invalidate = False
        self.invalidate_task = None
        self.markdown_theme = None
        self._is_thinking = False
        self._current_confirmation = None
        self._output = UIOutput(self)
        self._message_editing = UIMessageEditing(self)

    @property
    def output_field(self):
        return self._output_field

    @property
    def input_field(self):
        return self._input_field

    @property
    def is_thinking(self):
        return self._is_thinking

    @property
    def current_confirmation(self):
        return self._current_confirmation

    @property
    def is_application_built(self):
        return self.__dict__.get("application") is not None

    def invalidate_ui(self):
        pass

    def execute_hook(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        message_editing = self.__dict__.get("_message_editing")
        if message_editing is not None and hasattr(message_editing, name):
            return getattr(message_editing, name)
        output = self.__dict__.get("_output")
        if output is None:
            raise AttributeError(name)
        return getattr(output, name)


class _RecordingBuffer:
    def __init__(self, output_field):
        self._output_field = output_field
        self.cursor_position = 0

    @property
    def text(self):
        return self._output_field.text

    def set_document(self, document, bypass_readonly=False):
        self._output_field.text = document.text
        self.cursor_position = document.cursor_position


@pytest.fixture
def editing_ui():
    return MockEditingUI()
