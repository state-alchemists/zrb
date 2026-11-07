"""What the turn is doing, and how it stops.

The children run no turn of their own: this wrapper runs the one turn they all
watch, so "is a turn running", the cancel, and the queued-message delivery all
answer here rather than in a child.
"""

import asyncio

from zrb.llm.hook.types import HookEvent
from zrb.llm.ui.base.message_queue import QueuedMessage
from zrb.llm.ui.base.queue_delivery import (
    DeliveryReport,
    send_queued_messages_now,
)
from zrb.llm.ui.turn_hooks import get_turn_hook_manager

from zrb.llm.ui.multi.fanout import MultiUIFanout


class MultiUITurnControl(MultiUIFanout):
    """Answer for the turn, and stop it once for every child."""

    @property
    def is_turn_running(self) -> bool:
        """Whether this MultiUI is running a turn (its children run none)."""
        running = self._running_llm_task
        return running is not None and not running.done()

    def cancel_current_turn(self, reason: str) -> None:
        """Release children's confirmations, cancel this MultiUI's turn and
        fire `Stop` with *reason* once."""
        self.cancel_pending_confirmations()
        running = self._running_llm_task
        if running is None or running.done():
            return
        running.cancel()
        main_ui = self.main_ui
        stop = get_turn_hook_manager(self._llm_task).execute_hooks(
            HookEvent.STOP,
            {
                "reason": reason,
                "session": main_ui.conversation_session_name if main_ui else "",
            },
        )
        task = asyncio.get_running_loop().create_task(stop)
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

    def send_queued_messages_now(
        self,
        may_interrupt: bool = True,
        only_ready: bool = False,
        immediate_entry: QueuedMessage | None = None,
        move_shell: bool | None = None,
    ) -> DeliveryReport:
        """Deliver the queued messages into the running turn, now.

        The children share one queue and this wrapper runs the turn, so the
        delivery happens here rather than in a child.
        """
        report = send_queued_messages_now(
            active_run_context=self.active_run_context,
            queue=self._message_queue,
            is_turn_running=self.is_turn_running,
            is_waiting_for_answer=self.is_waiting_for_answer,
            cancel_turn=lambda: self.cancel_current_turn("send_now"),
            may_interrupt=may_interrupt,
            only_ready=only_ready,
            immediate_entry=immediate_entry,
            cut_signal=self.shell_cut_signal,
            move_shell=move_shell,
        )
        main_ui = self.main_ui
        if main_ui is not None:
            main_ui.redraw_echoes(report.delivered_entries)
        return report

    def deliver_queued_messages_early(self) -> DeliveryReport:
        """Hand the ready queued messages to the running turn at a checkpoint.

        Same rule as `BaseUI.deliver_queued_messages_early`: only the entries
        the queue calls ready, and no interruption.
        """
        return self.send_queued_messages_now(may_interrupt=False, only_ready=True)

    def is_prompt_answered_since(self, asked_at: float) -> bool:
        """Whether any child has answered the first prompt asked at or after
        *asked_at*: an answer from any of them settles it."""
        return any(ui.input.is_prompt_answered_since(asked_at) for ui in self._uis)
