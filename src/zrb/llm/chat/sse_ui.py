from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, TextIO

from zrb.llm.ui.simple_ui import PollingUI

if TYPE_CHECKING:
    from zrb.context.any_context import AnyContext
    from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
    from zrb.llm.task.llm_task import LLMTask

logger = logging.getLogger(__name__)


class ChatSSEUI(PollingUI):
    """SSE-based UI for web chat interface.

    This UI:
    - Broadcasts output directly via SSE
    - Routes incoming messages from HTTP API to the LLM
    - Integrates with ChatApproval for visual tool approval
    """

    def __init__(
        self,
        session_id: str,
        ctx: "AnyContext",
        llm_task: "LLMTask",
        history_manager: "AnyHistoryManager",
        config: "ChatUIConfig | None" = None,
        initial_message: str = "",
        initial_attachments: list[Any] | None = None,
        model: str | None = None,
        broadcast_fn=None,
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
        self._session_id = session_id
        self._sse_clients: dict[int, asyncio.Queue[str]] = {}
        self._client_counter = 0
        self._broadcast_fn = broadcast_fn
        self._is_streaming = False
        self._output_queue: asyncio.Queue[str] = asyncio.Queue()

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def is_streaming(self) -> bool:
        return self._is_streaming

    @is_streaming.setter
    def is_streaming(self, value: bool):
        self._is_streaming = value

    async def connect(self) -> int:
        """Register a new SSE client connection.

        Returns client ID.
        """
        client_id = self._client_counter
        self._client_counter += 1
        self._sse_clients[client_id] = asyncio.Queue()
        return client_id

    async def disconnect(self, client_id: int):
        """Unregister an SSE client."""
        self._sse_clients.pop(client_id, None)

    async def _broadcast(self, event_type: str, data: Any):
        """Send event to all connected SSE clients."""
        message = json.dumps({"type": event_type, "data": data}, ensure_ascii=False)
        print(
            f"[ChatSSEUI DEBUG] _broadcast called: type={event_type}, data={str(data)[:100]}..."
        )
        if self._broadcast_fn:
            print(f"[ChatSSEUI DEBUG] Calling _broadcast_fn")
            await self._broadcast_fn(message)
            print(f"[ChatSSEUI DEBUG] _broadcast_fn completed")
        for queue in self._sse_clients.values():
            await queue.put(message)

    async def _broadcast_text(self, text: str):
        """Send text output to all SSE clients."""
        await self._broadcast("message", text)

    async def _broadcast_approval(self, pending: dict):
        """Send approval request to all SSE clients."""
        await self._broadcast("approval", pending)

    async def _broadcast_approval_resolved(self, tool_call_id: str, action: str):
        """Send approval resolution to all SSE clients."""
        await self._broadcast(
            "approval_resolved",
            {
                "tool_call_id": tool_call_id,
                "action": action,
            },
        )

    async def _broadcast_status(self, status: dict):
        """Send status update to all SSE clients."""
        await self._broadcast("status", status)

    async def _broadcast_error(self, error: str):
        """Send error to all SSE clients."""
        await self._broadcast("error", error)

    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
    ):
        """Override to broadcast output via SSE.

        This is called synchronously during LLM execution. We queue the
        output and let the event loop process it.
        """
        text = sep.join(str(v) for v in values) + end
        print(f"[ChatSSEUI DEBUG] append_to_output called: {text[:100]}...")
        self._output_queue.put_nowait(text)
        print(
            f"[ChatSSEUI DEBUG] append_to_output queued, queue size now: {self._output_queue.qsize()}"
        )

    async def print(self, text: str) -> None:
        """Process queued output via SSE."""
        while not self._output_queue.empty():
            try:
                text = self._output_queue.get_nowait()
                if text.strip():
                    await self._broadcast_text(text)
            except asyncio.QueueEmpty:
                break

    async def _run_loop(self):
        """Process queued output and handle SSE client connections."""
        print(f"[ChatSSEUI DEBUG] _run_loop started for session {self._session_id}")
        await self._broadcast_status(
            {"connected": True, "session_id": self._session_id}
        )
        while True:
            try:
                text = await asyncio.wait_for(self._output_queue.get(), timeout=0.1)
                print(f"[ChatSSEUI DEBUG] Got from queue: {text[:100]}...")
                if text.strip():
                    await self._broadcast_text(text)
                    print(f"[ChatSSEUI DEBUG] Broadcasted text")
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                print(f"[ChatSSEUI DEBUG] Error in _run_loop: {e}")
            await asyncio.sleep(0.01)


class ChatUIConfig:
    """Configuration for ChatSSEUI."""

    def __init__(
        self,
        assistant_name: str = "Assistant",
        exit_commands: list[str] = [],
        info_commands: list[str] = [],
        save_commands: list[str] = [],
        load_commands: list[str] = [],
        attach_commands: list[str] = [],
        redirect_output_commands: list[str] = [],
        yolo_toggle_commands: list[str] = [],
        set_model_commands: list[str] = [],
        exec_commands: list[str] = [],
        summarize_commands: list[str] = [],
        is_yolo: bool = False,
        yolo_xcom_key: str = "",
        conversation_session_name: str = "",
    ):
        self.assistant_name = assistant_name
        self.exit_commands = exit_commands
        self.info_commands = info_commands
        self.save_commands = save_commands
        self.load_commands = load_commands
        self.attach_commands = attach_commands
        self.redirect_output_commands = redirect_output_commands
        self.yolo_toggle_commands = yolo_toggle_commands
        self.set_model_commands = set_model_commands
        self.exec_commands = exec_commands
        self.summarize_commands = summarize_commands
        self.is_yolo = is_yolo
        self.yolo_xcom_key = yolo_xcom_key
        self.conversation_session_name = conversation_session_name
