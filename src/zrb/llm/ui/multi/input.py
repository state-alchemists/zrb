"""Input: the shared queue, the raced prompts, and the choice widget.

Every child submits through this wrapper, so the queue, the "who won" record
and the shutdown check live here. A prompt goes to every child at once and the
first answer wins; a failed child drops out rather than winning, because an
empty answer reads as approval.
"""

import asyncio
import logging
import sys
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.llm.shared.input_source import (
    BACKGROUND_INPUT,
    KEYBOARD_INPUT,
    InputProvenance,
)
from zrb.llm.ui.any_ui_picker import AnyUIPicker
from zrb.llm.ui.base.message_queue import (
    QueuedMessage,
    raise_if_cancelling,
    settle_previous_job,
    submit_user_message_via_queue,
)
from zrb.llm.ui.base.queue_delivery import DeliveryReport

from zrb.llm.ui.multi.streaming import MultiUIStreaming
from zrb.llm.ui.multi.turn import MultiUITurnControl

if TYPE_CHECKING:
    from zrb.llm.ui.any_ui import ChoiceSpec

logger = logging.getLogger(__name__)


class MultiUIPicker(AnyUIPicker):
    """Ask every child UI's picker and take the first answer."""

    def __init__(self, host: "MultiUIInput") -> None:
        self._host = host

    async def ask_user_choice(
        self, spec: "ChoiceSpec", agent_id: str | None = None
    ) -> str:
        """Race the children, with the same rules as `ask_user`."""
        return await self._host.race_children(
            lambda ui: ui.picker.ask_user_choice(spec, agent_id=agent_id),
            "ask_user_choice",
        )


def is_shutdown_requested() -> bool:
    """Whether the process is going down, and no prompt should be waited on."""
    return getattr(sys, "zrb_shutdown_requested", False)


