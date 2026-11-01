"""A queued message its sender no longer wants can be taken back.

A background command's wake-up is queued when the command ends. If the model
reads the ending first, the message would start a turn about nothing, so the
sender withdraws it. Only a message that has not started can be withdrawn.
"""

from unittest.mock import MagicMock

from zrb.llm.input_source import BACKGROUND_INPUT, KEYBOARD_INPUT
from zrb.llm.ui.default.ui import UI
from zrb.llm.ui.multi_ui import MultiUI


def _ui(mock_ui_deps) -> UI:
    ui = UI(**mock_ui_deps)
    ui.append_to_output = MagicMock()  # type: ignore[method-assign]
    return ui


def test_a_queued_wake_up_can_be_withdrawn(mock_ui_deps):
    ui = _ui(mock_ui_deps)
    ui.submit_message("[Background process x finished (exit 0)]", BACKGROUND_INPUT)
    assert ui.queued_message_count == 1

    ui.withdraw_message("[Background process x finished (exit 0)]", BACKGROUND_INPUT)

    assert ui.queued_message_count == 0


def test_a_second_withdrawal_finds_nothing(mock_ui_deps):
    ui = _ui(mock_ui_deps)
    ui.submit_message("wake", BACKGROUND_INPUT)
    ui.submit_message("another", KEYBOARD_INPUT)
    ui.withdraw_message("wake", BACKGROUND_INPUT)

    ui.withdraw_message("wake", BACKGROUND_INPUT)

    assert ui.queued_message_count == 1


def test_the_users_own_message_with_the_same_words_is_not_withdrawn(mock_ui_deps):
    """The channel is part of the match: a sender takes back its own message."""
    ui = _ui(mock_ui_deps)
    ui.submit_message("same words", KEYBOARD_INPUT)

    ui.withdraw_message("same words", BACKGROUND_INPUT)

    assert ui.queued_message_count == 1


def test_a_message_that_was_never_queued_is_not_withdrawn(mock_ui_deps):
    ui = _ui(mock_ui_deps)

    ui.withdraw_message("never sent", BACKGROUND_INPUT)

    assert ui.queued_message_count == 0


def test_a_multi_ui_withdraws_from_its_own_queue_and_every_child():
    child_one, child_two = MagicMock(), MagicMock()
    multi = MultiUI([child_one, child_two])
    multi.submit_message("wake", BACKGROUND_INPUT)
    assert multi.message_queue.qsize() == 1

    multi.withdraw_message("wake", BACKGROUND_INPUT)

    assert multi.message_queue.qsize() == 0
    child_one.remove_echo.assert_called_once()
    child_two.remove_echo.assert_called_once()

    multi.withdraw_message("wake", BACKGROUND_INPUT)
    child_one.remove_echo.assert_called_once()


def test_a_background_notice_is_not_offered_back_as_something_the_user_typed(
    mock_ui_deps,
):
    """Up-arrow recall is the user's own words; a notice from a command that
    ended must not turn up there, or in the persisted input history."""
    ui = _ui(mock_ui_deps)
    ui.record_submitted_message = MagicMock()  # type: ignore[method-assign]

    ui.submit_message("[Background process x finished (exit 0)]", BACKGROUND_INPUT)
    ui.record_submitted_message.assert_not_called()

    ui.submit_message("what I typed", KEYBOARD_INPUT)
    ui.record_submitted_message.assert_called_once_with("what I typed")


def test_a_multi_ui_records_only_what_the_user_typed():
    main = MagicMock()
    multi = MultiUI([main, MagicMock()])

    multi.submit_message("[Background process x finished (exit 0)]", BACKGROUND_INPUT)
    main.record_submitted_message.assert_not_called()

    multi.submit_message("what I typed", KEYBOARD_INPUT)
    main.record_submitted_message.assert_called_once_with("what I typed")
