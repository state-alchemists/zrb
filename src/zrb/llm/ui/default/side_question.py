"""`/btw` side-question panel for the default `UI`.

A side question is answered off to the side and never saved to history, so its
answer must not scroll the transcript the user is reading. `UISideQuestion`
shows it in the same full-width framed float the choice widget uses, just above
the input: the question, then the answer once it arrives, at a fixed height that
scrolls instead of swallowing the screen.

The panel takes the focus while it is shown, so the movement keys walk the
answer instead of the input: Up/Down (with PageUp/PageDown/Home/End) scroll the
panel rather than recalling a queued message, and Esc closes it and gives the
input its focus back. It is a read-only answer view, so typing still starts a
message — a printable key lands in the input without the focus leaving the
panel, keeping the movement keys on the answer for as long as it is up. A panel
that opens while a prompt is waiting for the user keeps the focus where it is:
that field is what the turn is blocked on.

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

from typing import TYPE_CHECKING

from zrb.llm.ui.default.app.focus import focus_widget, invalidate_app

if TYPE_CHECKING:
    from prompt_toolkit.key_binding import KeyBindings
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

    def init_side_question_state(self) -> None:
        """Initialize the panel state and build its (hidden) widget."""
        self._question = ""
        self._is_active = False
        self._request = None
        self._window = self._create_window()

    @property
    def side_question_window(self) -> "TextArea | None":
        """The panel's window, or None before `init_side_question_state`."""
        return self._window

    @property
    def is_active(self) -> bool:
        """Whether the panel is currently shown."""
        return self._is_active

    def begin(self, question: str) -> object:
        """Open the panel for *question*, replacing any previous answer.

        Returns the token that `end`, `fail` and `cancel` must present: a
        token from an earlier question no longer matches, so its answer is
        dropped instead of being shown under this question.
        """
        self._question = question.strip()
        self._is_active = True
        self._request = request = object()
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

        An answer whose question the panel has moved past (a newer `/btw`, or
        Esc) is dropped: the panel belongs to the newer question.
        """
        if not self.is_current(request):
            return
        self._fill(self._echo(self._render(answer)))

    def fail(self, message: str, request: object | None = None) -> None:
        """Show why the side question could not be answered."""
        if not self.is_current(request):
            return
        self._fill(self._echo(f"  ❌ {message}\n"))

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
            return
        self._is_active = False
        self._request = None
        self._fill("")
        focus_widget(self._ui.input_field, "Input-field")
        self._invalidate()

    def _echo(self, body: str) -> str:
        return f"💭 {self._question}\n\n{body}"

    def _render(self, answer: str) -> str:
        """Render markdown to what the panel's lexer expects: styled lines."""
        return self._ui.render_markdown(answer, self._ui.output_field_width)

    def _fill(self, text: str) -> None:
        """Replace the panel's text and scroll back to its first line."""
        window = self._window
        if window is None:
            return
        # lazy: heavy third-party
        from prompt_toolkit.document import Document

        # The panel is read-only: only the panel itself writes its text.
        window.buffer.set_document(
            Document(text, cursor_position=0), bypass_readonly=True
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
            height=PANEL_HEIGHT,
            focusable=True,
            lexer=CLIStyleLexer(),
            style="class:side-question",
        )
        # TextArea takes no `key_bindings` argument; attach them to its control.
        panel.control.key_bindings = self._create_keybindings()
        return panel

    def _create_keybindings(self) -> "KeyBindings":
        """Bind the keys a focused panel receives — the panel holds the focus.

        Up/Down (with PageUp/PageDown/Home/End) move the panel's cursor, which
        scrolls the answer: `up` here must not reach the input field's own `up`,
        which recalls a queued message. A typed character starts a message
        instead — it goes into the input while the focus stays on the panel, so
        the movement keys keep scrolling the answer until the user closes it.
        """
        # lazy: heavy third-party
        from prompt_toolkit.key_binding import KeyBindings

        # lazy: heavy third-party — the wildcard key the catch-all below binds
        from prompt_toolkit.keys import Keys

        kb = KeyBindings()

        def send_to_input(event):
            # A selected passage is being read or copied, not typed over.
            if event.current_buffer.selection_state:
                return
            if not _is_message_text(event.data):
                return
            # A paste, or a dead-key sequence, arrives as one data string: it is
            # forwarded whole rather than a character at a time.
            self._ui.insert_input_text(event.data)

        # `Keys.Any`, not a list of the characters to accept: `string.printable`
        # is ASCII-only, so every character outside it — `é`, `ü`, `🙂` — matched
        # no binding of its own, fell through to the application's `Keys.Any`
        # self-insert and rang the bell on a read-only panel instead of reaching
        # the input. prompt_toolkit sorts an `Any` binding after the exact ones
        # and calls the last match, so the keys bound below still win; it is
        # registered first so that they remain the later of the two.
        kb.add(Keys.Any)(send_to_input)

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


def _is_message_text(data: str) -> bool:
    """Whether *data* is text the user typed rather than a key's own encoding.

    A terminal sends a movement key as an escape sequence (`\\x1b[B` for Down),
    a control key as a control character (`\\x01` for Ctrl+A), and a bare
    modifier as nothing at all; none of those is a character of a message.
    """
    if not data or data.startswith("\x1b"):
        return False
    return data.isprintable()
