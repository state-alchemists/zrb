"""
WebSocket UI Example for Zrb LLM Chat

This example demonstrates how to create a WebSocket-based UI for LLM chat
using BaseUI. This is a REQUEST-RESPONSE pattern where ask_user() can block.

Pattern: Request-Response
    - User sends message -> bot responds
    - ask_user() blocks until message received
    - Simple linear flow

Architecture:
    ┌─────────────────┐     WebSocket      ┌─────────────────┐
    │   Browser/Client │ <───────────────> │  WebSocketUI    │
    │   (JavaScript)  │                   │  (BaseUI)       │
    └─────────────────┘                   └─────────────────┘
                                                │
                                                ▼
                                         ┌─────────────────┐
                                         │   LLMChatTask   │
                                         └─────────────────┘

Usage:
    cd examples/chat-websocket
    zrb llm chat

    # Then connect with a WebSocket client:
    # websocket-client ws://localhost:8765
    #
    # Or use a browser:
    # const ws = new WebSocket('ws://localhost:8765');
    # ws.onmessage = (e) => console.log(e.data);
    # ws.send('Hello!');
"""

import asyncio
import json
import os
from typing import Any

from websockets.server import serve

from zrb.builtin.llm.chat import llm_chat
from zrb.context.any_context import AnyContext
from zrb.llm.app.base_ui import BaseUI
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.task.llm_task import LLMTask

# =============================================================================
# Configuration
# =============================================================================

WEBSOCKET_HOST = os.environ.get("ZRB_WS_HOST", "localhost")
WEBSOCKET_PORT = int(os.environ.get("ZRB_WS_PORT", "8765"))


# =============================================================================
# WebSocket UI Implementation
# =============================================================================


class WebSocketUI(BaseUI):
    """WebSocket-based UI for LLM Chat.

    This demonstrates the REQUEST-RESPONSE pattern:
    - append_to_output() sends message to WebSocket client
    - ask_user() blocks until client responds
    - Simple, linear conversation flow

    For EVENT-DRIVEN pattern (Telegram, Discord), see chat-telegram example.
    """

    def __init__(
        self,
        websocket,
        ctx: AnyContext,
        llm_task: LLMTask,
        history_manager: AnyHistoryManager,
        **kwargs,
    ):
        super().__init__(
            ctx=ctx,
            yolo_xcom_key=f"_yolo_ws_{id(self)}",
            assistant_name=kwargs.get("assistant_name", "Assistant"),
            llm_task=llm_task,
            history_manager=history_manager,
            initial_message=kwargs.get("initial_message", ""),
            initial_attachments=kwargs.get("initial_attachments", []),
            conversation_session_name=kwargs.get("conversation_session_name", ""),
            yolo=kwargs.get("yolo", False),
            exit_commands=kwargs.get("exit_commands", ["/exit", "/quit"]),
            info_commands=kwargs.get("info_commands", ["/help", "/?"]),
        )
        self.ws = websocket
        self._input_queue: asyncio.Queue[str] = asyncio.Queue()
        self._running = False

    # ==========================================================================
    # REQUIRED METHODS - BaseUI implementation
    # ==========================================================================

    def append_to_output(self, *values, sep=" ", end="\n", file=None, flush=False):
        """Send output to WebSocket client."""
        content = sep.join(str(v) for v in values) + end

        # Send as JSON for structured communication
        message = json.dumps(
            {
                "type": "output",
                "content": content,
                "timestamp": asyncio.get_event_loop().time(),
            }
        )
        asyncio.create_task(self.ws.send(message))

        # Track for result extraction
        if (
            content.strip()
            and not content.startswith("\n")
            and not content.startswith("🤖")
        ):
            self._last_result_data = content.rstrip("\n")

    async def ask_user(self, prompt: str) -> str:
        """Wait for user input from WebSocket client.

        This is the REQUEST-RESPONSE pattern:
        - Send the prompt (if any)
        - Block until client responds
        - Return the response
        """
        if prompt:
            # Send prompt as a question
            message = json.dumps(
                {
                    "type": "question",
                    "content": prompt,
                }
            )
            await self.ws.send(message)
        else:
            # Signal that we're waiting for input
            message = json.dumps(
                {
                    "type": "waiting",
                    "content": "Waiting for your input...",
                }
            )
            await self.ws.send(message)

        # Block until we receive a response from the client
        # This is the key difference from event-driven backends
        response = await self._input_queue.get()
        return response

    async def run_interactive_command(self, cmd: str | list[str], shell: bool = False):
        """Shell commands not supported in WebSocket UI."""
        message = json.dumps(
            {
                "type": "error",
                "content": "Shell commands are not supported in WebSocket mode.",
            }
        )
        await self.ws.send(message)
        return 1

    async def run_async(self) -> str:
        """Run the WebSocket UI event loop.

        This implements the REQUEST-RESPONSE pattern:
        1. Start message processing
        2. Start receiving messages from WebSocket
        3. Route messages to ask_user queue or command handler
        """
        self._process_messages_task = asyncio.create_task(self._process_messages_loop())

        # Send initial message if provided
        if self._initial_message:
            self._submit_user_message(self._llm_task, self._initial_message)

        self._running = True

        async def receive_messages():
            """Receive messages from WebSocket and route them."""
            try:
                async for raw_message in self.ws:
                    try:
                        data = json.loads(raw_message)
                        msg_type = data.get("type", "chat")
                        content = data.get("content", "")

                        if msg_type == "response":
                            # Response to ask_user - put in queue
                            await self._input_queue.put(content)
                        elif msg_type == "chat":
                            # Regular chat message - submit to LLM
                            self._submit_user_message(self._llm_task, content)
                        elif msg_type == "command":
                            # Handle commands (/exit, /help, etc.)
                            await self._handle_command(content)
                    except json.JSONDecodeError:
                        # Plain text - treat as chat
                        if raw_message.strip():
                            self._submit_user_message(self._llm_task, raw_message)
            except Exception:
                pass
            finally:
                self._running = False

        receive_task = asyncio.create_task(receive_messages())

        try:
            while self._running:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        finally:
            receive_task.cancel()
            self._process_messages_task.cancel()
            try:
                await receive_task
            except asyncio.CancelledError:
                pass
            try:
                await self._process_messages_task
            except asyncio.CancelledError:
                pass

        return self.last_output

    async def _handle_command(self, cmd: str):
        """Handle WebSocket commands."""
        cmd = cmd.strip().lower()
        if cmd in ("exit", "quit"):
            self._running = False
        elif cmd == "help":
            message = json.dumps(
                {
                    "type": "help",
                    "content": "Commands: /exit, /help, /yolo, /model <name>",
                }
            )
            await self.ws.send(message)
        elif cmd.startswith("model "):
            model = cmd[6:].strip()
            self._model = model
            message = json.dumps(
                {
                    "type": "info",
                    "content": f"Model switched to: {model}",
                }
            )
            await self.ws.send(message)

    def on_exit(self):
        """Cleanup on exit."""
        self._running = False
        message = json.dumps(
            {
                "type": "exit",
                "content": "Goodbye!",
            }
        )
        asyncio.create_task(self.ws.send(message))


