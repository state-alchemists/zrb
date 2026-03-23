"""
WebSocket UI - Simplified with PollingUI

This example shows how to create a WebSocket chat UI with minimal boilerplate
using the PollingUI base class.

══════════════════════════════════════════════════════════════════════════════
COMPARISON:
══════════════════════════════════════════════════════════════════════════════
BEFORE (BaseUI):                    AFTER (PollingUI):
────────────────────────────────    ────────────────────────────────
- 90 lines                         → 50 lines
- Manual queue management           → Built-in output_queue/input_queue
- 25+ constructor params            → Just implement print()
- Factory with 8 params             → create_ui_factory() one-liner

══════════════════════════════════════════════════════════════════════════════

PATTERN: PollingUI provides queues for external systems.

┌─────────────┐     WebSocket      ┌─────────────┐
│   Client    │ ◄───────────────► │ WebSocketUI │
└─────────────┘                    └──────┬──────┘
                                          │
                                   ┌──────▼──────┐
                                   │  LLMChatTask │
                                   └─────────────┘

Client polls:    ui.output_queue.get()  ← AI messages
Client sends:    ui.input_queue.put("response")  ← User responses

══════════════════════════════════════════════════════════════════════════════

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
from zrb.llm.app.simple_ui import PollingUI, create_ui_factory

WS_HOST = os.environ.get("WS_HOST", "localhost")
WS_PORT = int(os.environ.get("WS_PORT", "8765"))


# =============================================================================
# WebSocket UI - Inherit from PollingUI, queue-based I/O
# =============================================================================


class WebSocketUI(PollingUI):
    """WebSocket UI using PollingUI's built-in queues."""

    def __init__(self, ws, **kwargs):
        super().__init__(**kwargs)
        self.ws = ws

    def print(self, text: str) -> None:
        """Send output to WebSocket client."""
        # PollingUI has output_queue, but for WebSocket we send directly
        try:
            asyncio.create_task(
                self.ws.send(json.dumps({"type": "output", "text": text}))
            )
        except Exception:
            pass

    async def get_input(self, prompt: str) -> str:
        """Wait for input from WebSocket client."""
        if prompt:
            await self.ws.send(json.dumps({"type": "question", "text": prompt}))
        # Use PollingUI's input_queue
        return await self.input_queue.get()

    async def start_event_loop(self) -> None:
        """Listen for WebSocket messages."""

        async def receive():
            async for msg in self.ws:
                data = json.loads(msg)
                if data.get("type") == "response":
                    # Direct response to ask_user
                    await self.input_queue.put(data["text"])
                elif data.get("type") == "chat":
                    # New message to LLM
                    self.handle_incoming_message(data["text"])

        try:
            await receive()
        except Exception:
            pass


# =============================================================================
# WebSocket Server
# =============================================================================


async def handler(websocket):
    """Handle WebSocket connection."""
    await websocket.send(json.dumps({"type": "welcome", "text": "Connected!"}))

    # Create UI for this connection
    ui = WebSocketUI(
        ws=websocket,
        ctx=None,  # Will be provided by factory
        llm_task=llm_chat,
        history_manager=None,
    )
    await ui.run_async()


async def main():
    """Start WebSocket server."""
    print(f"WebSocket server: ws://{WS_HOST}:{WS_PORT}")
    print("Connect with: websocat ws://localhost:8765")
    async with serve(handler, WS_HOST, WS_PORT):
        await asyncio.Future()


# =============================================================================
# Integration with zrb
# =============================================================================

# Note: For WebSocket, we create UI per connection, not via factory
# The factory would be used for single-session mode

if __name__ == "__main__":
    asyncio.run(main())
