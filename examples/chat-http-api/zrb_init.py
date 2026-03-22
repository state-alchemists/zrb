"""
HTTP API UI Example for Zrb LLM Chat

This example demonstrates how to create an HTTP REST API UI for LLM chat
using BaseUI. This is a POLLING pattern where clients poll for responses.

Pattern: Request-Response with Polling
    - POST /chat -> returns session_id, starts LLM
    - GET /poll?session=id -> returns pending messages
    - POST /input -> provides user input for ask_user()

Architecture:
    ┌─────────────────┐                    ┌─────────────────┐
    │  HTTP Client    │                    │   HttpAPIUI     │
    │  (curl/browsr) │                    │   (BaseUI)      │
    └────────┬────────┘                    └────────┬────────┘
             │                                      │
             │  POST /chat {message}                  │
             │ ──────────────────────────────────────>│
             │                                      │
             │  GET /poll?session=id                  │
             │ ──────────────────────────────────────>│
             │                                      │
             │  {"messages": [...]}                │
             │ <─────────────────────────────────────│
             │                                      │
             │  POST /input {session, response}      │
             │ ──────────────────────────────────────>│
             │                                      │

Usage:
    cd examples/chat-http-api
    zrb llm chat

    # Then use curl or HTTP client:
    curl -X POST http://localhost:8000/chat -d '{"message": "Hello"}'
    curl http://localhost:8000/poll?session=abc123
    curl -X POST http://localhost:8000/input -d '{"session": "abc123", "response": "y"}'
"""

import asyncio
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from aiohttp import web

from zrb.builtin.llm.chat import llm_chat
from zrb.context.any_context import AnyContext
from zrb.llm.app.base_ui import BaseUI
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.task.llm_task import LLMTask

# =============================================================================
# Configuration
# =============================================================================

HTTP_HOST = os.environ.get("ZRB_HTTP_HOST", "localhost")
HTTP_PORT = int(os.environ.get("ZRB_HTTP_PORT", "8000"))


# =============================================================================
# Session Storage (for polling)
# =============================================================================


@dataclass
class SessionState:
    """State for a single chat session."""

    session_id: str
    ui: "HttpAPIUI"
    output_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    input_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)


# Global session storage
_sessions: dict[str, SessionState] = {}


# =============================================================================
# HTTP API UI Implementation
# =============================================================================


