"""Shared stand-ins: the queued-message echo UI and the choice-widget UI."""

from unittest.mock import MagicMock

import pytest

from zrb.llm.ui.base.confirmation_state import BaseUIConfirmationState
from zrb.llm.ui.base.message_queue import MessageQueue
from zrb.llm.ui.base.ui import BaseUI
from zrb.llm.ui.default.confirmation import UIConfirmation
from zrb.llm.ui.default.message_editing import UIMessageEditing
from zrb.llm.ui.default.output import UIOutput
from zrb.llm.ui.default.selection import UISelection
from zrb.util.cli.terminal import TerminalSize


@pytest.fixture
def terminal_rows(monkeypatch):
    """Pin the terminal height a docked panel measures itself against.

    CI runs on a 24-row terminal while a developer's is taller, so a height a
    test reads off the real one passes locally and fails in CI. Every test that
    asserts a panel's height calls this first.
    """
    from zrb.llm.ui.default.app import docking

    def _set(rows: int) -> None:
        monkeypatch.setattr(
            docking,
            "get_terminal_size",
            lambda *args, **kwargs: TerminalSize(columns=80, lines=rows),
        )

    return _set


class MockEditingUI:
    """Stand-in UI composing the real `UIOutput` and `UIMessageEditing`.

    Holds the state both parts reach via `self._ui` (normally supplied by the
    default `UI`) and forwards everything else to whichever part defines it.
    """

    # The real fan-out (drop from the shared queue, take the echo out of every
    # target), which the default `UI` inherits from `BaseUI` unchanged — so a
    # delete behaves here as it does in production.
    delete_queued_message = BaseUI.delete_queued_message

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
        self.status_badges: tuple[str, ...] = ()
        self.multi_ui_parent = None
        self._own_message_queue = MessageQueue()
        self._is_thinking = False
        self._current_confirmation = None
        self._output = UIOutput(self)
        self._message_editing = UIMessageEditing(self)

    @property
    def effective_message_queue(self):
        """The queue submissions land on: a `MultiUI` parent's when there is
        one, else this UI's own — the routing `BaseUI` does for every child."""
        parent = self.multi_ui_parent
        if parent is not None:
            return parent.message_queue
        return self._own_message_queue

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


@pytest.fixture
def editing_multi_ui():
    """Two real `MockEditingUI`s wired as `MultiUI` wires them: `multi_ui_parent`
    set on each, so both route to the one shared queue and one delete reaches
    both transcripts."""
    from zrb.llm.ui.multi_ui import MultiUI

    return MultiUI([MockEditingUI(), MockEditingUI()])


class FakeSelectionUI:
    """Minimal host composing the real `UISelection` (plus a real
    `UIConfirmation` sibling, so `handle_confirmation`'s fall-through to
    `UIConfirmation`'s base case is exercised exactly as in the real default
    `UI`). `resolve_current` is overridden directly on this stand-in UI —
    `UISelection`/`UIConfirmation` both call `self._ui.resolve_current`,
    so this override is what they both see. `begin_choice`/`end_choice`/
    `handle_confirmation` mirror the real `UI`'s own one-line delegators to
    `UISelection`'s public implementation.
    """

    def __init__(self):
        self.input_field = object()
        self.confirmation = BaseUIConfirmationState()
        self.confirmation.current = "FUTURE"  # truthy sentinel
        self.resolved: str | None = None
        self.echoes: list[str] = []
        self._confirmation = UIConfirmation(self)
        self._selection = UISelection(self, confirmation=self._confirmation)
        self._selection.init_selection_state()

    def append_to_output(self, *values, **kwargs):
        self.echoes.append("".join(str(v) for v in values))

    def resolve_current(self, text, echo):
        self.resolved = text
        if echo:
            self.echoes.append(echo)
        self.confirmation = BaseUIConfirmationState()
        self.end_choice()
        return True

    def begin_choice(self, spec):
        self._selection.begin_choice(spec)

    def end_choice(self):
        self._selection.end_choice()

    def handle_confirmation(self, event):
        return self._selection.handle_confirmation(event)

    def __getattr__(self, name):
        selection = self.__dict__.get("_selection")
        if selection is not None and hasattr(selection, name):
            return getattr(selection, name)
        confirmation = self.__dict__.get("_confirmation")
        if confirmation is not None:
            return getattr(confirmation, name)
        raise AttributeError(name)


@pytest.fixture
def ui():
    """A stand-in default UI showing the real choice widget."""
    return FakeSelectionUI()
