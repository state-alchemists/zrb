from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from zrb.llm.app.simple.simple_ui import SimpleUI

if TYPE_CHECKING:
    from pydantic_ai import UserContent

    from zrb.context.any_context import AnyContext
    from zrb.llm.app.simple.config import UIConfig
    from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
    from zrb.llm.task.llm_task import LLMTask


class PollingUI(SimpleUI):
    def __init__(
        self,
        ctx: "AnyContext",
        llm_task: "LLMTask",
        history_manager: "AnyHistoryManager",
        config: "UIConfig" | None = None,
        initial_message: str = "",
        initial_attachments: list["UserContent"] | None = None,
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
        self._input_queue: asyncio.Queue[str] = asyncio.Queue()
        self._waiting_for_input = False

    @property
    def input_queue(self) -> asyncio.Queue[str]:
        return self._input_queue

    async def print(self, text: str) -> None:
        self.output_queue.put_nowait(text)

    async def get_input(self, prompt: str) -> str:
        if prompt:
            await self.print(f"❓ {prompt}")
        self._waiting_for_input = True
        try:
            return await self._input_queue.get()
        finally:
            self._waiting_for_input = False

    def handle_incoming_message(self, text: str):
        if self._waiting_for_input:
            self._input_queue.put_nowait(text)
        else:
            self._submit_user_message(self._llm_task, text)
