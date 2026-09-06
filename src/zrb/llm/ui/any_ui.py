from __future__ import annotations

import asyncio
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

    The contract is in two halves: the six behavioral methods below, which
    every UI performs, and the ten state members and side-effect hooks after
    them, which describe what a *full* UI keeps. `BaseUI` implements all ten;
    a UI that keeps none of it mixes in `UIDefaultsMixin`
    (`llm/ui/defaults.py`).
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

    @property
    @abstractmethod
    def is_thinking(self) -> bool:
        """Whether the assistant is currently producing a response."""

    @is_thinking.setter
    @abstractmethod
    def is_thinking(self, value: bool) -> None: ...

    @property
    @abstractmethod
    def llm_task(self) -> Any:
        """The `LLMTask` driving this UI, or None when it has none."""

    @llm_task.setter
    @abstractmethod
    def llm_task(self, value: Any) -> None: ...

    @property
    @abstractmethod
    def model(self) -> Any:
        """The model this UI is currently talking to, or None."""

    @model.setter
    @abstractmethod
    def model(self, value: Any) -> None: ...

    @property
    @abstractmethod
    def yolo(self) -> bool | frozenset:
        """Auto-approval state: False, True, or the set of auto-approved tools.

        Read-only in the contract. Every assignment in the codebase goes
        through a `BaseUI`-typed receiver (`ui/base/model_commands.py`), which
        adds its own setter; a UI that merely reports the state does not need
        one.
        """

    @property
    @abstractmethod
    def multi_ui_parent(self) -> Any:
        """The `MultiUI` this UI is a child of, or None when standalone."""

    @multi_ui_parent.setter
    @abstractmethod
    def multi_ui_parent(self, parent: Any) -> None: ...

    @property
    @abstractmethod
    def tool_call_handler(self) -> Any:
        """This UI's tool-call confirmation handler, or None when it has none."""

    @property
    @abstractmethod
    def background_tasks(self) -> "set[asyncio.Task]":
        """Tasks this UI keeps referenced so they are not garbage collected.

        Callers mutate the returned set directly (`.add`, `.discard`), so an
        implementation must hand back the same set each time, not a copy.
        """

    @abstractmethod
    def invalidate_ui(self) -> None:
        """Ask this UI to repaint. A no-op for UIs with no live surface."""

    @abstractmethod
    def cancel_pending_confirmations(self, flush: bool = True) -> None:
        """Release any `ask_user` call blocked on a tool confirmation.

        A no-op for UIs that never hold one. `flush=False` from the Ctrl+C /
        exit path, where writing buffered tokens is wasted work.
        """

    @abstractmethod
    def flush_to_parent(self) -> None:
        """Write anything buffered here out to the delegating parent UI.

        A no-op for UIs that stream directly rather than buffering.
        """
