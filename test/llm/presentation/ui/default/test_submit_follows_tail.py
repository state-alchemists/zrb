"""A sent message puts the transcript back on its tail.

Reading further up while typing is worth keeping: a reply that streams in must
not pull the view down under a reader who scrolled away to read it. The moment a
message is sent, though, the reply being waited for is the one to show — so the
pane returns to the bottom, and the first chunk of the reply is read where the
new text actually is.

Two things were needed for that and only one was there. `resume()` marks the
pane as following, but the append path decides "was the reader at the tail?"
from the cursor on every chunk, so a flag alone is undone by the first chunk;
and the hook lived on `submit_message`, which a keyboard Enter never reaches.
"""

import dataclasses

from zrb.llm.contracts.shared.input_source import BACKGROUND_INPUT, DICTATION_INPUT
from zrb.llm.presentation.ui.default.ui import UI


def _read_above_the_tail(ui: UI) -> None:
    """Put the reader where the wheel leaves them: off the tail, not following."""
    ui.append_to_output("first answer\nsecond line of it\n")
    ui.output_field.buffer.cursor_position = 0
    ui.output_follow.note(ui.output_field)
    assert ui.output_follow.following is False


def _is_at_tail(ui: UI) -> bool:
    """Whether the pane's cursor sits at the end of everything written so far."""
    buffer = ui.output_field.buffer
    return buffer.cursor_position == len(buffer.text)


def test_sending_a_message_brings_the_pane_back_to_the_tail(mock_ui_deps):
    ui = UI(**mock_ui_deps)
    _read_above_the_tail(ui)

    ui.submit_user_message(ui.llm_task, "typed while reading above")

    assert ui.output_follow.following is True
    assert _is_at_tail(ui)

    # The reply's first chunk is what used to freeze the pane again.
    ui.append_to_output("the reply's first chunk\n")
    assert ui.output_follow.following is True
    assert _is_at_tail(ui)


def test_a_dictated_message_brings_the_pane_back_to_the_tail(mock_ui_deps):
    """Speech with the microphone armed is a message sent, the same as Enter.

    Dictation does not come through the keyboard binding: the trigger loop calls
    `submit_message_now`, which lands on `submit_message` and then on the submit
    path. It is the user's own words, and the reply to them is the one to watch.

    The provenance is the microphone's channel with this utterance's tone and
    length filled in, as `dictation/feature.py` sends it — never the constant.
    """
    ui = UI(**mock_ui_deps)
    _read_above_the_tail(ui)
    spoken = dataclasses.replace(
        DICTATION_INPUT, tone="calm", tone_score=0.8, spoken_seconds=2.5
    )

    ui.submit_message_now("said out loud", spoken, may_interrupt=False)

    assert ui.output_follow.following is True
    assert _is_at_tail(ui)


def test_a_subagent_message_leaves_the_reader_where_they_were(mock_ui_deps):
    """A sub-agent's words are not the user's, so they do not move the reader.

    Both of its ways into the main chat go through here with no provenance: the
    closing reply of a cancelled-then-continued session, and `SendMessageToParent`.
    Neither is a turn the user just sent, so reading further up stays readable.
    """
    ui = UI(**mock_ui_deps)
    _read_above_the_tail(ui)

    ui.submit_user_message(ui.llm_task, "the sub-agent's closing reply", None)

    assert ui.output_follow.following is False
    assert not _is_at_tail(ui)


def test_a_background_notice_leaves_the_reader_where_they_were(mock_ui_deps):
    """A command ending is not a reply being waited for, so it does not yank the view."""
    ui = UI(**mock_ui_deps)
    _read_above_the_tail(ui)

    ui.submit_user_message(ui.llm_task, "the shell finished", BACKGROUND_INPUT)

    assert ui.output_follow.following is False
    assert not _is_at_tail(ui)
