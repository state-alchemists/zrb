"""Arrow-key multiple-choice widget for the default `UI`.

Renders an `AskUserQuestion` `ChoiceSpec` as an in-layout selectable list
(no nested `Application` — that would fight the running full-screen app for
the terminal). The widget is a focusable `Window` in a framed panel that stands
in the input frame's place while a choice is up; its own key bindings drive
selection and resolve the active confirmation future via
`UIConfirmation.resolve_current`.

Selection model:
  - single-select: ↑/↓ move the cursor, Enter confirms the highlighted option.
  - multi-select: ↑/↓ move, Space toggles, Enter confirms all checked options.
  - a synthetic "✎ Type my own answer…" row drops to free-text: the widget
    closes, focus returns to the input field, and the next Enter resolves the
    same future with the typed text (via `handle_confirmation`).

Panel layering: the question's `context` (the facts needed to answer) renders
above the question, muted, and an option marked `recommended` carries a ★ in
its gutter. The panel takes at most a third of the screen (`app/docking.py`),
so a twenty-option question scrolls under the cursor instead of starving the
transcript, and a long context is ellipsized rather than pushing the options
out of view.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from typing import TYPE_CHECKING

from zrb.llm.tool_call.choice_spec_format import get_option_label
from zrb.llm.ui.default.app.docking import (
    RowWindow,
    framed_panel_height,
    panel_row_cap,
    rendered_row_count,
)
from zrb.llm.ui.default.app.focus import focus_widget, invalidate_app

if TYPE_CHECKING:
    from prompt_toolkit.formatted_text import StyleAndTextTuples
    from prompt_toolkit.layout import Window
    from prompt_toolkit.layout.containers import AnyContainer

    from zrb.llm.ui.default.confirmation import UIConfirmation
    from zrb.llm.ui.default.ui import UI


FREE_TEXT_LABEL = "✎ Type my own answer…"

# Gutter glyph on a row whose option is the one the model advises.
RECOMMENDED_MARK = "★"

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
        self._row_window = RowWindow()
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
        self._row_window.reset()
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

    def choice_panel(self) -> "AnyContainer":
        """The framed panel, standing in the input frame's place while it runs.

        A panel whose input is dead may stand in the input frame's place; a
        panel that keeps the input alive docks above it. A choice makes the
        input dead — printable keys reach it only outside a choice
        (`filter=not_choice_active`, `app/keybinding.py`) — so the panel takes
        the input's rows instead of covering the transcript with a float.
        """
        # lazy: heavy third-party
        from prompt_toolkit.widgets import Frame

        return Frame(
            self._choice_window,
            title="Select an answer",
            style="class:choice-frame",
            height=framed_panel_height(self.panel_rows),
        )

    def panel_rows(self) -> int:
        """Rows the panel paints: what the question has to show, capped.

        The rows come out of the transcript, so a twenty-option question must
        not take them all; what does not fit scrolls under the cursor.
        """
        spec = self._active_choice
        if spec is None:
            return 0
        frags, _ = self._render_panel(spec)
        return min(rendered_row_count(frags), panel_row_cap(self._ui))

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
        """The rows the panel paints: at most the cap, scrolled to the cursor."""
        spec = self._active_choice
        if spec is None:
            return []
        frags, cursor_row = self._render_panel(spec)
        return self._row_window.slice(frags, cursor_row, self.panel_rows())

    def _render_panel(self, spec: dict) -> "tuple[StyleAndTextTuples, int]":
        """Every row the panel would paint, and the row the cursor sits on."""
        width = self._wrap_width()
        body, row_starts = self._body_frags(spec, width)
        context = self._context_frags(spec, width, body)
        cursor_row = rendered_row_count(context) + row_starts[self._choice_cursor]
        return context + body, cursor_row

    def _body_frags(
        self, spec: dict, width: int
    ) -> "tuple[StyleAndTextTuples, list[int]]":
        """The question, the rows and the key hint — everything but the context.

        The second value is the painted row each selectable row starts on, so
        the visible slice can be kept on the one the cursor is on.
        """
        multi = bool(spec.get("multi_select"))
        idx, total = spec.get("index", 1), spec.get("total", 1)
        counter = f"  ({idx}/{total})" if total > 1 else ""
        question = f"{spec.get('question', '')}{counter}"
        rows = self._rows(spec)
        frags: StyleAndTextTuples = [
            ("class:choice.question bold", f" {line}\n")
            for line in _wrap(question, width - 1)
        ]
        painted = len(frags)
        row_starts: list[int] = []
        for row in rows:
            frags.append(("class:choice.option", "\n"))
            painted += 1
            row_starts.append(painted)
            row_frags = self._render_row(row, multi, width)
            frags += row_frags
            painted += len(row_frags)
        hint = (
            " ↑/↓ move · space toggle · enter confirm · esc cancel"
            if multi
            else " ↑/↓ move · enter confirm · esc cancel"
        )
        if any(row.recommended for row in rows):
            hint += f" · {RECOMMENDED_MARK} recommended"
        frags.append(("class:choice.hint", f"\n{hint}\n"))
        return frags, row_starts

    def _context_frags(
        self, spec: dict, width: int, body: "StyleAndTextTuples"
    ) -> "StyleAndTextTuples":
        """The context, above the question, clamped to what the cap leaves over."""
        context = spec.get("context") or ""
        lines = _wrap(context, width - 1)
        if not lines:
            return []
        # The cap now holds the whole panel — it is docked into the layout, so
        # its rows come out of the transcript — which makes the context's
        # budget what the question, the rows and the hint leave over, minus the
        # blank line that separates the context from the question. On a screen
        # too short for any of it the options win, and the full context is still
        # recorded in scrollback with the answer.
        budget = panel_row_cap(self._ui) - rendered_row_count(body) - 1
        lines = _clamp_lines(lines, budget, width - 1)
        if not lines:
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
        """Usable text width inside the panel.

        Four columns go to the full-width `Frame`'s border and padding; falls
        back to a default when the width is unknown.
        """
        columns = getattr(self._ui, "output_field_width", None)
        return max(24, (columns or 84) - 4)

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
