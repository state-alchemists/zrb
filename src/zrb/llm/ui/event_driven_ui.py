import asyncio
from abc import abstractmethod
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.task.llm_task import LLMTask
from zrb.llm.ui.ui_config import UIConfig
from zrb.llm.ui.simple_ui_base import SimpleUI

if TYPE_CHECKING:
    from pydantic_ai import UserContent


class EventDrivenUI(SimpleUI):
    """UI for event-driven backends (Telegram, Discord, WhatsApp).

    This class handles the queue + waiting pattern that's common in
    event-driven systems:
    - Messages arrive via handlers/callbacks
    - ask_user() blocks on an internal queue until user responds

    You need to implement:
    - print(text: str, kind: str) -> None   # Send to user
    - start_event_loop()                    # Start listening for events

    And call handle_incoming_message() when messages arrive.

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
        config: UIConfig | None = None,
        initial_message: str = "",
        initial_attachments: "list[UserContent] | None" = None,
        model: str | None = None,
        **kwargs,
    ):
        super().__init__(
            ctx=ctx,
            llm_task=llm_task,
            history_manager=history_manager,
            config=config,
            initial_message=initial_message,
            initial_attachments=initial_attachments,
            model=model,
            **kwargs,
        )
        self._input_queue: asyncio.Queue[str] = asyncio.Queue()
        self._waiting_for_input = False

    @property
    def input_queue(self) -> asyncio.Queue[str]:
        """Public accessor for input queue (backward compatibility).

        Prefer using handle_incoming_message() for routing messages.
        """
        return self._input_queue

    @abstractmethod
    async def start_event_loop(self):
        """Start the event loop for this UI.

        Override this to register handlers with your backend:
        - Telegram: Add message handler
        - Discord: Register on_message callback
        - WhatsApp: Set up webhook handler

        When a message arrives, call handle_incoming_message(text).
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement start_event_loop()"
        )

    def handle_incoming_message(self, text: str):
        """Call this when a message arrives from your backend.

        Routes the message to the appropriate handler:
        - If waiting for input (ask_user blocked), it goes to the queue
        - Otherwise, it's submitted as a new user message to the LLM
        """
        if self._waiting_for_input:
            self._input_queue.put_nowait(text)
        else:
            self._submit_user_message(self._llm_task, text)

    async def get_input(self, prompt: str) -> str:
        """Blocks until handle_incoming_message() receives a response."""
        if prompt:
            await self.print(f"❓ {prompt}", kind="text")
        self._waiting_for_input = True
        try:
            return await self._input_queue.get()
        finally:
            self._waiting_for_input = False

    async def _run_loop(self):
        """Start the event loop and wait."""
        await self.start_event_loop()
        while True:
            await asyncio.sleep(CFG.LLM_UI_STATUS_INTERVAL / 1000)
