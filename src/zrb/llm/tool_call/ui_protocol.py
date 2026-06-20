from __future__ import annotations

from typing import Any, Protocol, TextIO, TypedDict


class ChoiceOption(TypedDict, total=False):
    label: str
    description: str


class ChoiceSpec(TypedDict, total=False):
    """Structured spec for a single multiple-choice question.

    Carries everything a selection widget needs to render arrow-key choices.
    `index`/`total` drive the "Question 2 of 3" footer. UIs that cannot render
    a widget fall back to formatting this as numbered text (see
    `BaseUI.ask_user_choice`).
    """

    question: str
    options: list[ChoiceOption]
    multi_select: bool
    header: str
    index: int
    total: int


class UIProtocol(Protocol):
    async def ask_user(self, prompt: str) -> str: ...

    async def ask_user_choice(self, spec: ChoiceSpec) -> str: ...

    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ): ...

    def stream_to_parent(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ): ...

    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any: ...

    async def run_async(self) -> Any: ...
