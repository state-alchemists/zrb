import asyncio
from typing import TYPE_CHECKING

from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.task.llm_task import LLMTask
from zrb.llm.ui.ui_config import UIConfig
from zrb.llm.ui.simple_ui_base import SimpleUI

if TYPE_CHECKING:
    from pydantic_ai import UserContent


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
        self._input_queue: asyncio.Queue[str] = asyncio.Queue()
        self._waiting_for_input = False

    @property
    def input_queue(self) -> asyncio.Queue[str]:
        """Public accessor for input queue (backward compatibility).

        Prefer using handle_incoming_message() for routing messages.
        """
        return self._input_queue

    async def print(self, text: str, kind: str = "text") -> None:
        """Queue output for external polling.

        Note: This is async for consistency with the base class, but
        internally just puts to a queue (non-blocking).
        """
        self.output_queue.put_nowait(text)

    async def get_input(self, prompt: str) -> str:
        """Block until external system provides input via handle_incoming_message()."""
        if prompt:
            await self.print(f"❓ {prompt}", kind="text")
        self._waiting_for_input = True
        try:
            return await self._input_queue.get()
        finally:
            self._waiting_for_input = False

    def handle_incoming_message(self, text: str):
        """Call this when a user message arrives.

        Routes the message correctly:
        - If LLM is waiting for input (get_input blocked): unblocks it
        - If LLM is idle: starts a new conversation turn

        This is the KEY method for external integration. Use it for:
        - HTTP API: POST /chat calls this
        - WebSocket: When a message event arrives
        """
        if self._waiting_for_input:
            # LLM is blocked on get_input() waiting for user response
            self._input_queue.put_nowait(text)
        else:
            # LLM is idle - start a new conversation turn
            self._submit_user_message(self._llm_task, text)
