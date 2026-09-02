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


class AnyUI(Protocol):
    """The UI contract every task's `ui` slot is typed against.

    A `Protocol`, not an ABC: a UI is structural (six duck-typed methods),
    and nothing should have to inherit from this class to count as one —
    `StdUI`, `BaseUI` and every custom UI in `docs/advanced-topics/
    llm-custom-ui.md` satisfy it by shape alone. Do not "fix" this into an
    ABC for consistency with the other `Any*` types; most of those are
    genuine base classes, this one is deliberately not.
    """

    async def ask_user(
        self,
        prompt: str,
        output_to_parent: str = "",
        agent_id: str | None = None,
    ) -> str:
        """Ask the user a free-text question and return their answer."""
        ...

    async def ask_user_choice(
        self, spec: ChoiceSpec, agent_id: str | None = None
    ) -> str:
        """Ask the user a multiple-choice question and return their pick."""
        ...

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
        ...

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
        ...

    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
        """Run an interactive shell command, handing it the real terminal."""
        ...

    async def run_async(self) -> Any:
        """Drive this UI's own event loop until the session ends."""
        ...
