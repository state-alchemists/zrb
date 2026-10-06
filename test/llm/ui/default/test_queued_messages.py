from types import SimpleNamespace

from zrb.llm.ui.base.message_queue import EchoSpan, QueuedMessage
from zrb.llm.ui.base.ui import BaseUI


def make_entry(text="original", marker="💬", ts="10:00"):
    async def run():
        pass

    entry = QueuedMessage(text=text, attachments=[], kind="message", run=run)
    entry.echo_marker = marker
    entry.echo_timestamp = ts
    return entry


class _Buffer:
    """Just enough of a prompt-toolkit buffer for the recall handlers."""

    def __init__(self, text=""):
        self.text = text
        self.cursor_position = len(text)

    def reset(self):
        self.text = ""
        self.cursor_position = 0


def _event(buffer):
    return SimpleNamespace(current_buffer=buffer)


def _queue(editing_ui, *entries):
    for entry in entries:
        editing_ui.effective_message_queue.put_nowait(entry)


def _entries(*texts):
    return [make_entry(text=text) for text in texts]


def _panel(editing_ui) -> str:
    """The panel as the terminal would read it."""
    from prompt_toolkit.formatted_text import to_formatted_text

    frags = to_formatted_text(editing_ui.get_queued_messages_text())
    return "".join(fragment[1] for fragment in frags)


# --- what is waiting ----------------------------------------------------------


def test_the_queued_messages_are_listed_oldest_first(editing_ui):
    _queue(editing_ui, *_entries("fix the parser", "run the tests"))

    rendered = _panel(editing_ui)

    assert " 📥 2 queued · ↑ to edit" in rendered
    assert " 1. fix the parser" in rendered
    assert " 2. run the tests" in rendered


def test_nothing_queued_shows_no_panel(editing_ui):
    assert editing_ui.get_queued_messages_text() == []


def test_the_message_up_arrow_recalled_is_marked(editing_ui):
    _queue(editing_ui, *_entries("first", "second"))
    editing_ui.handle_up_arrow(_event(_Buffer()))

    rendered = _panel(editing_ui)

    assert "▸2. second" in rendered
    assert " 1. first" in rendered


def test_editing_a_recalled_message_rewrites_one_queue_entry_and_one_echo(
    editing_ui,
):
    entry = make_entry()
    echo = "\n💬 10:00 >> original\n"
    editing_ui.output_field.text = echo
    editing_ui.track_echo_span(entry, echo)
    _queue(editing_ui, entry)
    buffer = _Buffer("draft")

    editing_ui.handle_up_arrow(_event(buffer))
    buffer.text = "edited in place"
    buffer.cursor_position = len(buffer.text)
    editing_ui.edit_queued_message = BaseUI.edit_queued_message.__get__(
        editing_ui, type(editing_ui)
    )

    assert editing_ui.handle_enter_queued_edit(_event(buffer)) is True

    assert editing_ui.effective_message_queue.pending() == (entry,)
    assert entry.text == "edited in place"
    assert editing_ui.output_text == "\n💬 10:00 >> edited in place\n"
    assert editing_ui.output_text.count(">> ") == 1


def test_a_queue_longer_than_the_panel_is_summarized(editing_ui):
    _queue(editing_ui, *_entries(*[f"message {n}" for n in range(1, 8)]))

    rendered = _panel(editing_ui)

    assert " 5. message 5" in rendered
    assert "message 6" not in rendered
    assert "… and 2 more" in rendered


def test_a_queued_message_is_shown_as_its_first_line_only(editing_ui):
    _queue(editing_ui, make_entry(text="first line\nsecond line " + "x" * 200))

    rendered = _panel(editing_ui)

    assert "first line" in rendered
    assert "second line" not in rendered


# --- what Ctrl+X drops --------------------------------------------------------


def test_deleting_a_recalled_message_takes_it_out_of_the_queue(editing_ui):
    entry = make_entry()
    _queue(editing_ui, entry)
    buffer = _Buffer("a draft I was writing")
    editing_ui.handle_up_arrow(_event(buffer))
    assert editing_ui.queued_edit_entry is entry

    editing_ui.handle_delete_queued(_event(buffer))

    assert editing_ui.effective_message_queue.pending() == ()
    assert editing_ui.queued_edit_entry is None
    # The draft that was in the input when the recall started comes back.
    assert buffer.text == "a draft I was writing"


