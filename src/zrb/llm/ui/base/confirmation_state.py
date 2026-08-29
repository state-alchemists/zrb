"""Pending tool-call/ask-user confirmation state for `BaseUI`.

Self-contained like `BaseUIUsage`: the actual queueing/resolution logic lives
in `UIConfirmation` (`llm/ui/default/confirmation.py`), which reaches this
state only through `BaseUI`'s public properties (`current_confirmation`,
`confirmation_queue`, `confirmation_output_buffer`) — so this part, like that
one, needs no reference back to the owner. It exists to give the three fields
one name instead of three independent ones on `BaseUI` itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import asyncio


class BaseUIConfirmationState:
    """The pending-confirmation queue, its active entry, and the output
    buffer held while a confirmation is on screen."""

    def __init__(self) -> None:
        # Each queue entry is (future, prompt, spec, agent_id); spec is a
        # ChoiceSpec for AskUserQuestion-style requests, else None for plain
        # text; agent_id is the originating sub-agent's id, or None for the
        # main agent.
        self.queue: "list[tuple[asyncio.Future[str], str, Any, str | None]]" = []
        self.current: "asyncio.Future[str] | None" = None
        # Buffer for main-agent output during confirmation (avoids interleaving).
        self.output_buffer: list[str] = []
