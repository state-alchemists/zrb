from __future__ import annotations

import asyncio
from abc import abstractmethod
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.input_source import InputProvenance
from zrb.llm.ui.queue_based_input import QueueBasedInput
from zrb.llm.ui.simple_ui_base import SimpleUI
from zrb.llm.ui.ui_config import UIConfig

if TYPE_CHECKING:
    from zrb.llm.agent.types import UserContent
    from zrb.llm.task.llm_task import LLMTask


class EventDrivenUI(SimpleUI):
    """UI for event-driven backends (Telegram, Discord, WhatsApp).

    Implement `print(text, kind)` and `start_event_loop()`, and call
    `handle_incoming_message()` when messages arrive; `ask_user()` blocks on
    an internal queue until the user responds.

    Example:
        class TelegramUI(EventDrivenUI):
            async def print(self, text: str, kind: str) -> None:
                await self.bot.send_message(self.chat_id, text)

            async def start_event_loop(self):
                # Register handler that calls handle_incoming_message()
                self.bot.add_handler(MessageHandler(filters.TEXT, self._on_msg))

            async def _on_msg(self, update, context):
                self.handle_incoming_message(update.message.text)
    """

    def __init__(
        self,
        ctx,
        llm_task: LLMTask,
        history_manager: AnyHistoryManager,
        ui_config: UIConfig | None = None,
        initial_message: str = "",
        initial_attachments: "list[UserContent] | None" = None,
        model: str | None = None,
        **kwargs,
    ):
        super().__init__(
            ctx=ctx,
            llm_task=llm_task,
            history_manager=history_manager,
            ui_config=ui_config,
            initial_message=initial_message,
            initial_attachments=initial_attachments,
            model=model,
            **kwargs,
        )
        self._input_handling = QueueBasedInput(self)

    @property
    def input_queue(self) -> "asyncio.Queue[str]":
        return self._input_handling.input_queue

    @property
    def waiting_for_input(self) -> bool:
        return self._input_handling.waiting_for_input

    @waiting_for_input.setter
    def waiting_for_input(self, value: bool) -> None:
        self._input_handling.waiting_for_input = value

    async def get_input(self, prompt: str) -> str:
        return await self._input_handling.get_input(prompt)

    def handle_incoming_message(
        self, text: str, source: InputProvenance | None = None
    ) -> None:
        self._input_handling.handle_incoming_message(text, source)

    @property
    def is_waiting_for_answer(self) -> bool:
        return self.waiting_for_input

    @property
    def pending_answer_since(self) -> float | None:
        return self._input_handling.waiting_since

    def is_prompt_answered_since(self, asked_at: float) -> bool:
        return self._input_handling.is_answered_since(asked_at)

    def submit_answer(self, text: str) -> None:
        self.handle_incoming_message(text)

    @abstractmethod
    async def start_event_loop(self):
        """Register handlers with your backend; each calls
        `handle_incoming_message(text)`."""
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement start_event_loop()"
        )

    async def _run_loop(self):
        """Start the event loop and wait."""
        await self.start_event_loop()
        while True:
            await asyncio.sleep(CFG.LLM_UI_STATUS_INTERVAL / 1000)
