"""
HTTP API UI Example - Minimal Implementation

Pattern: Polling (clients poll for messages, ask_user blocks)

┌─────────────┐    POST /chat     ┌─────────────┐
│   Client    │ ───────────────► │  HttpAPIUI  │
│             │    GET /poll     │             │
│             │ ◄─────────────── │             │
│             │   POST /input    │             │
└─────────────┘                  └──────┬──────┘
                                        │
                                 ┌──────▼──────┐
                                 │  LLMChatTask │
                                 └─────────────┘

Usage:
    # Terminal 1: Start server
    export OPENAI_API_KEY="your-key"
    zrb llm chat

    # Terminal 2: Use API
    curl -X POST http://localhost:8000/chat -d '{"message":"hello"}'
    curl http://localhost:8000/poll?session=abc123
    curl -X POST http://localhost:8000/input -d '{"session":"abc123","response":"y"}'
"""

import asyncio
import uuid

from aiohttp import web

from zrb.builtin.llm.chat import llm_chat
from zrb.context.any_context import AnyContext
from zrb.llm.app.base_ui import BaseUI

# ─────────────────────────────────────────────────────────────────────────────
# HTTP API UI - ask_user blocks on queue, clients poll for messages
# ─────────────────────────────────────────────────────────────────────────────


class HttpAPIUI(BaseUI):
    """Minimal HTTP API UI - clients poll for output, ask_user blocks."""

    def __init__(self, session_id: str, ctx, llm_task, history_manager, **kwargs):
        super().__init__(
            ctx=ctx, llm_task=llm_task, history_manager=history_manager, **kwargs
        )
        self.session_id = session_id
        self.output_queue: asyncio.Queue = asyncio.Queue()
        self.input_queue: asyncio.Queue = asyncio.Queue()

    # Required: Queue output for /poll endpoint
    def append_to_output(self, *values, sep=" ", end="\n", **kwargs):
        self.output_queue.put_nowait(sep.join(str(v) for v in values) + end)

    # Required: Block until /input provides response
    async def ask_user(self, prompt: str) -> str:
        if prompt:
            self.output_queue.put_nowait(f"❓ {prompt}")
        return await self.input_queue.get()  # Blocks until client POSTs to /input

    # Required: Shell disabled
    async def run_interactive_command(self, cmd, shell=False):
        self.output_queue.put_nowait("⚠️ Shell disabled")
        return 1

    # Required: Run the loop
    async def run_async(self) -> str:
        self._process_messages_task = asyncio.create_task(self._process_messages_loop())
        if self._initial_message:
            self._submit_user_message(self._llm_task, self._initial_message)

        try:
            while True:
                await asyncio.sleep(0.1)  # Keep running
        except asyncio.CancelledError:
            pass
        finally:
            self._process_messages_task.cancel()
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# Session Management - One UI per session
# ─────────────────────────────────────────────────────────────────────────────

sessions: dict[str, HttpAPIUI] = {}

# ─────────────────────────────────────────────────────────────────────────────
# HTTP Endpoints
# ─────────────────────────────────────────────────────────────────────────────


async def handle_chat(request):
    """POST /chat - Start or continue conversation."""
    data = await request.json()
    message = data.get("message", "")

    # Create new session
    session_id = str(uuid.uuid4())[:8]
    ui = HttpAPIUI(
        session_id=session_id,
        ctx=AnyContext.get_temporary_context(),
        llm_task=llm_chat,
        history_manager=None,
        initial_message=message,
    )
    sessions[session_id] = ui
    asyncio.create_task(ui.run_async())

    return web.json_response({"session_id": session_id})


async def handle_poll(request):
    """GET /poll?session=id - Get pending messages."""
    session_id = request.query.get("session")
    if session_id not in sessions:
        return web.json_response({"error": "Invalid session"}, status=404)

    ui = sessions[session_id]
    messages = []
    while not ui.output_queue.empty():
        messages.append(ui.output_queue.get_nowait())

    return web.json_response({"messages": messages})


async def handle_input(request):
    """POST /input - Provide response for ask_user."""
    data = await request.json()
    session_id = data.get("session")
    response = data.get("response", "")

    if session_id not in sessions:
        return web.json_response({"error": "Invalid session"}, status=404)

    sessions[session_id].input_queue.put_nowait(response)
    return web.json_response({"status": "ok"})


# ─────────────────────────────────────────────────────────────────────────────
# Server Setup
# ─────────────────────────────────────────────────────────────────────────────

app = web.Application()
app.router.add_post("/chat", handle_chat)
app.router.add_get("/poll", handle_poll)
app.router.add_post("/input", handle_input)

if __name__ == "__main__":
    web.run_app(app, host="localhost", port=8000)