class HttpAPIUI(BaseUI):
    """HTTP REST API based UI for LLM Chat.

    This demonstrates the POLLING pattern:

    1. Client POSTs a message to /chat
    2. Server creates session, starts LLM
    3. Client GETs /poll to receive messages
    4. When ask_user() is called, client sees "question" in poll
    5. Client POSTs response to /input
    6. ask_user() returns the response

    This pattern works well for:
    - REST APIs
    - Server-Sent Events (SSE)
    - Applications that can't maintain WebSocket connections
    """

    def __init__(
        self,
        session_id: str,
        ctx: AnyContext,
        llm_task: LLMTask,
        history_manager: AnyHistoryManager,
        **kwargs,
    ):
        super().__init__(
            ctx=ctx,
            yolo_xcom_key=f"_yolo_http_{session_id}",
            assistant_name=kwargs.get("assistant_name", "Assistant"),
            llm_task=llm_task,
            history_manager=history_manager,
            initial_message=kwargs.get("initial_message", ""),
            initial_attachments=kwargs.get("initial_attachments", []),
            conversation_session_name=kwargs.get(
                "conversation_session_name", session_id
            ),
            yolo=kwargs.get("yolo", False),
            exit_commands=kwargs.get("exit_commands", ["/exit", "/quit"]),
            info_commands=kwargs.get("info_commands", ["/help", "/?"]),
        )
        self.session_id = session_id
        self._output_queue: asyncio.Queue = asyncio.Queue()
        self._input_queue: asyncio.Queue = asyncio.Queue()
        self._question_event: asyncio.Event = asyncio.Event()
        self._current_question: str | None = None
        self._running = False

    # ==========================================================================
    # REQUIRED METHODS - BaseUI implementation
    # ==========================================================================

    def append_to_output(self, *values, sep=" ", end="\n", file=None, flush=False):
        """Queue output message for polling."""
        content = sep.join(str(v) for v in values) + end

        message = {
            "type": "output",
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }
        self._output_queue.put_nowait(message)

        # Track for result extraction
        if (
            content.strip()
            and not content.startswith("\n")
            and not content.startswith("🤖")
        ):
            self._last_result_data = content.rstrip("\n")

    async def ask_user(self, prompt: str) -> str:
        """Wait for user input via /input endpoint.

        This implements the POLLING pattern:
        1. Put question in output queue
        2. Wait for /input to provide response
        3. Return the response
        """
        # Put question in queue so /poll sees it
        question_msg = {
            "type": "question",
            "content": prompt,
            "timestamp": datetime.now().isoformat(),
        }
        self._output_queue.put_nowait(question_msg)

        # Set current question for /input to see
        self._current_question = prompt
        self._question_event.set()

        # Wait for input from /input endpoint
        response = await self._input_queue.get()

        # Clear question state
        self._current_question = None
        self._question_event.clear()

        # Put response confirmation in output queue
        response_msg = {
            "type": "response_received",
            "content": (
                f"Received: {response[:50]}..."
                if len(response) > 50
                else f"Received: {response}"
            ),
            "timestamp": datetime.now().isoformat(),
        }
        self._output_queue.put_nowait(response_msg)

        return response

    async def run_interactive_command(self, cmd: str | list[str], shell: bool = False):
        """Shell commands not supported in HTTP API mode."""
        message = {
            "type": "error",
            "content": "Shell commands not supported in HTTP API mode.",
            "timestamp": datetime.now().isoformat(),
        }
        self._output_queue.put_nowait(message)
        return 1

    async def run_async(self) -> str:
        """Run the HTTP API UI event loop.

        This is simpler than WebSocket because:
        - No need to maintain connection state
        - Messages are polled via /poll endpoint
        - Input comes via /input endpoint
        """
        self._process_messages_task = asyncio.create_task(self._process_messages_loop())

        if self._initial_message:
            self._submit_user_message(self._llm_task, self._initial_message)

        self._running = True

        try:
            while self._running:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        finally:
            self._process_messages_task.cancel()
            try:
                await self._process_messages_task
            except asyncio.CancelledError:
                pass

        return self.last_output

    def on_exit(self):
        """Cleanup on exit."""
        self._running = False
        message = {
            "type": "exit",
            "content": "Session ended. Goodbye!",
            "timestamp": datetime.now().isoformat(),
        }
        self._output_queue.put_nowait(message)

    # ==========================================================================
    # HTTP API-specific methods
    # ==========================================================================

    async def get_pending_messages(self) -> list[dict]:
        """Get all pending messages for /poll endpoint."""
        messages = []
        while not self._output_queue.empty():
            messages.append(self._output_queue.get_nowait())
        return messages

    async def provide_input(self, response: str):
        """Provide input for ask_user() from /input endpoint."""
        await self._input_queue.put(response)

    def get_current_question(self) -> str | None:
        """Get the current question (if any) for /status endpoint."""
        return self._current_question


# =============================================================================
# Session Management
# =============================================================================


def create_session(
    ctx: AnyContext,
    llm_task: LLMTask,
    history_manager: AnyHistoryManager,
    initial_message: str = "",
) -> SessionState:
    """Create a new session with its own HttpAPIUI."""
    session_id = str(uuid.uuid4())[:8]

    ui = HttpAPIUI(
        session_id=session_id,
        ctx=ctx,
        llm_task=llm_task,
        history_manager=history_manager,
        initial_message=initial_message,
    )

    session = SessionState(
        session_id=session_id,
        ui=ui,
    )

    _sessions[session_id] = session
    return session


async def run_session(session: SessionState):
    """Run a session's UI in a background task."""
    await session.ui.run_async()


# =============================================================================
# HTTP API Endpoints
# =============================================================================