def test_deleting_a_recalled_message_takes_its_echo_out(editing_ui):
    echo = "\n💬 10:00 >> original\n"
    editing_ui.output_field.text = "head" + echo + "tail"
    entry = make_entry()
    start = len("head")
    entry.echo_spans[editing_ui] = EchoSpan(start, start + len(echo), echo)
    _queue(editing_ui, entry)
    buffer = _Buffer()
    editing_ui.handle_up_arrow(_event(buffer))

    editing_ui.handle_delete_queued(_event(buffer))

    assert editing_ui.output_text == "headtail"
    assert entry.echo_spans == {}


def test_deleting_a_recalled_message_drops_its_tracked_block(editing_ui):
    """The line is spliced out and its block forgotten, so a later resize
    cannot re-render the message back into the transcript."""
    echo = "\n💬 10:00 >> original\n"
    editing_ui.output_field.text = echo
    entry = make_entry()
    editing_ui.track_echo_span(entry, echo)
    assert len(editing_ui.rendered_blocks) == 1
    _queue(editing_ui, entry)
    buffer = _Buffer()
    editing_ui.handle_up_arrow(_event(buffer))

    editing_ui.handle_delete_queued(_event(buffer))

    assert editing_ui.rendered_blocks == []
    assert editing_ui.output_text == ""


def test_deleting_with_nothing_recalled_leaves_the_queue_alone(editing_ui):
    entry = make_entry()
    _queue(editing_ui, entry)

    editing_ui.handle_delete_queued(_event(_Buffer()))

    assert editing_ui.effective_message_queue.pending() == (entry,)


def test_a_message_whose_turn_started_cannot_be_deleted(editing_ui):
    """The queue no longer holds it, so the recall is dropped and no entry is
    taken out — and the recalled text goes with it, rather than staying in the
    input to be sent again as a new message by a later Enter."""
    entry = make_entry()
    _queue(editing_ui, entry)
    buffer = _Buffer("a draft I was writing")
    editing_ui.handle_up_arrow(_event(buffer))
    assert buffer.text == "original"
    editing_ui.effective_message_queue.remove(entry)

    editing_ui.handle_delete_queued(_event(buffer))

    assert editing_ui.queued_edit_entry is None
    assert buffer.text == "a draft I was writing"


def test_only_the_recalled_message_is_deleted(editing_ui):
    first, second = _entries("first", "second")
    _queue(editing_ui, first, second)
    buffer = _Buffer()
    editing_ui.handle_up_arrow(_event(buffer))

    editing_ui.handle_delete_queued(_event(buffer))

    assert editing_ui.effective_message_queue.pending() == (first,)
    assert second not in editing_ui.effective_message_queue.pending()


def test_deleting_while_a_sub_agent_view_is_up_clears_the_parked_transcript(
    editing_ui,
):
    """The pane holds the sub-agent's transcript and the main one is parked.
    The line has to leave the parked copy too: that is the text the view
    restores when it closes, so a line left there comes back on screen."""
    echo = "\n💬 10:00 >> original\n"
    editing_ui.output_field.text = echo
    entry = make_entry()
    editing_ui.track_echo_span(entry, echo)
    # The view opens: the main transcript is parked, the pane swaps to the
    # sub-agent's own buffer.
    editing_ui.saved_main_output = editing_ui.output_text
    editing_ui.viewing_agent_id = "agent-1"
    editing_ui.output_field.text = "sub-agent output\n"
    _queue(editing_ui, entry)
    buffer = _Buffer()
    editing_ui.handle_up_arrow(_event(buffer))

    editing_ui.handle_delete_queued(_event(buffer))

    assert editing_ui.effective_message_queue.pending() == ()
    # The sub-agent's own transcript is left exactly as it was...
    assert editing_ui.output_text == "sub-agent output\n"
    # ...and the parked main transcript lost the line, so closing the view
    # cannot bring the deleted message back.
    assert editing_ui.saved_main_output == ""
    assert entry.echo_spans == {}
    assert editing_ui.rendered_blocks == []


def test_deleting_from_one_child_of_a_multi_ui_clears_every_transcript(
    editing_multi_ui,
):
    """Each child UI keeps its own echo, so the delete has to reach all of
    them — a child left out would keep showing a message whose turn never
    runs."""
    first, second = editing_multi_ui.children
    echo = "\n💬 10:00 >> original\n"
    entry = make_entry()
    for child in (first, second):
        child.output_field.text = echo
        child.track_echo_span(entry, echo)
    editing_multi_ui.message_queue.put_nowait(entry)
    buffer = _Buffer()
    first.handle_up_arrow(_event(buffer))
    assert first.queued_edit_entry is entry

    first.handle_delete_queued(_event(buffer))

    assert editing_multi_ui.message_queue.pending() == ()
    assert first.output_text == ""
    assert second.output_text == ""
    assert entry.echo_spans == {}
