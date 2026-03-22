"""
WebSocket UI Example - Minimal Implementation

Pattern: Request-Response (ask_user can block on queue)

┌─────────────┐     WebSocket      ┌─────────────┐
│   Client    │ ◄───────────────► │ WebSocketUI │
└─────────────┘                    └──────┬──────┘
                                          │
                                   ┌──────▼──────┐
                                   │  LLMChatTask │
                                   └─────────────┘

Usage:
    export OPENAI_API_KEY="your-key"
    zrb llm chat

    # Connect with: websocat ws://localhost:8765
"""

import asyncio
import json
import os

from websockets.server import serve

from zrb.builtin.llm.chat import llm_chat
from zrb.context.any_context import AnyContext
from zrb.llm.app.base_ui import BaseUI

WS_HOST = os.environ.get("WS_HOST", "localhost")
WS_PORT = int(os.environ.get("WS_PORT", "8765"))

# ─────────────────────────────────────────────────────────────────────────────
# WebSocket UI - Inherit from BaseUI, implement 4 methods
# ─────────────────────────────────────────────────────────────────────────────


class WebSocketUI(BaseUI):
    """Minimal WebSocket UI - ask_user blocks on a queue."""

    def __init__(self, ws, ctx, llm_task, history_manager, **kwargs):
        super().__init__(
            ctx=ctx, llm_task=llm_task, history_manager=history_manager, **kwargs
        )
        self.ws = ws
        self.input_queue: asyncio.Queue = asyncio.Queue()

    # Required: Send output to client
    def append_to_output(self, *values, sep=" ", end="\n", **kwargs):
        msg = sep.join(str(v) for v in values) + end
        asyncio.create_task(self.ws.send(json.dumps({"type": "output", "text": msg})))

    # Required: Block until user responds
    async def ask_user(self, prompt: str) -> str:
        if prompt:
            await self.ws.send(json.dumps({"type": "question", "text": prompt}))
        return await self.input_queue.get()  # Blocks until client responds

    # Required: Shell commands (not supported in WebSocket)
    async def run_interactive_command(self, cmd, shell=False):
        await self.ws.send(json.dumps({"type": "error", "text": "Shell disabled"}))
        return 1

    # Required: Run the event loop
    async def run_async(self) -> str:
        self._process_messages_task = asyncio.create_task(self._process_messages_loop())
        if self._initial_message:
            self._submit_user_message(self._llm_task, self._initial_message)

        async def receive():
            async for msg in self.ws:
                data = json.loads(msg)
                if data.get("type") == "response":
                    await self.input_queue.put(data["text"])  # Unblock ask_user
                elif data.get("type") == "chat":
                    self._submit_user_message(self._llm_task, data["text"])

        recv_task = asyncio.create_task(receive())
        try:
            await recv_task  # Run until disconnected
        finally:
            recv_task.cancel()
            self._process_messages_task.cancel()
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket Server - Connect WebSocketUI to llm_chat
# ─────────────────────────────────────────────────────────────────────────────


async def handler(websocket):
    """Handle WebSocket connection. Creates one UI per connection."""
    await websocket.send(json.dumps({"type": "welcome", "text": "Connected!"}))

    # Create UI for this connection
    ui = WebSocketUI(
        ws=websocket,
        ctx=AnyContext.get_temporary_context(),
        llm_task=llm_chat,
        history_manager=None,
        initial_message="",
    )
    await ui.run_async()


async def main():
    print(f"WebSocket server: ws://{WS_HOST}:{WS_PORT}")
    print("Connect with: websocat ws://localhost:8765")
    async with serve(handler, WS_HOST, WS_PORT):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
