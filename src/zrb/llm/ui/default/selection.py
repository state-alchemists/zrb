"""Arrow-key multiple-choice widget for the default `UI`.

Renders an `AskUserQuestion` `ChoiceSpec` as an in-layout selectable list
(no nested `Application` — that would fight the running full-screen app for
the terminal). The widget is a focusable `Window` shown as a `Float`; its own
key bindings drive selection and resolve the active confirmation future via
`UIConfirmation.resolve_current`.

Selection model:
  - single-select: ↑/↓ move the cursor, Enter confirms the highlighted option.
  - multi-select: ↑/↓ move, Space toggles, Enter confirms all checked options.
  - a synthetic "✎ Type my own answer…" row drops to free-text: the widget
    closes, focus returns to the input field, and the next Enter resolves the
    same future with the typed text (via `handle_confirmation`).

Panel layering: the question's `context` (the facts needed to answer) renders
above the question, muted, and an option marked `recommended` carries a ★ in
its gutter. The panel grows with the context up to a share of the terminal
height, then the context is ellipsized so the options stay reachable.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from typing import TYPE_CHECKING

from zrb.llm.tool_call.choice_spec_format import get_option_label
from zrb.llm.ui.default.app.focus import focus_widget, invalidate_app
from zrb.util.cli.terminal import get_terminal_size

if TYPE_CHECKING:
    from prompt_toolkit.formatted_text import StyleAndTextTuples
    from prompt_toolkit.layout import Window

    from zrb.llm.ui.default.confirmation import UIConfirmation
    from zrb.llm.ui.default.ui import UI


FREE_TEXT_LABEL = "✎ Type my own answer…"

# Gutter glyph on a row whose option is the one the model advises.
RECOMMENDED_MARK = "★"

# The panel may take at most this share of the terminal's rows: enough to read
# the context without ever pushing the options off screen.
CHOICE_HEIGHT_SHARE = 0.4

# What a truncated context ends on.
ELLIPSIS = "…"


@dataclass(frozen=True)
class _Row:
    """One selectable row: an option, or the synthetic free-text one."""

    index: int
    label: str
    description: str = ""
    recommended: bool = False
    is_free_text: bool = False


class UISelection:
    """In-layout selection widget; pairs with `UIConfirmation`.

    Holds the `UIConfirmation` sibling directly so `handle_confirmation`'s
    fallback cannot loop back through `UI.handle_confirmation`, which
    dispatches here first.
    """

    def __init__(self, ui: "UI", confirmation: "UIConfirmation") -> None:
        self._ui = ui
        self._confirmation = confirmation

    def init_selection_state(self) -> None:
        """Initialize choice state and build the (hidden) widget."""
        self._active_choice: dict | None = None
        self._choice_cursor: int = 0
        self._choice_selected: set[int] = set()
        # Pending free-text capture: the checked labels to prepend to the typed
        # answer (None = none pending), plus the question and its context for
        # the echo.
        self._choice_freetext_prefix: str | None = None
        self._choice_freetext_question: str = ""
        self._choice_freetext_context: str = ""
        self._choice_window = self._create_choice_window()

    def has_active_choice(self) -> bool:
        """Whether a choice widget is currently being shown (public API).

        Viewing a sub-agent supersedes the choice: its live view owns the
        panes, and its Enter routes to the agent's confirmation first.
        """
        return (
            getattr(self._ui, "viewing_agent_id", None) is None
            and self._active_choice is not None
        )

    @property
    def choice_cursor(self) -> int:
        """Index of the highlighted row in the active choice widget."""
        return self._choice_cursor

    @property
    def choice_selected(self) -> "set[int]":
        """Indices checked so far in a multi-select choice widget."""
        return self._choice_selected

    @property
    def choice_window(self) -> "Window | None":
        """The choice widget's window (None before `init_selection_state`)."""
        return getattr(self, "_choice_window", None)

    # hooks called by UIConfirmation

    def begin_choice(self, spec: dict) -> None:
        self._active_choice = spec
        self._choice_cursor = 0
        self._choice_selected = set()
        # The question is echoed into scrollback with the answer on resolve.
        focus_widget(self._choice_window, "Choice-window")

    def end_choice(self) -> None:
        self._choice_freetext_prefix = None
        self._choice_freetext_question = ""
        self._choice_freetext_context = ""
        if self._active_choice is None:
            return
        self._active_choice = None
        self._choice_cursor = 0
        self._choice_selected = set()
        focus_widget(self._ui.input_field, "Input-field")

    # widget construction

    def _create_choice_window(self) -> "Window":
        # lazy: heavy third-party
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import Window
        from prompt_toolkit.layout.controls import FormattedTextControl

        kb = KeyBindings()

        @kb.add("up")
        def _(event):
            self._move_cursor(-1)

        @kb.add("down")
        def _(event):
            self._move_cursor(1)

        @kb.add("space")
        def _(event):
            self._toggle_current()

        @kb.add("enter")
        def _(event):
            self._confirm_choice()

        control = FormattedTextControl(
            self.get_choice_text, focusable=True, key_bindings=kb
        )
        # Backstop for `get_choice_text`'s own wrapping: a mis-measured line
        # (wide glyph, resize mid-paint) wraps instead of clipping.
        return Window(
            content=control,
            style="class:choice",
            dont_extend_height=True,
            wrap_lines=True,
        )

    # state transitions (public-testable seams)

    def move_choice_cursor(self, delta: int) -> None:
        """Move the selection cursor by `delta`, clamped (public API)."""
        self._move_cursor(delta)

    def toggle_choice_current(self) -> None:
        """Toggle the highlighted option in multi-select (public API)."""
        self._toggle_current()

    def confirm_choice(self) -> None:
        """Confirm the current selection, resolving the future (public API)."""
        self._confirm_choice()

    def _row_count(self) -> int:
        # options + the synthetic free-text row
        return (
            len(self._active_choice.get("options", [])) + 1
            if self._active_choice
            else 0
        )

    def _free_text_row(self) -> int:
        return self._row_count() - 1

    def _move_cursor(self, delta: int) -> None:
        if self._active_choice is None:
            return
        count = self._row_count()
        self._choice_cursor = max(0, min(count - 1, self._choice_cursor + delta))
        self._invalidate()

    def _toggle_current(self) -> None:
        if self._active_choice is None or not self._active_choice.get("multi_select"):
            return
        if self._choice_cursor == self._free_text_row():
            return
        if self._choice_cursor in self._choice_selected:
            self._choice_selected.discard(self._choice_cursor)
        else:
            self._choice_selected.add(self._choice_cursor)
        self._invalidate()

    def _confirm_choice(self) -> None:
        if self._active_choice is None:
            return
        spec = self._active_choice
        options = spec.get("options", [])
        question = spec.get("question", "")

        # Free-text row: close the widget and leave the future pending for the
        # input field's next Enter; checked options become the answer's prefix.
        if self._choice_cursor == self._free_text_row():
            prefix = ""
            if spec.get("multi_select"):
                checked = sorted(self._choice_selected)
                prefix = ", ".join(
                    get_option_label(options[i], i)
                    for i in checked
                    if 0 <= i < len(options)
                )
            context = spec.get("context", "")
            self.end_choice()
            self._choice_freetext_prefix = prefix
            self._choice_freetext_question = question
            self._choice_freetext_context = context
            self._append_now("\n  ✎ Type your answer and press Enter:\n")
            self._invalidate()
            return

        if spec.get("multi_select"):
            indices = sorted(self._choice_selected) or [self._choice_cursor]
        else:
            indices = [self._choice_cursor]
        labels = [
            get_option_label(options[i], i) for i in indices if 0 <= i < len(options)
        ]
        answer = ", ".join(labels)
        echo = self._answer_echo(question, answer, spec.get("context", ""))
        self._ui.resolve_current(answer, echo=echo)

    def _answer_echo(self, question: str, answer: str, context: str = "") -> str:
        """Scrollback record left after the widget closes: question + answer.

        The whole context is recorded here — the panel truncates it to fit on
        screen, so scrollback is where its long form lives.
        """
        quoted = "".join(f"  {line}\n" for line in context.splitlines())
        return f"\n❓ {question}\n{quoted}  ✔ {answer}\n"

    def handle_confirmation(self, event) -> bool:
        """Resolve a pending free-text capture, combining any checked options.

        When free-text was reached from a multi-select choice, the typed text is
        appended after the previously-checked option labels. Falls through to the
        plain text-confirmation handler when no choice free-text is pending.
        """
        prefix = self._choice_freetext_prefix
        if prefix is None:
            return self._confirmation.handle_confirmation(event)
        buff = event.current_buffer
        typed = buff.text.strip()
        question = self._choice_freetext_question
        context = self._choice_freetext_context
        self._choice_freetext_prefix = None
        self._choice_freetext_question = ""
        self._choice_freetext_context = ""
        combined = ", ".join(part for part in (prefix, typed) if part)
        # Clear the typed answer before resolving so the restored draft (stashed
        # when the confirmation activated) is not wiped afterwards.
        buff.reset()
        echo = self._answer_echo(question, combined, context)
        self._ui.resolve_current(combined, echo=echo)
        return True

    # rendering

    def get_choice_text(self) -> "StyleAndTextTuples":
        spec = self._active_choice
        if spec is None:
            return []
        width = self._wrap_width()
        body = self._body_frags(spec, width)
        return self._context_frags(spec, width, body) + body

    def _body_frags(self, spec: dict, width: int) -> "StyleAndTextTuples":
        """The question, the rows and the key hint — everything but the context."""
        multi = bool(spec.get("multi_select"))
        idx, total = spec.get("index", 1), spec.get("total", 1)
        counter = f"  ({idx}/{total})" if total > 1 else ""
        question = f"{spec.get('question', '')}{counter}"
        rows = self._rows(spec)
        frags: StyleAndTextTuples = [
            ("class:choice.question bold", f" {line}\n")
            for line in _wrap(question, width - 1)
        ]
        for row in rows:
            frags.append(("class:choice.option", "\n"))
            frags += self._render_row(row, multi, width)
        hint = (
            " ↑/↓ move · space toggle · enter confirm · esc cancel"
            if multi
            else " ↑/↓ move · enter confirm · esc cancel"
        )
        if any(row.recommended for row in rows):
            hint += f" · {RECOMMENDED_MARK} recommended"
        frags.append(("class:choice.hint", f"\n{hint}\n"))
        return frags

    def _context_frags(
        self, spec: dict, width: int, body: "StyleAndTextTuples"
    ) -> "StyleAndTextTuples":
        """The context, above the question, clamped to the panel's height budget."""
        context = spec.get("context") or ""
        lines = _wrap(context, width - 1)
        if not lines:
            return []
        # `_height_cap` bounds the context, not the whole panel: the question,
        # the rows and the hint are painted whatever happens. Two rows stay
        # reserved — one under the panel, one for the blank line that separates
        # the context from the question — so what is left over is the real
        # budget. Measuring the panel against the cap instead (`cap - body - 1`)
        # subtracted the body twice and left a 24-row terminal with a negative
        # budget, so a one-line context was dropped for want of arithmetic
        # rather than for want of room.
        budget = min(
            self._height_cap(),
            self._terminal_lines() - _painted_lines(body) - 2,
        )
        lines = _clamp_lines(lines, budget, width - 1)
        if not lines:
            # No room at all: the options matter more than the context, and the
            # full context is still recorded in scrollback with the answer.
            return []
        frags: StyleAndTextTuples = [
            ("class:choice.context", f" {line}\n") for line in lines
        ]
        frags.append(("class:choice.context", "\n"))
        return frags

    def _rows(self, spec: dict) -> "list[_Row]":
        """Every selectable row: the options, then the synthetic free-text one."""
        rows = [
            _Row(
                index=i,
                label=get_option_label(opt, i),
                description=opt.get("description", ""),
                recommended=bool(opt.get("recommended")),
            )
            for i, opt in enumerate(spec.get("options", []))
        ]
        rows.append(_Row(self._free_text_row(), FREE_TEXT_LABEL, is_free_text=True))
        return rows

    def _render_row(self, row: "_Row", multi: bool, width: int) -> "StyleAndTextTuples":
        """One row: its gutter-marked label, then its description beneath it.

        Paragraph-long descriptions would bury an inline label, so they go
        beneath it; continuation lines indent to the label's column so a wrap
        never reads as a new option. The ★ lives in the gutter, so a marked
        option's label stays the plain label an answer resolves to.
        """
        i = row.index
        is_cursor = i == self._choice_cursor
        cursor = "❯ " if is_cursor else "  "
        if row.is_free_text:
            marker = "  "
        elif multi:
            marker = "[x] " if i in self._choice_selected else "[ ] "
        else:
            marker = "◉ " if is_cursor else "◯ "
        star = f"{RECOMMENDED_MARK} " if row.recommended else "  "
        style = "class:choice.selected" if is_cursor else "class:choice.option"
        # The highlight covers the description too, as one continuous bar.
        desc_style = style if is_cursor else "class:choice.desc"
        gutter = f" {cursor}{marker}{star}"
        indent = " " * len(gutter)
        out: StyleAndTextTuples = []
        for line in _wrap(row.label, width - len(gutter)) or [""]:
            out.append((style, self._fill(f"{gutter}{line}", width, is_cursor)))
            gutter = indent
        for line in _wrap(row.description, width - len(indent)):
            out.append((desc_style, self._fill(f"{indent}{line}", width, is_cursor)))
        return out

    def _fill(self, line: str, width: int, is_cursor: bool) -> str:
        """Pad a highlighted line to full width so the bar has no ragged edge."""
        return (line.ljust(width) if is_cursor else line) + "\n"

    def _wrap_width(self) -> int:
        """Usable text width inside the choice float.

        Four columns go to the full-width `Frame`'s border and padding; falls
        back to a default when the width is unknown.
        """
        columns = getattr(self._ui, "output_field_width", None)
        return max(24, (columns or 84) - 4)

    def _height_cap(self) -> int:
        """Rows the context may paint: a share of the terminal, never all of it.

        A ceiling on the context, not on the panel: what a short screen cannot
        hold is decided against `_terminal_lines` in `_context_frags`, so this
        only stops a long context from dominating a tall one.
        """
        return max(1, int(self._terminal_lines() * CHOICE_HEIGHT_SHARE))

    def _terminal_lines(self) -> int:
        """Terminal rows.

        The running application first — its output is a dup of the real stdout,
        while `get_terminal_size` may read a redirected fd and disagree with
        what the renderer is painting.
        """
        app = self._running_application()
        if app is not None:
            try:
                return app.output.get_size().rows
            except (AttributeError, OSError, ValueError):
                # A redirected or console-less output: fall through to the
                # terminal probe, the same fallback `output_field_width` uses.
                pass
        return get_terminal_size().lines

    def _running_application(self):
        """The live prompt_toolkit application, or None before it is built."""
        if not getattr(self._ui, "is_application_built", False):
            return None
        return getattr(self._ui, "application", None)

    # helpers

    def _append_now(self, text: str) -> None:
        """Append to output now, bypassing the confirmation buffer guard.

        `append_to_output` buffers output while a confirmation is pending, and
        the free-text future still is, so the slot is cleared for the write.
        """
        saved = self._ui.confirmation.current
        self._ui.confirmation.current = None
        self._ui.append_to_output(text, kind="text")
        self._ui.confirmation.current = saved

    def _invalidate(self) -> None:
        invalidate_app("Choice-widget")


def _wrap(text: str, width: int) -> list[str]:
    """Word-wrap `text` to `width`, or `[]` when there is nothing to wrap."""
    if not text:
        return []
    return textwrap.wrap(text, max(10, width)) or [""]


def _painted_lines(frags: "StyleAndTextTuples") -> int:
    """How many terminal lines *frags* paint."""
    return "".join(frag[1] for frag in frags).count("\n")


def _clamp_lines(lines: list[str], budget: int, width: int) -> list[str]:
    """At most *budget* of *lines*, the last one ellipsized when some were cut."""
    if budget <= 0:
        return []
    if len(lines) <= budget:
        return lines
    kept = lines[:budget]
    kept[-1] = _ellipsize(kept[-1], width)
    return kept


def _ellipsize(line: str, width: int) -> str:
    """*line* ending in an ellipsis, dropping a word rather than overflow."""
    if len(line) + len(ELLIPSIS) > width:
        line = line.rsplit(" ", 1)[0] if " " in line.strip() else line[:-1]
    return f"{line.rstrip()}{ELLIPSIS}"
