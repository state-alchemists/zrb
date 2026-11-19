"""The UI's choice widget: one structured question, rendered as options."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypedDict


class AnyUIPicker(ABC):
    """The swap point for an arrow-key list, a numbered prompt, or a button row."""

    @abstractmethod
    async def ask_user_choice(
        self, spec: ChoiceSpec, agent_id: str | None = None
    ) -> str:
        """Ask the user a multiple-choice question and return their pick."""


class ChoiceOption(TypedDict, total=False):
    label: str
    description: str
    recommended: bool


class ChoiceSpec(TypedDict, total=False):
    """Structured spec for a single multiple-choice question.

    Carries everything a selection widget needs to render arrow-key choices.
    `index`/`total` drive the "Question 2 of 3" footer. UIs that cannot render
    a widget fall back to formatting this as numbered text (see
    `BaseUI.ask_user_choice`).
    """

    question: str
    options: list[ChoiceOption]
    context: str
    multi_select: bool
    header: str
    index: int
    total: int
