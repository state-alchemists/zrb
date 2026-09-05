from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TextIO, TypedDict


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


class AnyUI(ABC):
    """The UI contract every task's `ui` slot is typed against.

    Every built-in implementer (`BaseUI`, `StdUI`, `MultiUI`, `BufferedUI`,
    and everything `BaseUI` itself subclasses — `SimpleUI`/`EventDrivenUI`/
    the default `UI`) explicitly inherits this class, so a
    subclass missing a method fails at instantiation (`TypeError`) rather
    than at first use, deep in a session. A custom UI written per
    `docs/llm/llm-custom-ui.md` gets this for free by
    subclassing `SimpleUI`/`EventDrivenUI`/`BaseUI` — none of
    zrb's own docs show implementing this class directly.
    """

    @abstractmethod
    async def ask_user(
        self,
        prompt: str,
        output_to_parent: str = "",
        agent_id: str | None = None,
    ) -> str:
        """Ask the user a free-text question and return their answer."""

    @abstractmethod
    async def ask_user_choice(
        self, spec: ChoiceSpec, agent_id: str | None = None
    ) -> str:
        """Ask the user a multiple-choice question and return their pick."""

    @abstractmethod
    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ):
        """Write output the way `print()` would, kept for later replay."""

    @abstractmethod
    def stream_to_parent(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ):
        """Write output to a delegating parent UI, not this UI's own stream."""

    @abstractmethod
    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
        """Run an interactive shell command, handing it the real terminal."""

    @abstractmethod
    async def run_async(self) -> Any:
        """Drive this UI's own event loop until the session ends."""
