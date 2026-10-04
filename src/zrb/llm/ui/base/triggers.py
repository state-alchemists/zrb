"""Running a chat UI's external triggers.

A trigger is a callable returning an async iterable; each item it yields
becomes a user turn on the owning UI. The item vocabulary — a plain string,
a `TriggerMessage` carrying attachments, or a `TriggerReply` answering a
pending prompt — lives in `zrb.llm.ui.trigger`.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import AsyncIterable, Callable, Iterable
from typing import TYPE_CHECKING, Any

from zrb.llm.input_source import InputProvenance
from zrb.llm.ui.trigger import TriggerInput, TriggerMessage, TriggerReply
from zrb.util.cli.style import stylize_error
from zrb.util.exception import exception_summary

logger = logging.getLogger(__name__)

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
        async_iter: Any = None
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
                    self._deliver(item)
                except Exception as deliver_error:
                    # Report and keep going: a trigger is a long-lived source
                    # (a button, a queue, a microphone), so one bad item or
                    # one failed submission must not stop every later one.
                    owner.append_to_output(
                        stylize_error(
                            f"\n[Trigger Error: {exception_summary(deliver_error)}]\n"
                        )
                    )
        except asyncio.CancelledError:
            # A trigger runs as a background task; swallowing this would make
            # a cancelled loop look like one that finished.
            raise
        except Exception as e:
            owner.append_to_output(
                stylize_error(f"\n[Trigger Error: {exception_summary(e)}]\n")
            )
        finally:
            aclose: Any = getattr(async_iter, "aclose", None)
            if callable(aclose):
                try:
                    result = aclose()
                    if inspect.isawaitable(result):
                        await result
                except Exception as close_error:
                    logger.debug(f"Trigger iterator close failed: {close_error}")

    def _deliver(self, item: Any) -> None:
        if isinstance(item, TriggerReply):
            self._reply(item)
            return
        owner = self._owner
        text, attachments, source = self._split(item)
        if not text and not attachments:
            return
        # Drained by the `submit_user_message` below (a `MultiUI` parent
        # collects from its children) -- no await between, so this slice
        # still holds exactly what this item staged. The drain happens after
        # the submission's echo, so a submission that raises before it would
        # otherwise leave these staged for whatever turn comes next.
        owner.pending_attachments.extend(attachments)
        try:
            if source is None:
                owner.submit_user_message(owner.llm_task, text)
            else:
                owner.submit_user_message(owner.llm_task, text, source)
        except BaseException:
            _unstage(owner.pending_attachments, attachments)
            raise

    def _reply(self, reply: TriggerReply) -> None:
        owner = self._owner
        if owner.is_waiting_for_answer and self._is_said_to_pending(reply):
            if owner.is_waiting_for_choice:
                answer = reply.text
            else:
                answer = reply.approval or reply.text
            # An empty answer approves a tool call, so it is never sent.
            if answer.strip():
                owner.submit_answer(answer)
            return
        if reply.text.strip():
            if reply.source is None:
                owner.submit_user_message(owner.llm_task, reply.text)
            else:
                owner.submit_user_message(owner.llm_task, reply.text, reply.source)

    def _is_said_to_pending(self, reply: TriggerReply) -> bool:
        if reply.started_at is None:
            return True
        since = self._owner.pending_answer_since
        # A UI that cannot say when its prompt appeared gets no timed answers.
        return since is not None and since <= reply.started_at

    def _split(
        self, item: Any
    ) -> "tuple[str, list[UserContent], InputProvenance | None]":
        """Split a yielded item into text, attachments and provenance."""
        if isinstance(item, TriggerInput):
            return str(item.text or ""), list(item.attachments), item.source
        if isinstance(item, TriggerMessage):
            return str(item.text or ""), list(item.attachments), None
        if not isinstance(item, tuple):
            return str(item or ""), [], None
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
        return str(text or ""), list(attachments), None


def _unstage(staged: "list[UserContent]", items: "list[UserContent]") -> None:
    """Remove exactly *items* from *staged*, by identity, last occurrence first.

    Deleting the tail slice instead would assume nothing else touched the list
    between staging and the failure. Nothing does today — `submit_user_message`
    is synchronous and there is no await in between — but the list is shared
    with `/attach`, `/photo` and every other trigger loop, so the assumption is
    not the loop's to make.
    """
    for item in reversed(items):
        for index in range(len(staged) - 1, -1, -1):
            if staged[index] is item:
                del staged[index]
                break
