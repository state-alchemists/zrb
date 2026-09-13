"""Running a chat UI's external triggers.

A trigger is a callable returning an async iterable; each item it yields
becomes a user turn on the owning UI. The item vocabulary — a plain string, or
a `TriggerMessage` carrying attachments — lives in `zrb.llm.ui.trigger`.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import AsyncIterable, Callable
from typing import TYPE_CHECKING, Any

from zrb.util.cli.style import stylize_error

if TYPE_CHECKING:
    from zrb.llm.agent.types import UserContent
    from zrb.llm.ui.base.ui import BaseUI


class BaseUITriggers:
    """Drives the owner UI's trigger loops."""

    def __init__(self, owner: "BaseUI"):
        self._owner = owner

    async def trigger_loop(
        self, trigger_factory: Callable[[], AsyncIterable[Any]]
    ) -> None:
        """Submit a user turn for every item *trigger_factory* yields."""
        owner = self._owner
        try:
            iterator = trigger_factory()
            if inspect.isawaitable(iterator):
                iterator = await iterator
            if not hasattr(iterator, "__aiter__"):
                owner.append_to_output(
                    stylize_error(
                        "\n[Trigger Error: Trigger factory returned non-async "
                        f"iterator: {type(iterator)}]\n"
                    )
                )
                return
            async_iter = iterator.__aiter__()
            while True:
                try:
                    item = await async_iter.__anext__()
                except StopAsyncIteration:
                    break
                text, attachments = self._split(item)
                if not text and not attachments:
                    continue
                # Drained by the `submit_user_message` below (a `MultiUI`
                # parent collects from its children) -- no await between, so
                # this slice still holds exactly what this item staged. The
                # drain happens after the submission's echo, so a submission
                # that raises before it would otherwise leave these staged for
                # whatever turn comes next.
                staged_from = len(owner.pending_attachments)
                owner.pending_attachments.extend(attachments)
                try:
                    owner.submit_user_message(owner.llm_task, text)
                except BaseException:
                    del owner.pending_attachments[staged_from:]
                    raise
        except asyncio.CancelledError:
            pass
        except Exception as e:
            owner.append_to_output(stylize_error(f"\n[Trigger Error: {e}]\n"))

    def _split(self, item: Any) -> "tuple[str, list[UserContent]]":
        """Split a yielded item into its text and its attachments."""
        if isinstance(item, tuple):
            # `TriggerMessage`, or any bare (text, attachments) tuple.
            text, *rest = item
            return str(text or ""), list(rest[0]) if rest else []
        return str(item or ""), []
