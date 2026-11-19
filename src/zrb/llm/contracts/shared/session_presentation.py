"""The interactive session runner, at L0.

A chat session is driven two ways. One-shot (`run_non_interactive_session` in
`task/chat/running.py`) needs no UI at all — it reads the UIs already attached
and runs the inner task once. Interactive builds a UI from the task's own
values, replays the stored conversation onto it, runs its loop and reads its
display back: that is presentation work, so it lives in
`zrb.llm.presentation.ui.session`, and the task asks this module for it instead of
importing `ui/`.

`builtin/llm/chat.py` — the command that offers an interactive chat — is what
registers the runner. A task asked to run interactively with nothing
registered has no way to present itself, and says so rather than going quiet.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import TypeAlias

    #: Takes the chat task, then the session's own arguments as keywords.
    InteractiveRunner: TypeAlias = Callable[..., Awaitable[object]]

_runner: "InteractiveRunner | None" = None


def register_interactive_runner(runner: "InteractiveRunner") -> None:
    """Make *runner* what an interactive session is driven by from now on."""
    global _runner
    _runner = runner


def get_interactive_runner() -> "InteractiveRunner | None":
    """The registered runner, or ``None`` when nothing registered one."""
    return _runner


def clear_interactive_runner() -> None:
    """Forget the registered runner, so a later ask finds none."""
    global _runner
    _runner = None
