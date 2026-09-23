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
  through `UI`'s own `_track_echo_span`/`_redraw_echo` override hooks, which
  `BaseUI` invokes polymorphically and broadcasts across every child UI of a
  MultiUI.
* `redraw_echo` renders the body through `render_echo_body`, so *one* splice
  path serves both callers — an edit and a paste merge — and the displayed
  echo always matches what the entry's current text is: Markdown when it
  carries a construct, the raw line otherwise. Splitting that into a separate
  Markdown redraw let the two callers disagree, and editing a merged Markdown
  message replaced its rendered block with raw text.
* Every echo this UI tracks is registered as a re-renderable block
  (`RenderedEcho` + `render_echo`), and the block record — not the
  `EchoSpan` — is where the echo's offsets actually live. `UIOutput` already
  keeps `rendered_blocks` current through *every* buffer rewrite: a re-wrap
  re-renders each block and updates its offsets, and `_rebase_tracked_spans`
  shifts the blocks below any in-place edit. Reading the span back off the
  block (`refresh_echo_span`) inherits all of that, instead of duplicating
  the same bookkeeping over a second set of offsets that would silently rot
  whenever text above the echo changed.
"""

from __future__ import annotations

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

    `header` is the fixed `\n💬 10:00 >> ` prefix; the body is always derived
    from `entry.text`, so one record keeps re-rendering the *current* message
    however often it is edited or merged into. Holding the entry (rather than
    a snapshot of its text) is also what lets `refresh_echo_span` recognise
    which block belongs to which queued message.
    """

    header: str
    entry: QueuedMessage


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

        if entry is not None and not self.recall_navigation_active():
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
            # Empty edit cancels: restore the pre-edit draft instead of
            # submitting anything.
            self._load_edit_text(event.current_buffer, self._queued_edit_draft)
            return True
        if self._ui.edit_queued_message(entry, text):
            event.current_buffer.reset()
            return True
        # The message already started — fall through and submit as a new one.
        return False

    def track_echo_span(self, entry: QueuedMessage, echo: str) -> None:
        """Record where `echo` landed so an edit can rewrite it in place.

        The span is stored on the shared entry keyed by this UI (`self._ui`),
        so a `MultiUI` whose every child echoes the same line keeps one span
        per child buffer — a child redraws against its own span, never the
        last child's.

        Only recorded when the line actually reached the output buffer
        verbatim — a pending confirmation buffers the content instead, which
        would make the span a lie (the same guard `append_rendered` uses). The
        echo's own writer appends a separator newline after the line (the
        default `end="\\n"`), so the span is located by the exact echo
        substring at the tail rather than by a bare `endswith` — the buffer
        ends with `echo`, or with one blank line after it.
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
        # Register the echo as a re-renderable block so its offsets ride along
        # with every later buffer rewrite (see the module docstring). Only when
        # re-rendering reproduces the line that was actually written: the
        # writer decided Markdown from the stripped body, this decides from
        # `entry.text`, and on the rare input where those disagree a block
        # would re-render the echo into something the user never saw.
        source = RenderedEcho(header=self.echo_header(entry), entry=entry)
        if self.render_echo(source, self._ui.output_field_width) == echo:
            self._ui.set_rendered_block(
                index, index + len(echo), source, self.render_echo
            )

    def _validated_echo_span(self, entry: QueuedMessage) -> EchoSpan | None:
        """The echo span still safe to splice for this UI, or ``None``.

        The span is re-read off the echo's tracked block first, so a re-wrap
        or an in-place edit above the echo leaves it correct rather than
        stale. It is still unusable — and pruned — when it lies past the
        buffer or no longer holds the echoed line: an echo with no block (one
        whose registration the faithfulness check in `track_echo_span`
        declined) has nothing keeping its offsets current, and a rewound
        transcript invalidates both.
        """
        span = self.refresh_echo_span(entry)
        if span is None:
            return None
        if span.end > len(self._ui.output_text):
            # The span is stale — the buffer was rewritten since (e.g. rewind).
            del entry.echo_spans[self._ui]
            return None
        if span.text and self._ui.output_text[span.start : span.end] != span.text:
            # The span no longer holds the echoed line — a terminal resize
            # re-wrapped tracked markdown blocks and shifted the transcript
            # without updating this entry. Drop the span: the edit is already
            # effective (the turn streams the new text), it just won't rewrite
            # the echo, instead of splicing the line into the wrong offset and
            # corrupting the output buffer.
            del entry.echo_spans[self._ui]
            return None
        return span

    def refresh_echo_span(self, entry: QueuedMessage) -> EchoSpan | None:
        """This UI's recorded span for `entry`, re-read off its tracked block.

        The block record is the authoritative copy of where the echo is:
        `rewrap_output` rewrites its offsets when a resize re-renders it, and
        `_rebase_tracked_spans` shifts it whenever an in-place edit above it
        (a streamed shell span, a collapsing thinking block, another echo
        redraw) grows or shrinks the text between. Re-reading here is what
        makes the documented promise — the span survives, and a later edit can
        still rewrite the displayed message — hold across both.

        Falls back to the stored span when the entry has no block, and returns
        ``None`` when this UI never recorded a span at all.
        """
        span = entry.echo_spans.get(self._ui)
        if span is None:
            return None
        block = self.echo_block(entry)
        if block is None:
            return span
        start, end = block[0], block[1]
        span = EchoSpan(start=start, end=end, text=self._ui.output_text[start:end])
        entry.echo_spans[self._ui] = span
        return span

    def echo_block(self, entry: QueuedMessage) -> "list[Any] | None":
        """The `rendered_blocks` record holding `entry`'s echo, or None.

        Found by identity of the entry the block's `RenderedEcho` source
        holds, rather than by a second index keyed on the entry — a registry
        would keep every queued message alive for the life of the UI, and the
        scan runs only when a message is edited or merged into, at human
        speed, over a list this UI already walks on every resize.
        """
        for block in self._ui.rendered_blocks:
            source = block[2]
            if isinstance(source, RenderedEcho) and source.entry is entry:
                return block
        return None

    def echo_header(self, entry: QueuedMessage) -> str:
        """`entry`'s echo prefix — the marker and timestamp it was echoed with."""
        marker = entry.echo_marker or "💬"
        ts = entry.echo_timestamp or datetime.now().strftime("%H:%M")
        return f"\n{marker} {ts} >> "

    def redraw_echo(self, entry: QueuedMessage) -> str | None:
        """Splice `entry`'s echo back into the output buffer at its current text.

        The single splice path behind both callers — an edit of a queued
        message, and a paste line merging into one. The body is whatever
        `entry.text` currently is, drawn by `render_echo_body`: Markdown when
        the text carries a construct (so a merged fenced block or list reads
        as one block rather than a render of just the newest line), the raw
        line otherwise. Because the decision is re-made here from the entry
        itself, editing a merged Markdown message keeps rendering, and editing
        it back to plain text stops.

        Returns the rewritten echo, or ``None`` when nothing was redrawn —
        there is no tracked span for this UI, the span is stale, or the buffer
        no longer holds the echo. A caller that gets ``None`` (a bufferless UI,
        or the default UI past a rendered echo that never claimed a span) can
        fall back to emitting an ordinary echo so merged paste lines stay
        visible.

        The span lookup is keyed by this UI (`self._ui`), so one child's
        redraw never touches — or invalidates — the span another child tracks
        on the same shared entry.
        """
        span = self._validated_echo_span(entry)
        if span is None:
            return None
        source = RenderedEcho(header=self.echo_header(entry), entry=entry)
        echo = self.render_echo(source, self._ui.output_field_width)
        if not self._ui.replace_output_span(span.start, span.end, echo):
            return None
        # Re-register over the same start: the block is what keeps this echo's
        # offsets current afterwards, and a resize re-renders it at the new
        # width instead of leaving it wrapped for the old one.
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

        The re-render hook of the echo's tracked block, so it has to reproduce
        the entire spliced region: `rewrap_output` replaces the recorded span
        with whatever this returns, and a hook covering only the body would
        splice the body over its own header.
        """
        return f"{source.header}{self.render_echo_body(source.entry.text, width)}\n"

    def render_echo_body(self, text: str, width: int | None) -> str:
        """Render a queued message's echo body at `width`.

        Markdown when `text` carries a construct, the stripped line otherwise
        — the same rule `echo_user_message` applies to the first echo, so a
        redrawn echo and a freshly written one never disagree.

        Doubles as the re-render hook of the echo's tracked block, which is
        why it takes a width: `rewrap_output` calls it with the new width
        after a resize. A plain body renders to itself, so the one hook covers
        every echo and no block has to be untracked when an edit turns
        Markdown back into plain text.
        """
        if should_render_user_markdown(text):
            return self._ui.render_markdown(text, width)
        return text.strip()
