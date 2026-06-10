"""Arrow-key multiple-choice widget for the default `UI`.

Renders an `AskUserQuestion` `ChoiceSpec` as an in-layout selectable list
(no nested `Application` — that would fight the running full-screen app for
the terminal). The widget is a focusable `Window` shown as a `Float`; its own
key bindings drive selection and resolve the active confirmation future via
`ConfirmationMixin._resolve_current`.

Selection model:
  - single-select: ↑/↓ move the cursor, Enter confirms the highlighted option.
  - multi-select: ↑/↓ move, Space toggles, Enter confirms all checked options.
  - a synthetic "✎ Type my own answer…" row drops to free-text: the widget
    closes, focus returns to the input field, and the next Enter resolves the
    same future with the typed text (via `_handle_confirmation`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from prompt_toolkit.formatted_text import StyleAndTextTuples
    from prompt_toolkit.layout import Window


class SelectionMixin:
    """In-layout selection widget; pairs with `ConfirmationMixin`."""

    # Host-class contract: `_input_field`/`append_to_output` come from the
    # default `UI`/`OutputMixin`; resolution from `ConfirmationMixin`.
    if TYPE_CHECKING:
        _input_field: Any
        _current_confirmation: Any

        def append_to_output(self, *values: object, **kwargs: Any) -> None: ...

        def _resolve_current(self, text: str, echo: str | None) -> bool: ...

    def _init_selection_state(self) -> None:
        """Initialize choice state and build the (hidden) widget."""
        self._active_choice: dict | None = None
        self._choice_cursor: int = 0
        self._choice_selected: set[int] = set()
        # Set when dropping to free-text from a (multi-select) choice: the
        # already-selected labels to prepend to the typed answer. None means no
        # free-text capture is pending. The question is stashed alongside so the
        # resolved echo can still record it after the widget has closed.
        self._choice_freetext_prefix: str | None = None
        self._choice_freetext_question: str = ""
        self._choice_window = self._create_choice_window()

    def has_active_choice(self) -> bool:
        """Whether a choice widget is currently being shown (public API)."""
        return self._active_choice is not None

    @property
    def choice_window(self) -> "Window":
        return self._choice_window

    # --- hooks called by ConfirmationMixin -------------------------------

    def _begin_choice(self, spec: dict) -> None:
        # lazy: heavy third-party
        from prompt_toolkit.application import get_app

        self._active_choice = spec
        self._choice_cursor = 0
        self._choice_selected = set()
        # The question is shown inside the widget while active and echoed into
        # scrollback (with the answer) on resolve — not duplicated here.
        try:
            get_app().layout.focus(self._choice_window)
        except Exception:
            # Layout not ready (e.g. before first render) — focus on next paint.
            pass

    def _end_choice(self) -> None:
        self._choice_freetext_prefix = None
        self._choice_freetext_question = ""
        if self._active_choice is None:
            return
        self._active_choice = None
        self._choice_cursor = 0
        self._choice_selected = set()
        try:
            # lazy: heavy third-party
            from prompt_toolkit.application import get_app

            get_app().layout.focus(self._input_field)
        except Exception:
            pass

    # --- widget construction --------------------------------------------

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
            self._get_choice_text, focusable=True, key_bindings=kb
        )
        return Window(content=control, style="class:choice", dont_extend_height=True)

    # --- state transitions (public-testable seams) -----------------------

    def move_choice_cursor(self, delta: int) -> None:
        """Move the selection cursor by `delta`, clamped (public API)."""
        self._move_cursor(delta)

    def toggle_choice_current(self) -> None:
        """Toggle the highlighted option in multi-select (public API)."""
        self._toggle_current()

    def confirm_choice(self) -> bool:
        """Confirm the current selection, resolving the future (public API)."""
        return self._confirm_choice()

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

    def _confirm_choice(self) -> bool:
        if self._active_choice is None:
            return False
        spec = self._active_choice
        options = spec.get("options", [])
        question = spec.get("question", "")

        # Free-text row: close the widget, keep the future pending, and let the
        # next Enter in the input field resolve it via _handle_confirmation.
        # In multi-select, any already-checked options are carried as a prefix
        # so the final answer is "those options + the typed text".
        if self._choice_cursor == self._free_text_row():
            prefix = ""
            if spec.get("multi_select"):
                checked = sorted(self._choice_selected)
                prefix = ", ".join(
                    options[i].get("label", str(i))
                    for i in checked
                    if 0 <= i < len(options)
                )
            self._end_choice()  # clears prefix/question...
            self._choice_freetext_prefix = prefix  # ...then arm free-text capture
            self._choice_freetext_question = question
            self._append_now("\n  ✎ Type your answer and press Enter:\n")
            self._invalidate()
            return True

        if spec.get("multi_select"):
            indices = sorted(self._choice_selected) or [self._choice_cursor]
        else:
            indices = [self._choice_cursor]
        labels = [
            options[i].get("label", str(i)) for i in indices if 0 <= i < len(options)
        ]
        answer = ", ".join(labels)
        self._resolve_current(answer, echo=self._answer_echo(question, answer))
        return True

    def _answer_echo(self, question: str, answer: str) -> str:
        """Scrollback record left after the widget closes: question + answer."""
        return f"\n❓ {question}\n  ✔ {answer}\n"

    def _handle_confirmation(self, event) -> bool:
        """Resolve a pending free-text capture, combining any checked options.

        When free-text was reached from a multi-select choice, the typed text is
        appended after the previously-checked option labels. Falls through to the
        plain text-confirmation handler when no choice free-text is pending.
        """
        prefix = self._choice_freetext_prefix
        if prefix is None:
            return super()._handle_confirmation(event)
        buff = event.current_buffer
        typed = buff.text.strip()
        question = self._choice_freetext_question
        self._choice_freetext_prefix = None
        self._choice_freetext_question = ""
        combined = ", ".join(part for part in (prefix, typed) if part)
        self._resolve_current(combined, echo=self._answer_echo(question, combined))
        buff.reset()
        return True

    # --- rendering -------------------------------------------------------

    def _get_choice_text(self) -> "StyleAndTextTuples":
        spec = self._active_choice
        if spec is None:
            return []
        multi = bool(spec.get("multi_select"))
        idx, total = spec.get("index", 1), spec.get("total", 1)
        counter = f"  ({idx}/{total})" if total > 1 else ""
        frags: StyleAndTextTuples = [
            ("class:choice.question bold", f" {spec.get('question', '')}{counter}\n"),
        ]
        for i, opt in enumerate(spec.get("options", [])):
            frags += self._render_row(
                i,
                opt.get("label", f"Option {i + 1}"),
                opt.get("description", ""),
                multi,
            )
        frags += self._render_row(
            self._free_text_row(), "✎ Type my own answer…", "", multi, is_free_text=True
        )
        hint = (
            " ↑/↓ move · space toggle · enter confirm · esc cancel"
            if multi
            else " ↑/↓ move · enter confirm · esc cancel"
        )
        frags.append(("class:choice.hint", f"\n{hint}\n"))
        return frags

    def _render_row(
        self, i: int, label: str, desc: str, multi: bool, is_free_text: bool = False
    ) -> "StyleAndTextTuples":
        cursor = "❯ " if i == self._choice_cursor else "  "
        if is_free_text:
            marker = "  "
        elif multi:
            marker = "[x] " if i in self._choice_selected else "[ ] "
        else:
            marker = "◉ " if i == self._choice_cursor else "◯ "
        is_cursor = i == self._choice_cursor
        style = "class:choice.selected" if is_cursor else "class:choice.option"
        # On the highlighted row the description shares the highlight style so the
        # selection bar reads as one continuous segment.
        desc_style = style if is_cursor else "class:choice.desc"
        row: StyleAndTextTuples = [(style, f" {cursor}{marker}{label}")]
        if desc:
            row.append((desc_style, f"  — {desc}"))
        row.append((style, "\n"))
        return row

    # --- helpers ---------------------------------------------------------

    def _append_now(self, text: str) -> None:
        """Append to output now, bypassing the confirmation buffer guard.

        The guard in `append_to_output` swallows output while a confirmation is
        pending mid-thinking; the free-text future is still pending here, so we
        clear the active slot for the duration of the write.
        """
        saved = self._current_confirmation
        self._current_confirmation = None
        self.append_to_output(text, kind="text")
        self._current_confirmation = saved

    def _invalidate(self) -> None:
        try:
            # lazy: heavy third-party
            from prompt_toolkit.application import get_app

            get_app().invalidate()
        except Exception:
            pass
