"""
SSE Chat - Server-Sent Events for Real-time LLM Chat

This example shows how to create an SSE-based HTTP API for LLM chat.
When you run `zrb llm chat`, an HTTP server starts with SSE streaming.

══════════════════════════════════════════════════════════════════════════════
KEY CONCEPT: EventDrivenUI + Server-Sent Events
══════════════════════════════════════════════════════════════════════════════

EventDrivenUI handles the queue pattern automatically:
- When ask_user() is called, it blocks on an internal queue
- When messages arrive, call handle_incoming_message() to route them

Server-Sent Events provide real-time streaming:
- Client connects to GET /stream and receives all output in real-time
- Client sends messages via POST /chat
- No polling, no missed messages!

══════════════════════════════════════════════════════════════════════════════

Usage:
    export OPENAI_API_KEY="your-key"
    cd /path/to/zrb/examples/chat-sse
    zrb llm chat
    
    # Terminal 2: Connect to SSE stream (stays connected, receives all output)
    curl -N http://localhost:8000/stream
    
    # Terminal 3: Send messages
    curl -X POST http://localhost:8000/chat \
        -H "Content-Type: application/json" \
        -d '{"message": "Hello!"}'
    
    # Continue conversation
    curl -X POST http://localhost:8000/chat \
        -H "Content-Type: application/json" \
        -d '{"message": "What is 2+2?"}'
"""

import asyncio
import json
import os

from aiohttp import web

from zrb.builtin.llm.chat import llm_chat
from zrb.llm.ui.simple_ui import (
    BufferedOutputMixin,
    EventDrivenUI,
    create_ui_factory,
)
from zrb.llm.util.history_formatter import format_history_as_text
from zrb.util.cli.style import remove_style

SSE_HOST = os.environ.get("SSE_HOST", "localhost")
SSE_PORT = int(os.environ.get("SSE_PORT", "8000"))


# =============================================================================
# SSE Server Singleton
# =============================================================================


