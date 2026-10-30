"""`/btw` side-question panel for the default `UI`.

A side question is answered off to the side and never saved to history, so its
answer must not scroll the transcript the user is reading. `UISideQuestion`
shows it in the same framed panel the choice widget uses, docked above the
input: the question, then the answer once it arrives, at a fixed height that
scrolls instead of swallowing the screen.

It docks rather than taking the input frame's place because it keeps typing
alive: the panel takes the focus while it is shown, so the movement keys walk
the answer instead of the input (Up/Down with PageUp/PageDown/Home/End scroll
the panel rather than recalling a queued message), but a typed character starts
a message in the input without the focus leaving the panel, so the input frame
has to stay visible. Enter closes the panel without submitting an input draft;
Esc also closes it. Both return focus to the input. A panel that opens while a
prompt is waiting for the user keeps the focus where it is: that field is what
the turn is blocked on.

* `begin(question)` — open the panel and say the answer is coming. Returns a
  token naming that question.
* `end(answer, request)` / `fail(message, request)` — fill it in, but only when
  `request` is still the panel's current question.
* `dismiss()` — close it.

One panel serves every `/btw`, and answers arrive in their own background
tasks, so an older question's answer can finish after a newer one opened the
panel. The token is how a late answer recognizes that the panel has moved on
and stays out of it.
"""

from __future__ import annotations

import unicodedata
from typing import TYPE_CHECKING

from zrb.llm.ui.default.app.docking import (
    framed_panel_height,
    panel_content_height,
    panel_row_cap,
)
from zrb.llm.ui.default.app.focus import focus_widget, invalidate_app
from zrb.llm.ui.default.app.notice import append_notice

if TYPE_CHECKING:
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout.containers import AnyContainer
    from prompt_toolkit.widgets import TextArea

    from zrb.llm.ui.default.ui import UI

PANEL_HEIGHT = 12
"""Rows the panel shows before its own text scrolls."""

PANEL_PAGE_ROWS = PANEL_HEIGHT - 2
"""Rows PageUp/PageDown move, leaving two lines of the previous text in view."""


_PENDING = "  … thinking\n"


