"""Queued-message editing for the default `UI`.

While a turn is running, a freshly submitted message sits in the message
queue (`QueuedMessage`) instead of being processed. `UIMessageEditing` lets
the user recall one of those still-queued messages with the Up arrow, edit it
in the input field, and press Enter to replace it in place — the shared entry
is rewritten (so the turn, when it starts, streams the *edited* text) and the
echoed line in the output buffer is spliced to match.

Where each piece lives:

* `handle_up_arrow` / `handle_down_arrow` are the buffer-level handlers the
  input field's Up/Down keybindings consult first (see `create_input_field`);
  they return ``False`` to fall through to prompt-toolkit history recall.
* `handle_enter_queued_edit` is called from the Enter keybinding before the
  plain-submit path; it turns a queued message in the buffer into an edit.
* `track_echo_span` records where a submitted echo landed in the output
  buffer; `redraw_echo` splices the edited line back in. Both are called
  through `UI`'s own `track_echo_span`/`redraw_echo` override hooks (the
  `AnyUI` echo contract), which `BaseUI` invokes polymorphically and
  broadcasts across every child UI of a MultiUI.
* `redraw_echo` is the one splice path behind both callers (an edit and a
  paste merge) and re-decides the body from the entry's current text, so the
  two can never draw the message differently.
* Every tracked echo is also a re-renderable block (`RenderedEcho` +
  `render_echo`), and the block — not the `EchoSpan` — holds the authoritative
  offsets: `UIOutput` keeps `rendered_blocks` current through re-wraps and
  in-place edits, and `_refresh_echo_span` reads the span back off it.
"""

from __future__ import annotations

import weakref
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from zrb.llm.ui.base.message_queue import EchoSpan, QueuedMessage
from zrb.llm.ui.base.user_echo import should_render_user_markdown

if TYPE_CHECKING:
    from zrb.llm.ui.default.ui import UI


@dataclass
class RenderedEcho:
    """The source of a queued message's echo block.

    `header` is the `\n💬 10:00 >> ` prefix and `text` the message as last
    drawn; `redraw_echo` re-registers the block whenever the message changes.

    `entry` is weak and only identifies the owning message: a strong
    reference would pin the `QueuedMessage` (attachments, run coroutine) for
    as long as the never-pruned block lives. A dead referent matches nothing.

    `rendered` is what `render_echo` last produced, i.e. exactly what the
    buffer holds at the block's offsets. `_refresh_echo_span` compares
    against it, catching a block that drifted onto another message with the
    same header.
    """

    header: str
    text: str
    entry: "weakref.ReferenceType[QueuedMessage]"
    rendered: str = ""