# =============================================================================
# WebSocket Server Setup
# =============================================================================

# Store connected clients
_connected_clients: set = set()


async def handle_websocket(websocket, path=None):
    """Handle a WebSocket connection.

    This demonstrates the factory pattern for creating UI instances.
    """
    client_id = id(websocket)
    _connected_clients.add(websocket)

    try:
        # Send welcome message
        welcome = json.dumps(
            {
                "type": "welcome",
                "content": "Connected to Zrb LLM Chat! Type your message or /help for commands.",
            }
        )
        await websocket.send(welcome)

        # Keep connection alive until client disconnects
        # The UI will handle the conversation
        await websocket.wait_closed()
    finally:
        _connected_clients.discard(websocket)


# =============================================================================
# UI Factory Function
# =============================================================================


def create_websocket_ui(
    ctx: AnyContext,
    llm_task_core: LLMTask,
    history_manager: AnyHistoryManager,
    ui_commands: dict[str, list[str]],
    initial_message: str,
    initial_conversation_name: str,
    initial_yolo: bool,
    initial_attachments: list[Any],
) -> WebSocketUI:
    """Factory function that creates a WebSocketUI instance.

    This is called by llm_chat when it needs to create the UI.

    NOTE: For WebSocket, we need to set up the server separately.
    This factory creates UI for a client connection.
    """
    # This factory is called per-client connection
    # The websocket should be stored/retrieved from context
    ws = getattr(ctx, "_websocket", None)
    if ws is None:
        raise RuntimeError("No WebSocket connection in context")

    return WebSocketUI(
        websocket=ws,
        ctx=ctx,
        llm_task=llm_task_core,
        history_manager=history_manager,
        assistant_name="ZrbBot",
        initial_message=initial_message,
        conversation_session_name=initial_conversation_name,
        yolo=initial_yolo,
        initial_attachments=initial_attachments,
        exit_commands=ui_commands.get("exit", ["/exit", "/quit"]),
        info_commands=ui_commands.get("info", ["/help", "/?"]),
    )


# =============================================================================
# Alternative: Standalone WebSocket Server
# =============================================================================


async def run_standalone_server():
    """Run WebSocket server standalone (without zrb task system).

    This is useful for testing or running the WebSocket server separately.
    """
    print(f"Starting WebSocket server on ws://{WEBSOCKET_HOST}:{WEBSOCKET_PORT}")
    print("Connect with: websocket-client ws://localhost:8765")
    print("Or use a browser WebSocket API.")

    async with serve(handle_websocket, WEBSOCKET_HOST, WEBSOCKET_PORT):
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    # Run standalone server for testing
    asyncio.run(run_standalone_server())


# =============================================================================
# Integration with zrb llm chat
# =============================================================================

# For integration with zrb, you would typically:
# 1. Start the WebSocket server as a separate process/service
# 2. Each incoming connection creates a new WebSocketUI
# 3. The WebSocket server routes messages accordingly

# This example shows how to structure the code.
# For a complete working example, see the README.
