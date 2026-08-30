from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.ui.queue_based_input import QueueBasedInput
from zrb.llm.ui.simple_ui_base import SimpleUI
from zrb.llm.ui.ui_config import UIConfig

if TYPE_CHECKING:
    from zrb.llm.agent.types import UserContent
    from zrb.llm.task.llm_task import LLMTask


class PollingUI(SimpleUI):
    """UI for polling-based backends (HTTP API, WebSocket).

    This class provides output/input queues that external systems can use:
    - output_queue: Messages from AI (external system polls this)
    - handle_incoming_message(): Routes messages correctly based on LLM state

    Call handle_incoming_message() when user sends a new message:
    - If LLM is waiting for input (e.g., asking a question): answers it
    - If LLM is idle: starts new conversation turn

    You need to implement nothing — print(text, kind) is already implemented
    by PollingUI to queue all output. Override if you want kind-aware behaviour.

    Example:
        class HttpAPIUI(PollingUI):
            async def print(self, text: str, kind: str = "text") -> None:
                self.output_queue.put_nowait(text)

        # External system uses:
        ui.output_queue.get()  # Poll for AI messages
        ui.handle_incoming_message("user response")  # Provide input or start new
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
        self.output_queue: asyncio.Queue[str] = asyncio.Queue()
        self._input_handling = QueueBasedInput(self)

    async def print(self, text: str, kind: str = "text") -> None:
        """Queue output for external polling.

        Note: This is async for consistency with the base class, but
        internally just puts to a queue (non-blocking).
        """
        self.output_queue.put_nowait(text)

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

    def handle_incoming_message(self, text: str) -> None:
        self._input_handling.handle_incoming_message(text)