class UIMessageEditing:
    """Up/Down/Enter editing of still-queued messages (part of the default `UI`)."""

    def __init__(self, ui: "UI") -> None:
        self._ui = ui
        self._queued_edit_entry: QueuedMessage | None = None
        self._queued_edit_draft: str = ""

    @property
    def queued_edit_entry(self) -> QueuedMessage | None:
        """The still-queued message currently recalled for editing, if any."""
        return self._queued_edit_entry

    @queued_edit_entry.setter
    def queued_edit_entry(self, value: QueuedMessage | None) -> None:
        self._queued_edit_entry = value

    @property
    def queued_edit_draft(self) -> str:
        """The in-progress input text saved when a recall started, if any."""
        return self._queued_edit_draft

    @queued_edit_draft.setter
    def queued_edit_draft(self, value: str) -> None:
        self._queued_edit_draft = value

    def _load_edit_text(self, buffer: Any, text: str) -> None:
        """Put `text` in the input buffer with the cursor at its end.

        `Buffer.text` keeps the cursor where it was, which would strand it
        mid-message when recalling a text longer than the draft it replaces.
        """
        buffer.text = text
        buffer.cursor_position = len(text)

    def recall_navigation_active(self) -> bool:
        """Whether Up should walk queued messages rather than move the cursor.

        True while the input still holds the untouched recalled text with the
        cursor at its end — needed because a multi-line recall leaves the
        cursor off the first line, where Up would otherwise move the cursor.
        """
        entry = self._queued_edit_entry
        if entry is None:
            return False
        buffer = self._ui.input_field.buffer
        return buffer.text == entry.text and buffer.cursor_position == len(buffer.text)

    def handle_up_arrow(self, event: Any) -> bool:
        """Recall a still-queued message into the input field for editing.

        Returns ``True`` when the keypress was consumed by queued-message
        navigation; ``False`` lets the input field's history recall run.
        """
        queue = self._ui.effective_message_queue
        buffer = event.current_buffer
        entry = self._queued_edit_entry

        if entry is not None and not self.recall_navigation_active():
            # The user edited since the recall; navigating would clobber the
            # edit, which the saved (pre-recall) draft cannot restore.
            return False

        if entry is not None:
            if not queue.contains(entry):
                # The recalled message's turn started: recall afresh, keeping
                # the saved pre-recall draft.
                self._queued_edit_entry = None
                return self._recall_latest(buffer)
            older = queue.editable_before(entry)
            if older is not None:
                self._queued_edit_entry = older
                self._load_edit_text(buffer, older.text)
            return True

        return self._recall_latest(buffer, save_draft=True)

    def _recall_latest(self, buffer: Any, save_draft: bool = False) -> bool:
        """Load the newest queued message into the input field.

        On the first recall (`save_draft=True`) the in-progress text is saved
        so Down can restore it; later recalls from a stale edit mode leave the
        saved draft untouched.
        """
        newest = self._ui.effective_message_queue.latest_editable()
        if newest is None:
            return False
        if save_draft:
            self._queued_edit_draft = buffer.text
        self._queued_edit_entry = newest
        self._load_edit_text(buffer, newest.text)
        return True

    def handle_down_arrow(self, event: Any) -> bool:
        """Step toward the newest queued message, then exit edit mode.

        Returns ``True`` when the keypress was consumed; ``False`` lets the
        input field's history recall run. With an empty input field and no
        queued-message navigation in progress, Down Arrow opens the sub-agent
        picker instead (consumed) when live sub-agent sessions exist.
        """
        buffer = event.current_buffer
        if (
            buffer.text.strip() == ""
            and not self.recall_navigation_active()
            and self._ui.open_agent_picker()
        ):
            return True

        queue = self._ui.effective_message_queue
        entry = self._queued_edit_entry

        # Same guard as Up: never restore the draft over an in-progress edit.
        if entry is None or not self.recall_navigation_active():
            return False
        if not queue.contains(entry):
            self._queued_edit_entry = None
            return False
        newer = queue.editable_after(entry)
        if newer is not None:
            self._queued_edit_entry = newer
            self._load_edit_text(buffer, newer.text)
            return True
        # Past the newest queued message: exit edit mode, restore the draft.
        self._queued_edit_entry = None
        self._load_edit_text(buffer, self._queued_edit_draft)
        return True

    def handle_enter_queued_edit(self, event: Any) -> bool:
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
            # An empty edit cancels and restores the pre-edit draft.
            self._load_edit_text(event.current_buffer, self._queued_edit_draft)
            return True
        if self._ui.edit_queued_message(entry, text):
            event.current_buffer.reset()
            return True
        # The message already started — fall through and submit as a new one.
        return False

    def track_echo_span(self, entry: QueuedMessage, echo: str) -> None:
        """Record where `echo` landed so an edit can rewrite it in place.

        Spans are keyed by this UI, so each `MultiUI` child keeps its own.

        Recorded only when the line reached the buffer verbatim (a pending
        confirmation buffers it instead). The writer appends a separator
        newline, so the buffer ends with `echo` or `echo + "\\n"`.
        """
        text = self._ui.output_text
        if not (text.endswith(echo) or text.endswith(echo + "\n")):
            return
        index = text.rfind(echo)
        if index < 0:
            return
        entry.echo_spans[self._ui] = EchoSpan(
            start=index,
            end=index + len(echo),
            text=echo,
        )
        # Register as a block only if re-rendering reproduces the written line:
        # the writer and this decide Markdown from slightly different text.
        source = self._create_echo_source(entry)
        if self.render_echo(source, self._ui.output_field_width) == echo:
            self._ui.set_rendered_block(
                index, index + len(echo), source, self.render_echo
            )

    def _validated_echo_span(self, entry: QueuedMessage) -> EchoSpan | None:
        """The echo span still safe to splice for this UI, or ``None``.

        The span is re-read off its tracked block, then pruned if it lies past
        the buffer or no longer holds the echoed line (a block-less echo whose
        offsets nothing kept current, or a rewound transcript).
        """
        if getattr(self._ui, "viewing_agent_id", None) is not None:
            # The main transcript is parked behind a sub-agent view; the span
            # is kept, since it is still correct for the text that returns.
            return None
        span = self._refresh_echo_span(entry)
        if span is None:
            return None
        if span.end > len(self._ui.output_text):
            # Stale: the buffer was rewritten since (e.g. rewind).
            del entry.echo_spans[self._ui]
            return None
        if span.text and self._ui.output_text[span.start : span.end] != span.text:
            # A block-less echo the transcript shifted under. The edit still
            # takes effect; only the on-screen echo is left as is.
            del entry.echo_spans[self._ui]
            return None
        return span

    def _refresh_echo_span(self, entry: QueuedMessage) -> EchoSpan | None:
        """This UI's recorded span for `entry`, re-read off its tracked block.

        The block's offsets survive resizes and in-place edits above it, but
        the region is checked against the text the block last drew before
        being adopted. Falls back to the stored span when there is no block;
        ``None`` when this UI recorded no span.
        """
        span = entry.echo_spans.get(self._ui)
        if span is None:
            return None
        block = self._echo_block(entry)
        if block is None:
            return span
        start, end = block[0], block[1]
        text = self._ui.output_text[start:end]
        if text != block[2].rendered:
            # The buffer was replaced or rewound under the block: drop both
            # the span and the block, which would corrupt the next re-wrap.
            self._ui.rendered_blocks.remove(block)
            del entry.echo_spans[self._ui]
            return None
        span = EchoSpan(start=start, end=end, text=text)
        entry.echo_spans[self._ui] = span
        return span

    def _echo_block(self, entry: QueuedMessage) -> "list[Any] | None":
        """The `rendered_blocks` record holding `entry`'s echo, or None.

        A linear scan by weakref identity: an index keyed on the entry would
        keep every queued message alive. Runs only on an edit or merge.
        """
        for block in self._ui.rendered_blocks:
            source = block[2]
            if isinstance(source, RenderedEcho) and source.entry() is entry:
                return block
        return None

    def _create_echo_source(self, entry: QueuedMessage) -> RenderedEcho:
        return RenderedEcho(
            header=self._echo_header(entry),
            text=entry.text,
            entry=weakref.ref(entry),
        )

    def _echo_header(self, entry: QueuedMessage) -> str:
        """`entry`'s echo prefix — the marker and timestamp it was echoed with."""
        marker = entry.echo_marker or "💬"
        ts = entry.echo_timestamp or datetime.now().strftime("%H:%M")
        return f"\n{marker} {ts} >> "

    def redraw_echo(self, entry: QueuedMessage) -> str | None:
        """Splice `entry`'s echo back into the output buffer at its current text.

        The one splice path behind a queued-message edit and a paste merge.
        Markdown vs. plain is re-decided from `entry.text` each time.

        Returns the rewritten echo, or ``None`` when nothing was redrawn (no
        valid span for this UI, or a sub-agent view is on screen); the caller
        may then fall back to emitting an ordinary echo. Spans are keyed by
        this UI, so one `MultiUI` child never touches another's.
        """
        span = self._validated_echo_span(entry)
        if span is None:
            return None
        source = self._create_echo_source(entry)
        echo = self.render_echo(source, self._ui.output_field_width)
        if not self._ui.replace_output_span(span.start, span.end, echo):
            return None
        # Re-register so the block keeps tracking (and re-wrapping) the echo.
        self._ui.set_rendered_block(
            span.start, span.start + len(echo), source, self.render_echo
        )
        entry.echo_spans[self._ui] = EchoSpan(
            start=span.start,
            end=span.start + len(echo),
            text=echo,
        )
        return echo

    def render_echo(self, source: RenderedEcho, width: int | None) -> str:
        """Render a queued message's whole echo — header, body, separator.

        As the block's re-render hook it must reproduce the whole spliced
        region. Records the result on `source` on every call, re-wraps
        included.
        """
        source.rendered = (
            f"{source.header}{self._render_echo_body(source.text, width)}\n"
        )
        return source.rendered

    def _render_echo_body(self, text: str, width: int | None) -> str:
        """Render a queued message's echo body at `width`.

        Markdown when `text` carries a construct, the stripped line otherwise
        — the same rule `echo_user_message` applies to the first echo.
        """
        if should_render_user_markdown(text):
            return self._ui.render_markdown(text, width)
        return text.strip()
