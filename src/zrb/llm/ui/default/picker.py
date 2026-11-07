"""The choice widget for the default `UI`: the confirmation queue's selection mode."""

from __future__ import annotations

from typing import TYPE_CHECKING

from zrb.llm.ui.any_ui_picker import AnyUIPicker

if TYPE_CHECKING:
    from zrb.llm.ui.any_ui_picker import ChoiceSpec
    from zrb.llm.ui.default.confirmation import UIConfirmation


class UIPicker(AnyUIPicker):
    """Send the question to the confirmation queue, which owns the widget."""

    def __init__(self, confirmation: "UIConfirmation") -> None:
        self._confirmation = confirmation

    async def ask_user_choice(
        self, spec: "ChoiceSpec", agent_id: str | None = None
    ) -> str:
        """Queue the question and let the selection widget render it."""
        return await self._confirmation.ask_user_choice(spec, agent_id)
