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
    
    # Approve tool call
    curl -X POST http://localhost:8000/chat \
        -H "Content-Type: application/json" \
        -d '{"message": "y"}'

    curl -X POST http://localhost:8000/chat \
        -H "Content-Type: application/json" \
        -d '{"message": "n"}'

    curl -X POST http://localhost:8000/chat \
        -H "Content-Type: application/json" \
        -d '{"message": "e"}'
    
    # Edit tool call args (when prompted)
    curl -X POST http://localhost:8000/chat \
        -H "Content-Type: application/json" \
        -d '{"message": {"file_path": "/new/path/file.txt"}}'
"""

import asyncio
import json
import os
from typing import Any

from aiohttp import web

from zrb.builtin.llm.chat import llm_chat
from zrb.llm.approval import ApprovalChannel, ApprovalContext, ApprovalResult
from zrb.llm.ui.simple_ui import EventDrivenUI
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
        self._approval_channel: "SSEApproval | None" = None

    @classmethod
    def get(cls) -> "SSEServer":
        if cls._instance is None:
            cls._instance = cls(SSE_HOST, SSE_PORT)
        return cls._instance

    def set_ui(self, ui: "SSEUI") -> None:
        """Set the UI instance for message routing."""
        self._ui_instance = ui

    def set_approval_channel(self, approval: "SSEApproval") -> None:
        """Set the approval channel for tool approvals."""
        self._approval_channel = approval

    async def broadcast(self, text: str, kind: str = "text") -> None:
        """Queue text for broadcast to all SSE clients."""
        clean = remove_style(text).strip()
        if not clean:
            return
        await self._output_queue.put({"text": clean, "kind": kind})

    async def start(self) -> None:
        """Start the HTTP/SSE server."""
        self._app = web.Application()
        self._app.router.add_post("/chat", self._handle_chat)
        self._app.router.add_get("/stream", self._handle_stream)
        self._app.router.add_get("/status", self._handle_status)
        self._app.router.add_get("/history", self._handle_history)
        self._app.router.add_get("/pending", self._handle_pending)

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
        print("  GET  /pending - Get pending tool approvals")
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

        # Accept both string and dict/object for message
        if isinstance(message, dict):
            # Message is already a JSON object - convert to string for processing
            message_json = message
            message_str = json.dumps(message)
        elif not message:
            return web.json_response({"error": "Message required"}, status=400)
        else:
            # Message is a string
            message_str = message
            message_json = None

        # Check if approval channel is waiting for input
        if self._approval_channel:
            # Handle edit input - accept both dict and string
            if self._approval_channel.is_waiting_for_edit():
                if message_json is not None:
                    # Direct JSON object - use directly
                    self._approval_channel.handle_edit_response_obj(message_json)
                else:
                    # String - parse as JSON/YAML
                    self._approval_channel.handle_edit_response(message_str)
                return web.json_response(
                    {"status": "edit_received", "message": message}
                )

            # If message is a dict but we're not waiting for edit, it's an error
            if message_json is not None:
                return web.json_response(
                    {
                        "error": "Unexpected JSON args - not in edit mode. Send 'e' first."
                    },
                    status=400,
                )

            # Handle approval response (y/n/e) if there's a pending tool call
            if self._approval_channel.has_pending_approvals():
                handled = self._approval_channel.handle_response(message_str)
                if handled:
                    return web.json_response(
                        {"status": "approval_handled", "message": message}
                    )

        # Route through handle_incoming_message()
        self._ui_instance.handle_incoming_message(message_str)

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
                        item = await self._output_queue.get()
                        if isinstance(item, dict):
                            payload = {
                                "type": item.get("kind", "text"),
                                "text": item.get("text", ""),
                            }
                        else:
                            payload = {"type": "text", "text": item}
                        # Use ensure_ascii=False to preserve Unicode (emojis, etc.)
                        await response.write(
                            f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()
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
        """GET /history - Get conversation history."""
        if not self._ui_instance:
            return web.json_response({"error": "UI not initialized"}, status=500)

        session_name = request.query.get(
            "session", self._ui_instance._conversation_session_name
        )
        output_format = request.query.get("format", "text")
        max_length = int(request.query.get("max_length", "10000"))

        try:
            history_manager = self._ui_instance._history_manager
            messages = history_manager.load(session_name)

            if output_format == "json":
                messages_data = []
                for msg in messages:
                    if hasattr(msg, "model_dump"):
                        messages_data.append(msg.model_dump())
                    else:
                        messages_data.append(str(msg))

                return web.json_response(
                    {
                        "session_name": session_name,
                        "message_count": len(messages),
                        "messages": messages_data,
                    }
                )
            else:
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

    async def _handle_pending(self, request: web.Request) -> web.Response:
        """GET /pending - Get pending tool approvals."""
        if not self._approval_channel:
            return web.json_response(
                {"error": "Approval channel not initialized"}, status=500
            )

        pending = self._approval_channel.get_pending_approvals()
        return web.json_response({"pending_approvals": pending})


# =============================================================================
# SSE Approval Channel - Handle tool approvals via text messages
# =============================================================================


class SSEApproval(ApprovalChannel):
    """SSE approval channel supporting approve/deny/edit via text messages.

    Similar to TelegramApproval but using plain text responses:
    - "y" / "yes" / "" -> Approve
    - "n" / "no" -> Deny
    - "e" / "edit" -> Edit (prompts for new args via next message)

    Edit flow:
    1. User sends "e" or "edit"
    2. Server broadcasts current args and sets waiting state
    3. User sends JSON/YAML args via next /chat message
    4. Server parses and approves with modified args
    """

    def __init__(self, server: SSEServer):
        self.server = server
        self._pending: dict[str, asyncio.Future[ApprovalResult]] = {}
        self._pending_context: dict[str, ApprovalContext] = {}
        self._waiting_for_edit_tool_call_id: str | None = None

    def is_waiting_for_edit(self) -> bool:
        """Check if waiting for edit input."""
        return self._waiting_for_edit_tool_call_id is not None

    def has_pending_approvals(self) -> bool:
        """Check if there are pending tool approvals waiting for response."""
        return len(self._pending) > 0

    def get_pending_approvals(self) -> list[dict[str, Any]]:
        """Get list of pending tool approvals."""
        result = []
        for tool_call_id, ctx in self._pending_context.items():
            result.append(
                {
                    "tool_call_id": tool_call_id,
                    "tool_name": ctx.tool_name,
                    "tool_args": ctx.tool_args,
                }
            )
        return result

    async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
        """Request approval for a tool call."""
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending[context.tool_call_id] = future
        self._pending_context[context.tool_call_id] = context

        # Broadcast tool call info for user to approve
        args_json = json.dumps(context.tool_args, indent=2, default=str)
        message = (
            f"🎰 Tool '{context.tool_name}'\n"
            f"Args:\n```json\n{args_json}\n```\n"
            f"❓ Approve? (y/yes = approve, n/no = deny, e/edit = edit args)"
        )
        await self.server.broadcast(message)

        try:
            return await future
        except asyncio.CancelledError:
            if context.tool_call_id in self._pending:
                del self._pending[context.tool_call_id]
            if context.tool_call_id in self._pending_context:
                del self._pending_context[context.tool_call_id]
            raise

    async def notify(
        self, message: str, context: ApprovalContext | None = None
    ) -> None:
        """Notify user (broadcast via SSE)."""
        await self.server.broadcast(message)

    def handle_response(self, response: str, tool_call_id: str | None = None) -> bool:
        """Handle a response from the user.

        Returns True if handled, False if not waiting for input.
        """
        # If we're waiting for edit input, route to edit handler
        if self._waiting_for_edit_tool_call_id:
            self._handle_edit_response(response)
            return True

        # Check if this is a pending tool call
        if tool_call_id and tool_call_id in self._pending:
            self._apply_response(tool_call_id, response)
            return True

        # If only one pending tool call, apply response to it
        if len(self._pending) == 1:
            only_tool_call_id = list(self._pending.keys())[0]
            self._apply_response(only_tool_call_id, response)
            return True

        return False

    def handle_edit_response(
        self, response: str, tool_call_id: str | None = None
    ) -> None:
        """Handle edit response (new args as JSON/YAML string)."""
        if not self._waiting_for_edit_tool_call_id:
            return

        tool_call_id = tool_call_id or self._waiting_for_edit_tool_call_id
        self._waiting_for_edit_tool_call_id = None

        if tool_call_id not in self._pending:
            return

        context = self._pending_context.get(tool_call_id)
        new_args = self._parse_edited_content(response)
        future = self._pending.pop(tool_call_id)
        del self._pending_context[tool_call_id]

        if new_args is not None:
            asyncio.create_task(
                self.server.broadcast(
                    f"✅ Tool '{context.tool_name}' approved (with edited args)"
                )
            )
            future.set_result(ApprovalResult(approved=True, override_args=new_args))
        else:
            asyncio.create_task(
                self.server.broadcast(
                    f"🛑 Tool '{context.tool_name}' denied: Invalid JSON/YAML format"
                )
            )
            future.set_result(
                ApprovalResult(approved=False, message="Invalid JSON/YAML format")
            )

    def handle_edit_response_obj(
        self, args: dict, tool_call_id: str | None = None
    ) -> None:
        """Handle edit response when args are already a dict (from JSON object message)."""
        if not self._waiting_for_edit_tool_call_id:
            return

        tool_call_id = tool_call_id or self._waiting_for_edit_tool_call_id
        self._waiting_for_edit_tool_call_id = None

        if tool_call_id not in self._pending:
            return

        context = self._pending_context.get(tool_call_id)
        future = self._pending.pop(tool_call_id)
        del self._pending_context[tool_call_id]

        # Args are already a dict, use directly
        asyncio.create_task(
            self.server.broadcast(
                f"✅ Tool '{context.tool_name}' approved (with edited args)"
            )
        )
        future.set_result(ApprovalResult(approved=True, override_args=args))

    def _handle_edit_response(self, response: str) -> None:
        """Internal handler for edit response."""
        self.handle_edit_response(response)

    def _apply_response(self, tool_call_id: str, response: str) -> None:
        """Apply response to a pending tool call."""
        if tool_call_id not in self._pending:
            return

        # Handle non-string responses (shouldn't happen, but be defensive)
        if not isinstance(response, str):
            asyncio.create_task(
                self.server.broadcast(
                    f"🛑 Unexpected response type: {type(response).__name__}"
                )
            )
            future = self._pending.pop(tool_call_id)
            del self._pending_context[tool_call_id]
            future.set_result(
                ApprovalResult(approved=False, message="Invalid response type")
            )
            return

        response_lower = response.lower().strip()
        future = self._pending.pop(tool_call_id)
        context = self._pending_context.pop(tool_call_id)

        if response_lower in ("y", "yes", "ok", "okay", ""):
            # Approve
            asyncio.create_task(
                self.server.broadcast(f"✅ Tool '{context.tool_name}' approved")
            )
            future.set_result(ApprovalResult(approved=True))
        elif response_lower in ("n", "no", "deny", "cancel"):
            # Deny
            asyncio.create_task(
                self.server.broadcast(f"🛑 Tool '{context.tool_name}' denied")
            )
            future.set_result(ApprovalResult(approved=False, message="User denied"))
        elif response_lower in ("e", "edit"):
            # Edit - DO NOT resolve future yet, just set waiting state
            # The future will be resolved when user sends JSON args
            self._pending[tool_call_id] = future
            self._pending_context[tool_call_id] = context
            self._waiting_for_edit_tool_call_id = tool_call_id

            # Broadcast current args in copy-paste friendly format
            args_json = json.dumps(context.tool_args, indent=2, ensure_ascii=False)

            # Create a curl-ready JSON payload
            message_payload = json.dumps(
                {"message": context.tool_args}, ensure_ascii=False
            )

            message = (
                f"✏️ Editing tool '{context.tool_name}'\n\n"
                f"Current args:\n```json\n{args_json}\n```\n\n"
                f"Send modified args as JSON object:\n"
                f"```\n"
                f"curl -X POST http://{self.server.host}:{self.server.port}/chat \\\n"
                f"  -H 'Content-Type: application/json' \\\n"
                f"  -d '{message_payload}'\n"
                f"```\n\n"
                f"Modify the values inside `message` as needed."
            )
            asyncio.create_task(self.server.broadcast(message))
            # DO NOT resolve future here - wait for JSON args
        else:
            # Treat as denial with reason
            asyncio.create_task(
                self.server.broadcast(
                    f"🛑 Tool '{context.tool_name}' denied: {response}"
                )
            )
            future.set_result(
                ApprovalResult(approved=False, message=f"User denied: {response}")
            )

    def _parse_edited_content(self, content: str) -> dict | None:
        """Parse edited content as JSON or YAML."""
        content = content.strip()
        # Remove markdown code blocks if present
        if content.startswith("```"):
            lines = content.split("\n")
            # Remove first and last line (code block markers)
            content = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        try:
            result = json.loads(content)
            if isinstance(result, dict):
                return result
            return None
        except json.JSONDecodeError:
            pass
        try:
            import yaml

            result = yaml.safe_load(content)
            if isinstance(result, dict):
                return result
            return None
        except yaml.YAMLError:
            pass
        return None


# =============================================================================
# SSE UI - EventDrivenUI with SSE Broadcasting
# =============================================================================


class SSEUI(EventDrivenUI):
    """SSE UI that broadcasts each event immediately with its kind."""

    def __init__(self, server: SSEServer, **kwargs):
        super().__init__(**kwargs)
        self.server = server
        self._streaming_started = False
        server.set_ui(self)

    def handle_incoming_message(self, text: str) -> None:
        self._streaming_started = False
        super().handle_incoming_message(text)

    async def print(self, text: str, kind: str = "text") -> None:
        """Broadcast each event with its kind for visual distinction."""
        if kind == "streaming":
            self._streaming_started = True
        elif kind == "text":
            if self._streaming_started:
                self._streaming_started = False
                return
        clean = remove_style(text).strip()
        if clean:
            await self.server.broadcast(clean, kind=kind)

    async def get_input(self, prompt: str) -> str:
        """Send question via SSE and wait for response."""
        if prompt:
            clean_prompt = remove_style(prompt).strip()
            if clean_prompt:
                await self.server.broadcast(f"❓ {clean_prompt}")

        self._waiting_for_input = True
        try:
            return await self._input_queue.get()
        finally:
            self._waiting_for_input = False

    async def start_event_loop(self) -> None:
        """Start the SSE server."""
        await self.server.start()
        while True:
            await asyncio.sleep(3600)


# =============================================================================
# Integration with zrb llm chat - SSE + CLI Dual Mode
# =============================================================================

server = SSEServer.get()
sse_approval = SSEApproval(server)
server.set_approval_channel(sse_approval)


def sse_ui_factory(
    ctx,
    llm_task,
    history_manager,
    ui_commands,
    initial_message,
    initial_conversation_name,
    initial_yolo,
    initial_attachments,
):
    from zrb.llm.ui.simple_ui import UIConfig

    cfg = UIConfig.default()
    if ui_commands:
        cfg = cfg.merge_commands(ui_commands)
    cfg.yolo = initial_yolo
    cfg.conversation_session_name = initial_conversation_name

    ui = SSEUI(
        ctx=ctx,
        llm_task=llm_task,
        history_manager=history_manager,
        config=cfg,
        initial_message=initial_message,
        initial_attachments=initial_attachments,
        server=server,
    )
    return ui


# Add SSE UI alongside default terminal UI (dual mode)
llm_chat.append_ui_factory(sse_ui_factory)

# Add approval channels:
# - SSE first (gets priority in race conditions)
# - Terminal second (fallback for CLI users)
llm_chat.append_approval_channel(sse_approval)

print("🌐 SSE + CLI dual mode enabled")
print("   Both terminal and SSE receive all messages.")
print("   Use terminal or POST /chat to send messages.")
print("")
print("Tool Approval:")
print("  y/yes  - Approve tool call")
print("  n/no   - Deny tool call")
print("  e/edit - Edit tool args (then send JSON/YAML)")
