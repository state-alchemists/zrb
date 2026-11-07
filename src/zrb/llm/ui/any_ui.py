"""The UI contract every task's `ui` slot is typed against.

`AnyUI` is one object made of five roles, each its own contract so a backend can
replace one without touching the rest:

- `AnyUIDisplay` — what the UI writes: output, answers, block markers.
- `AnyUIInput` — questions to the user and the queue a typed message enters.
- `AnyUIPicker` — the structured choice widget.
- `AnyUITools` — a tool call's lifecycle and its approval state.
- `AnyUISession` — which conversation is open, which model answers, its meters.

The input and tools roles are inherited. Display, picker and session are reached
through an accessor — `ui.display`, `ui.picker` and `ui.session` — because a
backend swaps the writer and the widget, and the session is the conversation the
object already *is*: a UI that tracks its own model, history and turn state
answers for the role without a second object holding a copy of that state.

This module adds only what belongs to the whole: `run_async`, `is_local`, and
the `MultiUI` parent link. A UI keeps the roles it renders and mixes in the
matching defaults from `zrb.llm.ui.fallback` for the ones it does not.

`AnyUI` is still one `ABC`: a member it declares itself, or one of the two roles
it inherits, fails with `TypeError` at construction when a backend leaves it out.
The three accessor roles are abstract too, so a class implementing `AnyUI`
directly must supply `display`, `picker` and `session`; `UIStateDefaultsMixin`
supplies all three (each handing the object back) plus an inert default for every
member a UI leaves out. What an accessor *hands back* is not checked at
construction — a UI missing one of those members answers at the first read, which
is the gap the mixin exists to close.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TextIO

from zrb.llm.ui.any_ui_display import AnyUIDisplay
from zrb.llm.ui.any_ui_input import AnyUIInput
from zrb.llm.ui.any_ui_picker import AnyUIPicker, ChoiceOption, ChoiceSpec
from zrb.llm.ui.any_ui_session import AnyUISession
from zrb.llm.ui.any_ui_tools import AnyUITools

__all__ = [
    "AnyUI",
    "AnyUIDisplay",
    "AnyUIInput",
    "AnyUIPicker",
    "AnyUISession",
    "AnyUITools",
    "ChoiceOption",
    "ChoiceSpec",
]


class AnyUI(AnyUIInput, AnyUITools, ABC):
    """Two roles in one object, plus what belongs to the whole.

    Display, picker and session are the exceptions: what a UI writes, the widget
    it asks a choice through, and the conversation it is talking to are reached
    as `display`, `picker` and `session`, so a caller that needs one of them asks
    for that one and a backend can replace either of the first two without
    answering to the rest of the aggregate.
    """

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
        """Write output the way `print()` would, kept for later replay.

        The one member the display role and the whole object share: it is what
        a backend overrides, and what `display` writes through.
        """

    @property
    @abstractmethod
    def display(self) -> AnyUIDisplay:
        """What this UI writes: output, answers, block markers, echo spans."""

    @property
    @abstractmethod
    def picker(self) -> AnyUIPicker:
        """This UI's choice widget."""

    @property
    @abstractmethod
    def session(self) -> AnyUISession:
        """The conversation this UI is talking to: model, turn state, meters."""

    @abstractmethod
    async def run_async(self) -> Any:
        """Drive this UI's own event loop until the session ends."""

    @property
    def is_local(self) -> bool:
        """Whether the user driving this UI sits at the machine zrb runs on.

        The default is True: a UI is local until it says otherwise. A UI
        driven over a network (the web chat, Telegram) returns False, so a
        command that acts on local hardware — the screen, the camera — can
        refuse instead of capturing a machine the user cannot see.
        """
        return True

    @property
    @abstractmethod
    def multi_ui_parent(self) -> Any:
        """The `MultiUI` this UI is a child of, or None when standalone."""

    @multi_ui_parent.setter
    @abstractmethod
    def multi_ui_parent(self, parent: Any) -> None: ...