async def handle_chat(request: web.Request) -> web.Response:
    """POST /chat - Start or continue a conversation."""
    try:
        data = await request.json()
        message = data.get("message", "")
        session_id = data.get("session_id")

        if session_id and session_id in _sessions:
            # Continue existing session
            session = _sessions[session_id]
            session.ui._submit_user_message(session.ui._llm_task, message)
        else:
            # Create new session
            # NOTE: In production, you'd get ctx and llm_task from proper setup
            session = create_session(
                ctx=AnyContext.get_temporary_context(),
                llm_task=llm_chat,
                history_manager=None,  # Would be proper history manager
                initial_message=message,
            )
            # Start session in background
            asyncio.create_task(run_session(session))

        return web.json_response(
            {
                "session_id": session.session_id,
                "status": "started" if not session_id else "continued",
            }
        )
    except Exception as e:
        return web.json_response(
            {
                "error": str(e),
            },
            status=500,
        )


async def handle_poll(request: web.Request) -> web.Response:
    """GET /poll?session=id - Get pending messages."""
    session_id = request.query.get("session")

    if not session_id or session_id not in _sessions:
        return web.json_response(
            {
                "error": "Invalid session",
            },
            status=404,
        )

    session = _sessions[session_id]
    messages = await session.ui.get_pending_messages()

    return web.json_response(
        {
            "session_id": session_id,
            "messages": messages,
            "current_question": session.ui.get_current_question(),
        }
    )


async def handle_input(request: web.Request) -> web.Response:
    """POST /input - Provide input for ask_user()."""
    try:
        data = await request.json()
        session_id = data.get("session_id")
        response = data.get("response", "")

        if not session_id or session_id not in _sessions:
            return web.json_response(
                {
                    "error": "Invalid session",
                },
                status=404,
            )

        session = _sessions[session_id]

        if session.ui.get_current_question() is None:
            return web.json_response(
                {
                    "error": "No question pending",
                },
                status=400,
            )

        await session.ui.provide_input(response)

        return web.json_response(
            {
                "status": "ok",
                "session_id": session_id,
            }
        )
    except Exception as e:
        return web.json_response(
            {
                "error": str(e),
            },
            status=500,
        )


async def handle_status(request: web.Request) -> web.Response:
    """GET /status?session=id - Get session status."""
    session_id = request.query.get("session")

    if not session_id or session_id not in _sessions:
        return web.json_response(
            {
                "error": "Invalid session",
            },
            status=404,
        )

    session = _sessions[session_id]

    return web.json_response(
        {
            "session_id": session_id,
            "running": session.ui._running,
            "current_question": session.ui.get_current_question(),
            "pending_messages": session.ui._output_queue.qsize(),
        }
    )


# =============================================================================
# HTTP Server Setup
# =============================================================================


def create_app() -> web.Application:
    """Create the aiohttp application."""
    app = web.Application()

    app.router.add_post("/chat", handle_chat)
    app.router.add_get("/poll", handle_poll)
    app.router.add_post("/input", handle_input)
    app.router.add_get("/status", handle_status)

    return app


async def run_server():
    """Run the HTTP API server."""
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, HTTP_HOST, HTTP_PORT)

    print(f"Starting HTTP API server on http://{HTTP_HOST}:{HTTP_PORT}")
    print("\nEndpoints:")
    print(f"  POST   http://{HTTP_HOST}:{HTTP_PORT}/chat")
    print(f"  GET    http://{HTTP_HOST}:{HTTP_PORT}/poll?session=ID")
    print(f"  POST   http://{HTTP_HOST}:{HTTP_PORT}/input")
    print(f"  GET    http://{HTTP_HOST}:{HTTP_PORT}/status?session=ID")

    await site.start()
    await asyncio.Future()  # Run forever


if __name__ == "__main__":
    asyncio.run(run_server())


# =============================================================================
# Integration with zrb llm chat
# =============================================================================

# For integration with zrb, you would:
# 1. Run the HTTP server as a separate process/service
# 2. Each session creates a new HttpAPIUI
# 3. Clients interact via REST endpoints