class SSEServer:
    """Shared SSE server instance - manages clients and message routing."""

    _instance: "SSEServer | None" = None

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._ui_instance: "SSEUI | None" = None
        self._output_queue: asyncio.Queue[str] = asyncio.Queue()

    @classmethod
    def get(cls) -> "SSEServer":
        if cls._instance is None:
            cls._instance = cls(SSE_HOST, SSE_PORT)
        return cls._instance

    def set_ui(self, ui: "SSEUI") -> None:
        """Set the UI instance for message routing."""
        self._ui_instance = ui

    async def broadcast(self, text: str) -> None:
        """Queue text for broadcast to all SSE clients.

        Messages are sent via _output_queue and delivered to ONE client
        (first to request). For multi-client broadcast, use per-client queues.
        """
        clean = remove_style(text).strip()
        if not clean:
            return
        await self._output_queue.put(clean)

    async def start(self) -> None:
        """Start the HTTP/SSE server."""
        self._app = web.Application()
        self._app.router.add_post("/chat", self._handle_chat)
        self._app.router.add_get("/stream", self._handle_stream)
        self._app.router.add_get("/status", self._handle_status)
        self._app.router.add_get("/history", self._handle_history)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()

        print(f"🌐 SSE Chat Server: http://{self.host}:{self.port}")
        print("")
        print("Endpoints:")
        print("  POST /chat    - Send message")
        print("  GET  /stream  - SSE stream (stays connected)")
        print("  GET  /status  - Session status")
        print("  GET  /history - Get conversation history")
        print("")
        print("Press CTRL+C to exit")

    async def _handle_chat(self, request: web.Request) -> web.Response:
        """POST /chat - Send a message."""
        if not self._ui_instance:
            return web.json_response({"error": "UI not initialized"}, status=500)

        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        message = data.get("message", "")
        if not message:
            return web.json_response({"error": "Message required"}, status=400)

        # Route through handle_incoming_message()
        self._ui_instance.handle_incoming_message(message)

        return web.json_response({"status": "sent", "message": message})

    async def _handle_stream(self, request: web.Request) -> web.StreamResponse:
        """GET /stream - SSE endpoint for real-time output."""
        response = web.StreamResponse(
            status=200,
            reason="OK",
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

        await response.prepare(request)

        try:
            # Send welcome message
            await response.write(b'event: connected\ndata: {"status": "connected"}\n\n')

            # Keep connection alive and send output
            while True:
                try:
                    # Wait for output with timeout for keepalive
                    async with asyncio.timeout(30):
                        text = await self._output_queue.get()
                        # Use ensure_ascii=False to preserve Unicode (emojis, etc.)
                        await response.write(
                            f"data: {json.dumps(text, ensure_ascii=False)}\n\n".encode()
                        )
                except asyncio.TimeoutError:
                    # Send keepalive comment
                    await response.write(b": keepalive\n\n")
        except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
            # Client disconnected
            pass

        return response

    async def _handle_status(self, request: web.Request) -> web.Response:
        """GET /status - Check session status."""
        if not self._ui_instance:
            return web.json_response({"error": "UI not initialized"}, status=500)

        return web.json_response(
            {
                "waiting_for_input": self._ui_instance._waiting_for_input,
                "session_name": self._ui_instance._conversation_session_name,
            }
        )

    async def _handle_history(self, request: web.Request) -> web.Response:
        """GET /history - Get conversation history.

        Query params:
            session: Optional session name (defaults to current session)
            format: "text" or "json" (defaults to "text")

        Returns:
            Formatted conversation history or raw JSON
        """
        if not self._ui_instance:
            return web.json_response({"error": "UI not initialized"}, status=500)

        # Get session name from query param or use current session
        session_name = request.query.get(
            "session", self._ui_instance._conversation_session_name
        )
        output_format = request.query.get("format", "text")
        max_length = int(request.query.get("max_length", "10000"))

        try:
            # Access history manager through UI instance
            history_manager = self._ui_instance._history_manager
            messages = history_manager.load(session_name)

            if output_format == "json":
                # Return raw message structure as JSON
                # ModelMessage objects have .model_dump() method
                messages_data = []
                for msg in messages:
                    if hasattr(msg, "model_dump"):
                        messages_data.append(msg.model_dump())
                    else:
                        # Fallback for older pydantic-ai versions
                        messages_data.append(str(msg))

                return web.json_response(
                    {
                        "session_name": session_name,
                        "message_count": len(messages),
                        "messages": messages_data,
                    }
                )
            else:
                # Return formatted text
                history_text = format_history_as_text(messages, max_length=max_length)
                return web.Response(
                    text=history_text,
                    content_type="text/plain",
                    charset="utf-8",
                )

        except FileNotFoundError:
            return web.json_response(
                {"error": f"Session '{session_name}' not found"}, status=404
            )
        except Exception as e:
            return web.json_response(
                {"error": f"Failed to load history: {str(e)}"}, status=500
            )


# =============================================================================
# SSE UI - EventDrivenUI with SSE Broadcasting
# =============================================================================


class SSEUI(EventDrivenUI, BufferedOutputMixin):
    """SSE UI using EventDrivenUI with buffered output broadcasting.

    Uses:
    - EventDrivenUI: Automatic queue + event loop management
    - BufferedOutputMixin: Batches output to avoid fragmented messages
    - SSEServer: Broadcasts to all connected SSE clients

    Message flow:
    - POST /chat calls handle_incoming_message()
    - print() buffers output and sends via SSE to all clients
    - get_input() asks via SSE and waits for _input_queue
    """

    def __init__(self, server: SSEServer, **kwargs):
        super().__init__(**kwargs)
        BufferedOutputMixin.__init__(self, flush_interval=0.3, max_buffer_size=3000)
        self.server = server
        server.set_ui(self)

    async def _send_buffered(self, text: str) -> None:
        """Broadcast buffered content to all SSE clients."""
        await self.server.broadcast(text)

    async def print(self, text: str) -> None:
        """Buffer output (called by append_to_output during streaming)."""
        self.buffer_output(text)

    async def get_input(self, prompt: str) -> str:
        """Send question via SSE and wait for response.

        Overrides EventDrivenUI.get_input() to broadcast the question.
        """
        if prompt:
            # Broadcast the question to all clients
            clean_prompt = remove_style(prompt).strip()
            if clean_prompt:
                await self.server.broadcast(f"❓ {clean_prompt}")

        self._waiting_for_input = True
        try:
            return await self._input_queue.get()
        finally:
            self._waiting_for_input = False

    async def start_event_loop(self) -> None:
        """Start the SSE server and flush loop."""
        # Start the HTTP/SSE server
        await self.server.start()

        # Start the periodic flush loop
        await self.start_flush_loop()

        # Keep running forever
        while True:
            await asyncio.sleep(3600)


# =============================================================================
# Integration with zrb llm chat - SSE + CLI Dual Mode
# =============================================================================

server = SSEServer.get()

# Create SSE UI factory
sse_ui_factory = create_ui_factory(SSEUI, server=server)

# Add SSE UI alongside default terminal UI (dual mode)
# This gives you both CLI input/output AND SSE streaming
llm_chat.append_ui_factory(sse_ui_factory)

print(f"🌐 SSE + CLI dual mode enabled")
print("   Both terminal and SSE receive all messages.")
print("   Use terminal or POST /chat to send messages.")
