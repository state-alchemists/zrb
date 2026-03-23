"""
HTTP API UI - Simplified with PollingUI

This example shows how to create an HTTP API for LLM chat
using the PollingUI base class.

══════════════════════════════════════════════════════════════════════════════
COMPARISON:
══════════════════════════════════════════════════════════════════════════════
BEFORE (BaseUI):                    AFTER (PollingUI):
────────────────────────────────    ────────────────────────────────
- 100 lines                        → 60 lines
- Manual queue management           → Built-in output_queue/input_queue
- 25+ constructor params            → Just implement print()
- Complex session handling          → PollingUI provides queues

══════════════════════════════════════════════════════════════════════════════

PATTERN: PollingUI provides queues for HTTP polling.

┌─────────────┐    POST /chat     ┌─────────────┐
│   Client    │ ───────────────► │  HttpAPIUI  │
│             │    GET /poll     │             │
│             │ ◄─────────────── │             │
│             │   POST /response │             │
└─────────────┘                  └──────┬──────┘
                                        │
                                 ┌──────▼──────┐
                                 │  LLMChatTask │
                                 └─────────────┘

══════════════════════════════════════════════════════════════════════════════

Usage:
    # Terminal 1: Start server
    export OPENAI_API_KEY="your-key"
    python -m zrb.llm.chat --http

    # Terminal 2: Use API
    curl -X POST http://localhost:8000/chat -d '{"message":"hello"}'
    curl http://localhost:8000/poll?session=abc123
    curl -X POST http://localhost:8000/respond -d '{"session":"abc123","text":"y"}'
"""

import asyncio
import uuid

from aiohttp import web

from zrb.builtin.llm.chat import llm_chat
from zrb.context.any_context import AnyContext
from zrb.llm.app.simple_ui import PollingUI

HTTP_HOST = "localhost"
HTTP_PORT = 8000


# =============================================================================
# HTTP API UI - PollingUI provides the queues!
# =============================================================================


class HttpAPIUI(PollingUI):
    """HTTP API UI using PollingUI's built-in queues.

    output_queue → GET /poll retrieves messages
    input_queue → POST /respond provides user responses
    """

    def print(self, text: str) -> None:
        """PollingUI already queues to output_queue, nothing more needed!"""
        # PollingUI.print() already puts to output_queue
        super().print(text)


# =============================================================================
# Session Management
# =============================================================================

sessions: dict[str, HttpAPIUI] = {}


# =============================================================================
# HTTP Endpoints
# =============================================================================


async def handle_chat(request: web.Request) -> web.Response:
    """POST /chat - Start a new chat session."""
    data = await request.json()
    message = data.get("message", "")

    # Create new session
    session_id = str(uuid.uuid4())[:8]
    ui = HttpAPIUI(
        ctx=AnyContext.get_temporary_context(),
        llm_task=llm_chat,
        history_manager=None,
        initial_message=message,
    )
    sessions[session_id] = ui

    # Start the UI in background
    asyncio.create_task(ui.run_async())

    return web.json_response({"session_id": session_id})


async def handle_poll(request: web.Request) -> web.Response:
    """GET /poll?session=id - Get pending messages."""
    session_id = request.query.get("session")
    if session_id not in sessions:
        return web.json_response({"error": "Invalid session"}, status=404)

    ui = sessions[session_id]
    messages = []

    # Drain all messages from PollingUI's output_queue
    while not ui.output_queue.empty():
        messages.append(ui.output_queue.get_nowait())

    return web.json_response({"messages": messages})


async def handle_respond(request: web.Request) -> web.Response:
    """POST /respond - Provide response for ask_user()."""
    data = await request.json()
    session_id = data.get("session")
    text = data.get("text", "")

    if session_id not in sessions:
        return web.json_response({"error": "Invalid session"}, status=404)

    # Put response into PollingUI's input_queue (unblocks ask_user)
    sessions[session_id].input_queue.put_nowait(text)
    return web.json_response({"status": "ok"})


# =============================================================================
# Server Setup
# =============================================================================

app = web.Application()
app.router.add_post("/chat", handle_chat)
app.router.add_get("/poll", handle_poll)
app.router.add_post("/respond", handle_respond)


def run_server():
    """Run the HTTP API server."""
    print(f"HTTP API server: http://{HTTP_HOST}:{HTTP_PORT}")
    print("\nEndpoints:")
    print("  POST /chat    - Start session: {'message': 'hello'}")
    print("  GET  /poll    - Get messages: ?session=ID")
    print("  POST /respond - Send response: {'session': 'ID', 'text': 'y'}")
    web.run_app(app, host=HTTP_HOST, port=HTTP_PORT)


if __name__ == "__main__":
    run_server()
