"""A choice rendered as numbered text, for a UI with no widget of its own.

`AnyUIPicker` exists so a backend can render a structured question its own way.
A backend with no way to draw one — a log file, a pipe, a plain REPL — still has
`ask_user`, so the question is formatted as numbered text and asked as text.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from zrb.llm.ui.any_ui_picker import AnyUIPicker
from zrb.llm.util.choice_spec_format import format_choice_spec

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from zrb.llm.ui.any_ui_picker import ChoiceSpec


class TextPicker(AnyUIPicker):
    """Ask a choice as numbered text through the host's `ask_user`."""

    def __init__(self, ask_user: "Callable[..., Awaitable[str]]") -> None:
        self._ask_user = ask_user

    async def ask_user_choice(
        self, spec: "ChoiceSpec", agent_id: str | None = None
    ) -> str:
        """Format *spec* as numbered text and ask it as a free-text question."""
        return await self._ask_user(format_choice_spec(spec), agent_id=agent_id)
