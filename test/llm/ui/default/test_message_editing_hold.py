"""Holding a queued message while it is being edited.

The flag lives on the entry rather than on `UIMessageEditing`, because the
checkpoint that delivers runs in the turn's own thread and never holds that
helper. These pin that a recall raises it and that every way out — Enter, Ctrl+X,
or Down past the newest — lowers it again, so a message cannot be delivered
mid-edit and cannot stay stuck out of reach either.
"""

import pytest

from .test_keybindings_history_nav import (
    MockUI,
    _queued_entry,
    _set_input_buffer,
    create_mock_event,
)


@pytest.fixture
def mock_ui():
    return MockUI()


def test_a_recalled_message_is_held_until_enter(mock_ui):
    entry = _queued_entry("queued message")
    mock_ui.effective_message_queue.put_nowait(entry)
    event = create_mock_event("draft")

    mock_ui.handle_up_arrow(event)
    assert entry.is_being_edited is True

    event.current_buffer.text = "queued message EDITED"
    event.current_buffer.cursor_position = len("queued message EDITED")
    _set_input_buffer(mock_ui, "queued message EDITED", len("queued message EDITED"))
    mock_ui.handle_enter_queued_edit(event)

    assert mock_ui.queued_edit_entry is None
    assert entry.is_being_edited is False


def test_dropping_a_recalled_message_releases_the_hold(mock_ui):
    entry = _queued_entry("queued message")
    mock_ui.effective_message_queue.put_nowait(entry)
    event = create_mock_event("draft")

    mock_ui.handle_up_arrow(event)
    mock_ui.handle_delete_queued(event)

    assert entry.is_being_edited is False
    assert entry not in mock_ui.effective_message_queue.pending()


def test_walking_past_the_newest_queued_message_releases_the_hold(mock_ui):
    entry = _queued_entry("queued message")
    mock_ui.effective_message_queue.put_nowait(entry)
    event = create_mock_event("draft")

    mock_ui.handle_up_arrow(event)
    assert entry.is_being_edited is True

    _set_input_buffer(mock_ui, "queued message", len("queued message"))
    mock_ui.handle_down_arrow(event)

    assert mock_ui.queued_edit_entry is None
    assert entry.is_being_edited is False


def test_stepping_to_an_older_message_moves_the_hold(mock_ui):
    """Only one message is being edited at a time: the hold follows the recall."""
    older = _queued_entry("older")
    newer = _queued_entry("newer")
    queue = mock_ui.effective_message_queue
    queue.put_nowait(older)
    queue.put_nowait(newer)
    event = create_mock_event("draft")

    mock_ui.handle_up_arrow(event)
    assert (older.is_being_edited, newer.is_being_edited) == (False, True)

    _set_input_buffer(mock_ui, "newer", len("newer"))
    mock_ui.handle_up_arrow(event)

    assert mock_ui.queued_edit_entry is older
    assert (older.is_being_edited, newer.is_being_edited) == (True, False)
