"""Running a chat UI's external triggers.

A trigger is a callable returning an async iterable; each item it yields
becomes a user turn on the owning UI. The item vocabulary — a plain string, or
a `TriggerMessage` carrying attachments — lives in `zrb.llm.ui.trigger`.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import AsyncIterable, Callable, Iterable
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
                try:
                    text, attachments = self._split(item)
                except ValueError as split_error:
                    # Report and keep going: a trigger is a long-lived source
                    # (a button, a queue), so one malformed item must not stop
                    # every later one from being delivered.
                    owner.append_to_output(
                        stylize_error(f"\n[Trigger Error: {split_error}]\n")
                    )
                    continue
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
        """Split a yielded item into its text and its attachments.

        A tuple must be the `(text, attachments)` shape `TriggerMessage`
        declares. Anything else raises `ValueError` rather than being
        reinterpreted: a 3-tuple used to lose its third element silently, a
        bare string in the attachments slot became a list of its characters,
        and `None` there raised `TypeError` from inside `list()`.
        """
        if not isinstance(item, tuple):
            return str(item or ""), []
        if len(item) != 2:
            raise ValueError(
                "a trigger tuple must be (text, attachments); "
                f"got {len(item)} element(s): {item!r}"
            )
        text, attachments = item
        if attachments is None:
            attachments = ()
        if isinstance(attachments, (str, bytes)) or not isinstance(
            attachments, Iterable
        ):
            raise ValueError(
                "a trigger item's attachments must be a sequence, not "
                f"{type(attachments).__name__}: {attachments!r}. Wrap a single "
                "attachment in a list."
            )
        return str(text or ""), list(attachments)
