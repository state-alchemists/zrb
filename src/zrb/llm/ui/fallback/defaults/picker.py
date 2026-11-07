"""Inert picker role: a UI with no choice widget renders numbered text.

`AnyUIPicker` exists so a backend can draw a structured question its own way. A
backend with no way to draw one — a log file, a pipe, a plain REPL — still asks
free-text questions, so the spec is formatted as numbered text and asked as one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from zrb.llm.ui.any_ui_picker import AnyUIPicker
from zrb.llm.ui.fallback.text_picker import TextPicker


class UIPickerDefaults:
    """The picker role for a UI that cannot draw a widget."""

    # Built on first use, so a UI that is never asked a choice never builds one;
    # one per instance, because it holds that instance's `ask_user`.
    _uidefaults_picker: AnyUIPicker | None = None

    if TYPE_CHECKING:

        async def ask_user(
            self,
            prompt: str,
            output_to_parent: str = "",
            agent_id: str | None = None,
        ) -> str:
            """The host's question, which the input role declares abstract."""
            ...

    @property
    def picker(self) -> AnyUIPicker:
        """Ask a choice as numbered text: a UI without a widget still answers."""
        if self._uidefaults_picker is None:
            self._uidefaults_picker = TextPicker(self.ask_user)
        return self._uidefaults_picker
