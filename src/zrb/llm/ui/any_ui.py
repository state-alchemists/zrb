"""The UI contract every task's `ui` slot is typed against.

`AnyUI` is one object made of five roles, each its own contract so a backend can
replace one without touching the rest:

- `AnyUIDisplay` — what the UI writes: output, answers, block markers.
- `AnyUIInput` — questions to the user and the queue a typed message enters.
- `AnyUIPicker` — the structured choice widget.
- `AnyUITools` — a tool call's lifecycle and its approval state.
- `AnyUISession` — which conversation is open, which model answers, its meters.

Every role is reached through an accessor — `ui.display`, `ui.input`,
`ui.picker`, `ui.session`, `ui.tools` — because a backend swaps the writer, the
widget and the queue, and the session is the conversation the object already
*is*: a UI that tracks its own model, history and turn state answers for the
role without a second object holding a copy of that state.

This module adds only what belongs to the whole: the shared writer
`append_to_output`, `run_async`, `is_local`, and the `MultiUI` parent link. A UI
keeps the roles it renders and mixes in the matching defaults from
`zrb.llm.ui.fallback` for the ones it does not.

`AnyUI` is still one `ABC`: each of its own members fails with `TypeError` at
construction when a backend leaves it out, and the five accessors are among
them, so a class implementing `AnyUI` directly must supply all five.
`UIStateDefaultsMixin` supplies each accessor (handing the object back) plus an
inert default for every member a UI leaves out. What an accessor *hands back* is
not checked at construction — a UI missing one of those members answers at the
first read, which is the gap the mixin exists to close.
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


class AnyUI(ABC):
    """The whole object: its own members, and one accessor per role.

    The aggregate promises nine members — the writer, the loop, the locality
    flag, the parent link, and the five accessors — so a caller that needs a
    role asks that role for it, and a reader is not handed fifty methods to
    sift for the one they want.
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
    def input(self) -> AnyUIInput:
        """Questions to the user, and the queue a typed message enters."""

    @property
    @abstractmethod
    def picker(self) -> AnyUIPicker:
        """This UI's choice widget."""

    @property
    @abstractmethod
    def session(self) -> AnyUISession:
        """The conversation this UI is talking to: model, turn state, meters."""

    @property
    @abstractmethod
    def tools(self) -> AnyUITools:
        """A tool call's lifecycle, and the state of its approval."""

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