class MultiUIInput(MultiUIStreaming, MultiUITurnControl):
    """Queue what a child submits, and race what a child asks."""

    def submit_user_message(
        self,
        llm_task: Any,
        user_message: str,
        source: InputProvenance | None = KEYBOARD_INPUT,
    ):
        """Broadcast a child's user input to every UI and queue the turn.

        Attachments and echoes fan out to every child. The message is recorded
        once, on the primary child, since all children share one history file.
        """
        main_ui = self.main_ui
        # A background notice is not something the user typed: no recall for it.
        if main_ui is not None and source != BACKGROUND_INPUT:
            main_ui.input.record_submitted_message(user_message)
        submit_user_message_via_queue(
            append_to_output=self.append_to_output,
            stream_ai_response=self.stream_ai_response,
            queue=self._message_queue,
            attachment_sources=self._uis,
            echo_targets=self._uis,
            llm_task=llm_task,
            user_message=user_message,
            marker="💬",
            append_markdown=self.append_markdown,
            source=source,
        )

    def submit_message(
        self,
        user_message: str,
        source: InputProvenance | None = KEYBOARD_INPUT,
    ) -> None:
        """Queue *user_message* for the shared agent turn (Ctrl+G sends sooner).

        `KEYBOARD_INPUT` by default because this is the keystroke path; a
        caller submitting words that are not the user's own passes `None`.
        """
        self.submit_user_message(self._llm_task, user_message, source)

    @property
    def is_waiting_for_answer(self) -> bool:
        """Whether any child holds a prompt waiting for the user."""
        return any(ui.input.is_waiting_for_answer for ui in self._uis)

    @property
    def pending_answer_since(self) -> "float | None":
        """The earliest moment any child's pending prompt has been waiting
        since, as a `time.monotonic()` value; ``None`` when none is pending or
        no child dates its own.

        The earliest, not the main child's: a prompt every child shows is one
        prompt, and it appeared when the first of them put it up.
        """
        since = [getattr(ui.input, "pending_answer_since", None) for ui in self._uis]
        dated = [value for value in since if value is not None]
        return min(dated) if dated else None

    def submit_answer(self, text: str) -> None:
        """Answer the pending prompt with *text*; with none pending, queue it as
        a message.

        A prompt raised through the composite is raised on every child at once
        and the first answer wins, so the words go to a child that is actually
        waiting. Queueing them instead would leave the approval blocked, then
        treat a spoken "yes" as an ordinary message once the turn moved on.
        """
        waiting = next((ui for ui in self._uis if ui.input.is_waiting_for_answer), None)
        if waiting is None:
            self.submit_message(text)
            return
        waiting.input.submit_answer(text)

    def is_prompt_answered_since(self, asked_at: float) -> bool:
        """Whether any child has answered the first prompt asked at or after
        *asked_at*: an answer from any of them settles it."""
        return any(ui.input.is_prompt_answered_since(asked_at) for ui in self._uis)

    def withdraw_message(
        self, user_message: str, source: InputProvenance | None
    ) -> None:
        """Drop the queued message `submit_message` was given, if it is still
        waiting; each child takes its echo of it out of its own output."""
        entry = self._message_queue.find_pending(user_message, source)
        if entry is None:
            return
        self._message_queue.remove(entry)
        for child in self._uis:
            child.display.remove_echo(entry)

    def submit_message_now(
        self,
        user_message: str,
        source: InputProvenance | None = None,
        may_interrupt: bool = True,
        move_shell: bool | None = None,
    ) -> DeliveryReport:
        """Send this message promptly without flushing other queued drafts."""
        self.submit_message(user_message, source)
        return self.send_queued_messages_now(
            may_interrupt=may_interrupt,
            only_ready=True,
            immediate_entry=self._message_queue.peek_latest(),
            move_shell=move_shell,
        )

    async def process_messages_loop(self):
        """Process jobs from shared queue sequentially."""
        while True:
            try:
                entry = await self._message_queue.get()
                try:
                    await settle_previous_job(self._running_llm_task)
                    await self._run_job(entry)
                finally:
                    # Also when quitting ends the loop mid-job.
                    self._message_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in message queue: {e}")
                await asyncio.sleep(CFG.LLM_UI_STATUS_INTERVAL / 1000)

    async def _run_job(self, entry: "QueuedMessage") -> None:
        """Run one queued job, and raise `CancelledError` when the loop was
        cancelled meanwhile (quitting), even if the job absorbed the cancel."""
        task = asyncio.create_task(entry.run())
        self._running_llm_task = task
        try:
            await task
        except asyncio.CancelledError:
            # A cancel aimed at the job alone keeps the loop going.
            pass
        finally:
            self._running_llm_task = None
        raise_if_cancelling()

    async def ask_user(
        self,
        prompt: str,
        output_to_parent: str = "",
        agent_id: str | None = None,
    ) -> str:
        """Race all UIs for input and return the first response.

        The losers' prompts are cancelled once one UI answers.
        """
        return await self.race_children(
            lambda ui: ui.input.ask_user(
                prompt, output_to_parent=output_to_parent, agent_id=agent_id
            ),
            "ask_user",
        )

    @property
    def picker(self) -> AnyUIPicker:
        """Ask a choice across every child UI, taking the first answer."""
        return MultiUIPicker(self)

    async def race_children(
        self, ask: Callable[[Any], Coroutine[Any, Any, str]], label: str
    ) -> str:
        """Return the first answer any child gives.

        A failed child drops out rather than winning: an empty answer approves
        a tool call. With no child left to answer this raises, as
        `MultiplexApprovalChannel` denies.
        """
        if is_shutdown_requested():
            raise RuntimeError(f"Shutdown requested; {label} has no answer")
        loop = asyncio.get_running_loop()
        pending_tasks: dict[asyncio.Task, tuple[int, Any]] = {}
        for i, ui in enumerate(self._uis):
            try:
                pending_tasks[loop.create_task(ask(ui))] = (i, ui)
            except Exception as e:
                CFG.LOGGER.debug(f"Child UI {label} setup failed: {e}")
        if not pending_tasks:
            raise RuntimeError(f"No child UI could take {label}")
        # Shared by concurrent races; each removes only its own tasks.
        self._pending_input_tasks.extend(pending_tasks)
        waiting: set[asyncio.Task] = set(pending_tasks)
        last_error: BaseException | None = None
        try:
            while waiting:
                done, waiting = await asyncio.wait(
                    waiting, return_when=asyncio.FIRST_COMPLETED
                )
                # Several UIs may finish in the same wait round; the lowest
                # index wins so the result never depends on set iteration order.
                for task in sorted(done, key=lambda t: pending_tasks[t][0]):
                    if task.cancelled():
                        continue
                    error = task.exception()
                    if error is not None:
                        CFG.LOGGER.debug(f"Child UI {label} failed: {error}")
                        last_error = error
                        continue
                    self._last_winning_ui = pending_tasks[task][1]
                    return task.result()
            raise RuntimeError(f"Every child UI failed {label}") from last_error
        finally:
            # Cancelling a loser releases that loser's prompt and no other.
            for task in pending_tasks:
                task.cancel()
            await asyncio.gather(*pending_tasks, return_exceptions=True)
            for task in pending_tasks:
                if task in self._pending_input_tasks:
                    self._pending_input_tasks.remove(task)
