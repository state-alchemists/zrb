"""Queued-message editing for the default `UI`.

While a turn is running, a freshly submitted message sits in the message
queue (`QueuedMessage`) instead of being processed. `UIMessageEditing` lets
the user recall one of those still-queued messages with the Up arrow, edit it
in the input field, and press Enter to replace it in place — the shared entry
is rewritten (so the turn, when it starts, streams the *edited* text) and the
echoed line in the output buffer is spliced to match.

Where each piece lives:

* `_handle_up_arrow` / `_handle_down_arrow` are the buffer-level handlers the
  input field's Up/Down keybindings consult first (see `create_input_field`);
  they return ``False`` to fall through to prompt-toolkit history recall.
* `_handle_enter_queued_edit` is called from the Enter keybinding before the
  plain-submit path; it turns a queued message in the buffer into an edit.
* `_track_echo_span` (overrides the `BaseUI` no-op) records where a submitted
  echo landed in the output buffer; `_redraw_echo` (also an override) splices
  the edited line back in. Both are called from `BaseUI`, which broadcasts
  them across every child UI of a MultiUI.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from zrb.llm.ui.base.message_queue import QueuedMessage

if TYPE_CHECKING:
    from zrb.llm.ui.base.message_queue import MessageQueue


class UIMessageEditing:
    """Up/Down/Enter editing of still-queued messages (part of the default `UI`)."""

    # Host-class contract: state owned by `BaseUI.__init__` and the default
    # `UI.__init__`, plus methods from sibling parts. Declared here so static
    # type checkers can verify accesses; the block does not run at runtime.
    if TYPE_CHECKING:
        # From BaseUI
        @property
        def effective_message_queue(self) -> "MessageQueue": ...

        def edit_queued_message(self, entry: QueuedMessage, new_text: str) -> bool: ...

        # From UIOutput
        @property
        def output_text(self) -> str: ...

        def replace_output_span(
            self, start: int, end: int, replacement: str
        ) -> bool: ...

        # From UIAgentPicker — Down Arrow opens the sub-agent picker when the
        # input field is empty and live sessions are tracked.
        def open_agent_picker(self) -> bool: ...

        # Set by the default `UI.__init__`
        _queued_edit_entry: QueuedMessage | None
        _queued_edit_draft: str
        _input_field: Any

    def _load_edit_text(self, buffer: Any, text: str) -> None:
        """Put `text` in the input buffer with the cursor at its end.

        `Buffer.text` keeps the cursor where it was, which would strand it
        mid-message when recalling a text longer than the draft it replaces.
        """
        buffer.text = text
        buffer.cursor_position = len(text)

    def _recall_navigation_active(self) -> bool:
        """Whether Up should walk queued messages rather than move the cursor.

        True while the input field holds a recalled message the user has not
        touched since — the buffer still matches the recalled text with the
        cursor at its end. A recalled message may span multiple lines, in which
        case the cursor is not on the first line and the input field's Up
        binding would otherwise treat the press as cursor movement. As soon as
        the user types or moves the cursor, this returns False and Up resumes
        cursor movement.
        """
        entry = self._queued_edit_entry
        if entry is None:
            return False
        buffer = self._input_field.buffer
        return buffer.text == entry.text and buffer.cursor_position == len(buffer.text)

    def _handle_up_arrow(self, event: Any) -> bool:
        """Recall a still-queued message into the input field for editing.

        Returns ``True`` when the keypress was consumed by queued-message
        navigation; ``False`` lets the input field's history recall run.
        """
        queue = self.effective_message_queue
        buffer = event.current_buffer
        entry = self._queued_edit_entry

        if entry is not None and not self._recall_navigation_active():
            # The user typed or moved the cursor since the recall — return the
            # arrows to their normal behavior instead of navigating the queue
            # over the in-progress edit (which is not recoverable: the saved
            # draft is the pre-recall text, not the edit).
            return False

        if entry is not None:
            if not queue.contains(entry):
                # The recalled message's turn started — drop the edit mode and
                # treat this Up as a fresh recall. The saved draft survives:
                # the pre-recall text is still what Down should restore.
                self._queued_edit_entry = None
                return self._recall_latest(buffer)
            older = queue.editable_before(entry)
            if older is not None:
                self._queued_edit_entry = older
                self._load_edit_text(buffer, older.text)
                return True
            # Already at the oldest queued message — stay put.
            return True

        return self._recall_latest(buffer, save_draft=True)

    def _recall_latest(self, buffer: Any, save_draft: bool = False) -> bool:
        """Load the newest queued message into the input field.

        On the first recall (`save_draft=True`) the in-progress text is saved
        so Down can restore it; later recalls from a stale edit mode leave the
        saved draft untouched.
        """
        newest = self.effective_message_queue.latest_editable()
        if newest is None:
            return False
        if save_draft:
            self._queued_edit_draft = buffer.text
        self._queued_edit_entry = newest
        self._load_edit_text(buffer, newest.text)
        return True

    def _handle_down_arrow(self, event: Any) -> bool:
        """Step toward the newest queued message, then exit edit mode.

        Returns ``True`` when the keypress was consumed; ``False`` lets the
        input field's history recall run. With an empty input field and no
        queued-message navigation in progress, Down Arrow opens the sub-agent
        picker instead (consumed) when live sub-agent sessions exist.
        """
        buffer = event.current_buffer
        if (
            buffer.text.strip() == ""
            and not self._recall_navigation_active()
            and self.open_agent_picker()
        ):
            return True

        queue = self.effective_message_queue
        entry = self._queued_edit_entry

        if entry is not None and not self._recall_navigation_active():
            # Same guard as Up: once the user typed or moved the cursor, Down
            # must not restore the pre-recall draft over their in-progress edit.
            return False
        if entry is None:
            return False
        if not queue.contains(entry):
            self._queued_edit_entry = None
            return False
        newer = queue.editable_after(entry)
        if newer is not None:
            self._queued_edit_entry = newer
            self._load_edit_text(buffer, newer.text)
            return True
        # At the newest queued message — Down exits edit mode and restores the
        # draft the user was typing before they started recalling.
        self._queued_edit_entry = None
        self._load_edit_text(buffer, self._queued_edit_draft)
        return True

    def _handle_enter_queued_edit(self, event: Any) -> bool:
        """Enter while a still-queued message is in the input buffer.

        Replaces the queued message's text in place instead of submitting a new
        message. Returns ``True`` when the keypress was consumed (the message
        was edited or the edit was cancelled); ``False`` falls through to the
        plain-submit path (e.g. the message's turn already started).
        """
        entry = self._queued_edit_entry
        if entry is None:
            return False
        self._queued_edit_entry = None
        text = event.current_buffer.text
        if not text.strip():
            # Empty edit cancels: restore the pre-edit draft instead of
            # submitting anything.
            self._load_edit_text(event.current_buffer, self._queued_edit_draft)
            return True
        if self.edit_queued_message(entry, text):
            event.current_buffer.reset()
            return True
        # The message already started — fall through and submit as a new one.
        return False

    def _track_echo_span(self, entry: QueuedMessage, echo: str) -> None:
        """Record where `echo` landed so an edit can rewrite it in place.

        Only recorded when the line actually reached the output buffer verbatim
        — a pending confirmation buffers the content instead, which would make
        the span a lie (the same guard `append_rendered` uses).
        """
        text = self.output_text
        if text.endswith(echo):
            entry.echo_span = (len(text) - len(echo), len(text))
            entry.echo_text = echo

    def _redraw_echo(self, entry: QueuedMessage) -> None:
        """Splice `entry`'s echoed line back into the output buffer after an edit."""
        if entry.echo_span is None:
            return
        start, end = entry.echo_span
        if end > len(self.output_text):
            # The span is stale — the buffer was rewritten since (e.g. rewind).
            entry.echo_span = None
            return
        if entry.echo_text and self.output_text[start:end] != entry.echo_text:
            # The span no longer holds the echoed line — a terminal resize
            # re-wrapped tracked markdown blocks and shifted the transcript
            # without updating this entry. Drop the span: the edit is already
            # effective (the turn streams the new text), it just won't rewrite
            # the echo, instead of splicing the line into the wrong offset and
            # corrupting the output buffer.
            entry.echo_span = None
            return
        marker = entry.echo_marker or "💬"
        ts = entry.echo_timestamp or datetime.now().strftime("%H:%M")
        echo = f"\n{marker} {ts} >> {entry.text.strip()}\n"
        self.replace_output_span(start, end, echo)
        entry.echo_span = (start, start + len(echo))
        entry.echo_text = echo