class UISideQuestion:
    """The `/btw` panel: one question, one answer, until dismissed."""

    def __init__(self, ui: "UI") -> None:
        self._ui = ui
        self._question = ""
        self._is_active = False
        self._window: "TextArea | None" = None
        # Identifies the question the panel currently shows; None once closed.
        self._request: object | None = None
        # The raw markdown of the answer currently shown, for `rewrap`; None
        # while the panel shows a pending/failure message or nothing at all.
        self._last_answer: str | None = None
        # A command reply's body (`show`), kept because the panel may have to
        # hand it to the transcript when the screen shrinks under it.
        self._shown_body: str | None = None
        self._rendered_width: int | None = None

    def init_side_question_state(self) -> None:
        """Initialize the panel state and build its (hidden) widget."""
        self._question = ""
        self._is_active = False
        self._request = None
        self._last_answer = None
        self._shown_body = None
        self._rendered_width = None
        self._window = self._create_window()

    @property
    def side_question_window(self) -> "TextArea | None":
        """The panel's window, or None before `init_side_question_state`."""
        return self._window

    @property
    def is_active(self) -> bool:
        """Whether the panel is currently shown."""
        return self._is_active

    def has_rows(self) -> bool:
        """Whether the docked panel is up and has a row to paint.

        A docked panel whose content height is zero still spends the `Frame`'s
        border rows, so the layout shows an empty box and the transcript pays
        for it. The container is gated on this instead of `is_active`.
        """
        return self._is_active and self.panel_rows() > 0

    def begin(self, question: str) -> object:
        """Open the panel for *question*, replacing any previous answer.

        Returns the token that `end`, `fail` and `cancel` must present: a
        token from an earlier question no longer matches, so its answer is
        dropped instead of being shown under this question.
        """
        self._question = question.strip()
        self._request = request = object()
        self._last_answer = None
        self._shown_body = None
        if panel_row_cap(self._ui) <= 0:
            # No rows to dock into: the frame would spend the layout's border
            # rows painting nothing at all. The question goes to the transcript
            # at this size, and `end` puts the answer there with it.
            self._is_active = False
            append_notice(self._ui, f"\n💭 {self._question}\n")
            self._invalidate()
            return request
        self._is_active = True
        self._fill(self._echo(_PENDING))
        # The panel takes the focus while it is shown, so Up/Down scroll the
        # answer instead of recalling a message into the input. A prompt that is
        # waiting for the user keeps it: that field is what the turn is blocked
        # on, and `/btw` is routed ahead of a pending approval rather than after.
        if not self._ui.is_waiting_for_answer:
            focus_widget(self._window, "Side-question")
        self._invalidate()
        return request

    def is_current(self, request: object | None) -> bool:
        """Whether *request* is the question the panel is showing now."""
        return request is None or request is self._request

    def end(self, answer: str, request: object | None = None) -> None:
        """Show the finished answer, rendered at the pane's width.

        An answer whose panel was replaced or dismissed is dropped; the token
        belongs only to the question that opened it.
        """
        if not self.is_current(request):
            return
        self._last_answer = answer
        if not self._is_active:
            # Opened into the transcript for want of room: the answer follows
            # the question there instead of into a panel that never appeared.
            self._ui.append_answer(answer)
            return
        self._render_and_fill(answer)

    def show(self, title: str, body: str) -> None:
        """Show *title* and *body* until dismissed — a command's reply panel.

        The body is laid out by its writer (`/usage` draws a fixed-width
        table), so it is shown as written: no markdown pass, and nothing for
        `rewrap` to redo. The panel is shared with `/btw`, and whatever asked
        for it last owns it — a side answer still on its way is dropped rather
        than painted over this, because its token no longer matches.
        """
        self._question = title.strip()
        self._request = None
        self._last_answer = None
        self._shown_body = body
        if panel_row_cap(self._ui) <= 0:
            # No rows to dock into: a reply written only into the hidden buffer
            # would never be seen, so it goes to the transcript the way
            # `BaseUI.show_panel` prints one.
            self._is_active = False
            append_notice(self._ui, f"\n{self._question}\n{body}\n")
            self._shown_body = None
            self._invalidate()
            return
        self._is_active = True
        self._fill(f"  {self._question}\n{body}")
        if not self._ui.is_waiting_for_answer:
            focus_widget(self._window, "Panel")
        self._invalidate()

    def rewrap(self) -> None:
        """Re-render the shown answer at the current width (public API).

        `end` renders markdown to plain styled lines once; without this, a
        resize after the answer lands would leave it wrapped for the old
        width. Called from the app's after-render hook, so it runs on every
        frame — a no-op unless an answer is showing and the width changed.

        A raw character offset is not a stable anchor across a re-wrap: the
        same number of characters can now precede different content once the
        line lengths change. `_cursor_for_rewrap` resolves the reader's
        position to something that survives that — the end of the buffer, or
        a (line, column) pair — before the new text exists to re-measure it
        against.
        """
        if not self._is_active or self._last_answer is None:
            return
        if self._ui.output_field_width == self._rendered_width:
            return
        self._render_and_fill(self._last_answer, self._cursor_for_rewrap())

    def _cursor_for_rewrap(self) -> "int | tuple[int, int] | None":
        """The reader's position, anchored for `_fill` to re-find in the new text.

        `None` (the new end) when they were at the old text's end — the
        common case of watching a long answer stream in. Otherwise a
        (line, column) pair: not an exact character match (a word that moves
        lines still lands at the start of wherever its line went), but close
        enough that a resize leaves the reader on the content they were
        reading rather than wherever a stale raw offset now falls.
        """
        window = self._window
        if window is None:
            return 0
        text, cursor = window.buffer.text, window.buffer.cursor_position
        if cursor >= len(text):
            return None
        return _line_and_column(text, cursor)

    def fail(self, message: str, request: object | None = None) -> None:
        """Show why the side question could not be answered."""
        if not self.is_current(request):
            return
        self._last_answer = None
        if not self._is_active:
            # Opened into the transcript for want of room: the failure belongs
            # there too, not in a panel nobody can see.
            append_notice(self._ui, f"  ❌ {message}\n")
            return
        self._fill(self._echo(f"  ❌ {message}\n"))

    def fall_back_when_unpaintable(self) -> None:
        """Move a side answer the terminal shrank away from into the transcript.

        The panel leaves the layout once it has no rows, but it is still what
        `end` writes into: the answer would land in a buffer nobody paints, and
        the question would never be read either. Closing it here is the same
        move `begin` makes on a screen that never had the rows — after this,
        `end` appends the answer to the transcript, because that is where an
        inactive panel's answer goes.
        """
        if not self._is_active:
            return
        if panel_row_cap(self._ui) > 0:
            return
        self._is_active = False
        # The token stays: the answer still belongs to this question, and it is
        # about to be written to the transcript under it.
        append_notice(self._ui, f"\n💭 {self._question}\n")
        if self._shown_body is not None:
            # A command reply the panel was showing: the body is nowhere else.
            append_notice(self._ui, f"{self._shown_body}\n")
            self._shown_body = None
        if self._last_answer is not None:
            # An answer that already arrived: the panel was the only place it
            # lived, so it moves with the question rather than vanishing behind
            # a panel that no longer has a row to paint.
            self._ui.append_answer(self._last_answer)
            self._last_answer = None
        self._fill("")
        focus_widget(self._ui.input_field, "Input-field")
        self._invalidate()

    def cancel(self, request: object | None = None) -> None:
        """Close the panel if *request* is the question it is showing.

        Cancelling an older background task must not close a panel a newer
        `/btw` opened.
        """
        if not self.is_current(request):
            return
        self.dismiss()

    def dismiss(self) -> None:
        """Close the panel and return focus to the input box."""
        if not self._is_active:
            # A question that never had rows went to the transcript instead of
            # the panel. Closing it still drops the token: otherwise a background
            # answer landing afterwards passes the "still current" check and
            # prints under a question the user already closed.
            self._request = None
            return
        self._is_active = False
        self._request = None
        self._last_answer = None
        self._shown_body = None
        self._fill("")
        focus_widget(self._ui.input_field, "Input-field")
        self._invalidate()

    def handle_typed_text(self, data: str) -> None:
        """Type *data* into the input while the panel has the focus.

        The panel is a read-only answer view: a character typed into it starts a
        message instead. A selected passage is being read or copied, not typed
        over, and a key's own encoding (an escape sequence, a control character)
        is not message text.
        """
        window = self._window
        if window is not None and window.buffer.selection_state:
            return
        if not is_message_text(data):
            return
        self._ui.insert_input_text(data)

    def _echo(self, body: str) -> str:
        return f"💭 {self._question}\n\n{body}"

    def _render(self, answer: str) -> str:
        """Render markdown to what the panel's lexer expects: styled lines."""
        return self._ui.render_markdown(answer, self._ui.output_field_width)

    def _render_and_fill(
        self, answer: str, cursor_position: "int | tuple[int, int] | None" = 0
    ) -> None:
        """Render `answer` at the current width and fill the panel with it.

        Records the width it rendered at, so `rewrap` can tell a stale render
        from a current one.
        """
        self._rendered_width = self._ui.output_field_width
        self._fill(self._echo(self._render(answer)), cursor_position)

    def _fill(
        self, text: str, cursor_position: "int | tuple[int, int] | None" = 0
    ) -> None:
        """Replace the panel's text, placing the cursor at `cursor_position`.

        Defaults to the first line — the read naturally starts there for a
        new question's answer, failure, or pending message. `rewrap` instead
        passes `None` for the new text's end (a reader who was at the old
        text's end), a `(line, column)` pair resolved against the *new* text
        (a reader who was elsewhere — a raw offset from the old text could
        now land on different content), or an int for its own non-rewrap
        defaults.
        """
        window = self._window
        if window is None:
            return
        # lazy: heavy third-party
        from prompt_toolkit.document import Document

        if cursor_position is None:
            position = len(text)
        elif isinstance(cursor_position, tuple):
            position = _offset_of(text, *cursor_position)
        else:
            position = min(cursor_position, len(text))
        # The panel is read-only: only the panel itself writes its text.
        window.buffer.set_document(
            Document(text, cursor_position=position), bypass_readonly=True
        )
        self._invalidate()

    def _create_window(self) -> "TextArea":
        # lazy: heavy third-party
        from prompt_toolkit.widgets import TextArea

        # lazy: heavy third-party — the ANSI lexer the output pane also uses
        from zrb.llm.ui.default.app.lexer import CLIStyleLexer

        panel = TextArea(
            text="",
            read_only=True,
            wrap_lines=True,
            scrollbar=False,
            height=panel_content_height(self.panel_rows),
            focusable=True,
            lexer=CLIStyleLexer(),
            style="class:side-question",
        )
        # TextArea takes no `key_bindings` argument; attach them to its control.
        panel.control.key_bindings = self._create_keybindings()
        return panel

    def side_question_panel(self) -> "AnyContainer":
        """The framed panel, docked above the input while a side answer is up.

        A panel whose input is dead may stand in the input frame's place; a
        panel that keeps the input alive docks above it. Typing here starts a
        message in the input (`handle_typed_text`), so hiding the input would
        make that typing blind.
        """
        # lazy: heavy third-party
        from prompt_toolkit.widgets import Frame

        if self._window is None:
            raise RuntimeError(
                "init_side_question_state was not called before side_question_panel"
            )
        return Frame(
            self._window,
            title="Side question · esc closes",
            style="class:side-question-frame",
            height=framed_panel_height(self.panel_rows),
        )

    def panel_rows(self) -> int:
        """Rows the panel paints: its own fixed height, capped for the screen.

        `PANEL_HEIGHT` is the panel's own scheme — a body of that many rows that
        scrolls itself, with `PANEL_PAGE_ROWS` for PageUp/PageDown. A short
        terminal lowers it to the cap instead of pushing the transcript off the
        bottom; it never grows past `PANEL_HEIGHT` for a longer answer.
        """
        return min(PANEL_HEIGHT, panel_row_cap(self._ui))

    def _create_keybindings(self) -> "KeyBindings":
        """Bind the keys a focused panel receives — the panel holds the focus.

        Up/Down (with PageUp/PageDown/Home/End) move the panel's cursor, which
        scrolls the answer: `up` here must not reach the input field's own `up`,
        which recalls a queued message. Typing is not bound here: the
        application-level catch-all forwards it while the panel is focused.
        Enter closes the panel without submitting the draft; Esc also closes it.
        Other exact application bindings still win over the catch-all.
        """
        # lazy: heavy third-party
        from prompt_toolkit.key_binding import KeyBindings

        kb = KeyBindings()

        @kb.add("enter")
        def _(event):
            self.dismiss()

        @kb.add("escape")
        def _(event):
            self.dismiss()

        @kb.add("up")
        def _(event):
            event.current_buffer.cursor_up()

        @kb.add("down")
        def _(event):
            event.current_buffer.cursor_down()

        @kb.add("pageup")
        def _(event):
            event.current_buffer.cursor_up(count=PANEL_PAGE_ROWS)

        @kb.add("pagedown")
        def _(event):
            event.current_buffer.cursor_down(count=PANEL_PAGE_ROWS)

        @kb.add("home")
        def _(event):
            event.current_buffer.cursor_position = 0

        @kb.add("end")
        def _(event):
            event.current_buffer.cursor_position = len(event.current_buffer.text)

        return kb

    def _invalidate(self) -> None:
        invalidate_app("Side-question")


def is_message_text(data: str) -> bool:
    """Whether *data* is text the user typed rather than a key's own encoding.

    Reject terminal controls (including escape sequences), not all characters
    `str.isprintable()` rejects: a typed non-breaking space or emoji joiner
    belongs in the input field too.
    """
    return bool(data) and all(unicodedata.category(char) != "Cc" for char in data)


def _line_and_column(text: str, offset: int) -> tuple[int, int]:
    """The 0-indexed (line, column) `offset` falls on within `text`."""
    before = text[:offset]
    line = before.count("\n")
    column = len(before) - (before.rfind("\n") + 1)
    return line, column


def _offset_of(text: str, line: int, column: int) -> int:
    """The character offset of `(line, column)` within `text`, clamped to it.

    An out-of-range line or column lands on `text`'s nearest edge instead of
    raising — the caller resolved the pair against a different (older) text,
    so a shorter new one is expected, not a bug to surface here.
    """
    lines = text.split("\n")
    line = max(0, min(line, len(lines) - 1))
    column = max(0, min(column, len(lines[line])))
    return sum(len(earlier) + 1 for earlier in lines[:line]) + column
