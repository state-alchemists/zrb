"""
WhatsApp UI for Zrb LLM Chat

This example extends `llm_chat` to work on WhatsApp via Twilio.
Set environment variables, then run `zrb llm chat`.

Pattern: Event-Driven Webhook (ask_user uses queue)

IMPORTANT: WhatsApp uses webhooks. You need to:
1. Start a webhook server (this module does it automatically)
2. Configure Twilio webhook URL to point to your server
3. Use ngrok for local testing: ngrok http 8080

Usage:
    export TWILIO_ACCOUNT_SID="your-sid"
    export TWILIO_AUTH_TOKEN="your-token"
    export TWILIO_PHONE_NUMBER="whatsapp:+14155238886"
    export TWILIO_WEBHOOK_PORT="8080"  # Optional, default 8080

    # Terminal 1: Start ngrok
    ngrok http 8080

    # Terminal 2: Run llm chat
    zrb llm chat
"""

import asyncio
import json
import os

from aiohttp import web
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

from zrb.builtin.llm.chat import llm_chat
from zrb.llm.app.base_ui import BaseUI
from zrb.llm.approval import ApprovalChannel, ApprovalContext, ApprovalResult
from zrb.util.cli.style import remove_style

TWILIO_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE = os.environ.get("TWILIO_PHONE_NUMBER")
WEBHOOK_PORT = int(os.environ.get("TWILIO_WEBHOOK_PORT", "8080"))

# Sessions for routing messages - keyed by phone number
_sessions: dict[str, "WhatsAppUI"] = {}
# Pending approvals - keyed by phone_number, value is dict of tool_call_id -> future
_pending_approvals: dict[str, dict[str, asyncio.Future]] = {}
# Waiting for approval response - keyed by phone_number, value is tool_call_id
_waiting_for_approval: dict[str, str] = {}


# ─────────────────────────────────────────────────────────────────────────────
# WhatsApp Client - Buffered sending with approval support
# ─────────────────────────────────────────────────────────────────────────────


class WhatsAppClient:
    """Twilio client with buffered output and approval tracking."""

    def __init__(self, phone: str, flush_interval: float = 1.0):
        self.phone = phone
        self.flush_interval = flush_interval
        self.client = Client(TWILIO_SID, TWILIO_TOKEN) if TWILIO_SID else None
        self._buffer: list[str] = []
        self._flush_task: asyncio.Task | None = None

    async def start(self):
        """Start flush loop."""
        if self._flush_task is None:
            self._flush_task = asyncio.create_task(self._flush_loop())

    async def _flush_loop(self):
        """Periodically flush buffer."""
        while True:
            await asyncio.sleep(self.flush_interval)
            if self._buffer:
                await self._flush_buffer()

    async def _flush_buffer(self):
        """Send all buffered content via Twilio."""
        if not self._buffer or not self.client or not TWILIO_PHONE:
            self._buffer = []
            return

        content = "\n".join(self._buffer)
        self._buffer = []

        if not content.strip():
            return

        try:
            self.client.messages.create(
                from_=TWILIO_PHONE, body=content[:1500], to=f"whatsapp:{self.phone}"
            )
        except Exception as e:
            print(f"Send error: {e}")

    def send(self, text: str):
        """Buffer text for sending."""
        clean = remove_style(text).strip()
        if clean:
            self._buffer.append(clean)
            # Flush when large
            if len(self._buffer) > 30 or sum(len(s) for s in self._buffer) > 800:
                asyncio.create_task(self._flush_buffer())

    async def send_now(self, text: str):
        """Send immediately."""
        if not self.client or not TWILIO_PHONE:
            print(f"[WhatsApp:{self.phone}] {text[:50]}...")
            return
        clean = remove_style(text).strip()
        if not clean:
            return
        try:
            self.client.messages.create(
                from_=TWILIO_PHONE, body=clean[:1500], to=f"whatsapp:{self.phone}"
            )
        except Exception as e:
            print(f"Send error: {e}")

    async def send_approval_request(
        self, text: str, tool_call_id: str, future: asyncio.Future
    ):
        """Send approval request and track it."""
        # Register the pending approval
        if self.phone not in _pending_approvals:
            _pending_approvals[self.phone] = {}
        _pending_approvals[self.phone][tool_call_id] = future
        _waiting_for_approval[self.phone] = tool_call_id

        await self.send_now(text)

    async def flush(self):
        """Manually flush buffer."""
        if self._buffer:
            await self._flush_buffer()


# ─────────────────────────────────────────────────────────────────────────────
# WhatsApp UI - Buffered output
# ─────────────────────────────────────────────────────────────────────────────


class WhatsAppUI(BaseUI):
    """WhatsApp UI with buffered output for cleaner messages."""

    def __init__(self, client: WhatsAppClient, **kwargs):
        super().__init__(**kwargs)
        self.client = client
        self.input_queue: asyncio.Queue = asyncio.Queue()
        self.waiting = False

    # Required: Buffer output
    def append_to_output(self, *values, sep=" ", end="\n", **kwargs):
        content = remove_style(sep.join(str(v) for v in values) + end)
        self.client.send(content)

    # Required: Ask user (via queue)
    async def ask_user(self, prompt: str) -> str:
        await self.client.flush()
        await self.client.send_now(f"❓ {prompt}\n\n_Reply with your response._")
        self.waiting = True
        try:
            return await self.input_queue.get()
        finally:
            self.waiting = False

    # Required: Shell disabled
    async def run_interactive_command(self, cmd, shell=False):
        await self.client.send_now("⚠️ Shell disabled")
        return 1

    # Required: Run event loop
    async def run_async(self) -> str:
        await self.client.start()

        # Register this session
        _sessions[self.client.phone] = self

        self._process_messages_task = asyncio.create_task(self._process_messages_loop())
        if self._initial_message:
            self._submit_user_message(self._llm_task, self._initial_message)

        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            self._process_messages_task.cancel()
            _sessions.pop(self.client.phone, None)
        return ""

    async def respond(self, text: str):
        """Provide response for ask_user (called by webhook)."""
        await self.input_queue.put(text)

    def chat(self, text: str):
        """Submit chat message (called by webhook)."""
        self._submit_user_message(self._llm_task, text)


# ─────────────────────────────────────────────────────────────────────────────
# WhatsApp Approval Channel - Uses message replies
# ─────────────────────────────────────────────────────────────────────────────


class WhatsAppApprovalChannel(ApprovalChannel):
    """Approval via WhatsApp message reply (yes/no)."""

    def __init__(self, client: WhatsAppClient):
        self.client = client

    async def request_approval(self, ctx: ApprovalContext) -> ApprovalResult:
        await self.client.flush()

        # Format the approval request
        args_str = json.dumps(ctx.tool_args, indent=2, default=str)[:800]
        message = (
            f"🔔 *Tool:* `{ctx.tool_name}`\n"
            f"```\n{args_str}\n```\n"
            f"_Reply with 'yes' to approve or 'no' to deny._"
        )

        # Create future for this approval
        loop = asyncio.get_event_loop()
        future = loop.create_future()

        # Register pending approval
        if self.client.phone not in _pending_approvals:
            _pending_approvals[self.client.phone] = {}
        _pending_approvals[self.client.phone][ctx.tool_call_id] = future
        _waiting_for_approval[self.client.phone] = ctx.tool_call_id

        # Send approval request
        await self.client.send_now(message)

        # Wait for response (with timeout)
        try:
            async with asyncio.timeout(300):
                return await future
        except asyncio.TimeoutError:
            # Clean up on timeout
            _pending_approvals.get(self.client.phone, {}).pop(ctx.tool_call_id, None)
            if _waiting_for_approval.get(self.client.phone) == ctx.tool_call_id:
                _waiting_for_approval.pop(self.client.phone, None)
            return ApprovalResult(
                approved=False, message="Timeout waiting for approval"
            )

    async def notify(self, msg: str, ctx=None):
        await self.client.send_now(f"📢 {msg}")


# ─────────────────────────────────────────────────────────────────────────────
# Webhook Handler - Routes messages and approval responses
# ─────────────────────────────────────────────────────────────────────────────


async def handle_whatsapp(request: web.Request) -> web.Response:
    """Handle Twilio webhook - routes messages and approval responses."""
    data = await request.post()

    from_number = data.get("From", "").replace("whatsapp:", "")
    message_body = data.get("Body", "").strip().lower()

    if not from_number or not message_body:
        return web.Response(text="", status=400)

    # Check if this is a response to an approval request
    if from_number in _waiting_for_approval:
        tool_call_id = _waiting_for_approval[from_number]
        if message_body in ("yes", "y", "approve", "1"):
            # Approved
            if (
                from_number in _pending_approvals
                and tool_call_id in _pending_approvals[from_number]
            ):
                _pending_approvals[from_number].pop(tool_call_id).set_result(
                    ApprovalResult(approved=True)
                )
            _waiting_for_approval.pop(from_number, None)
            return web.Response(
                text=str(MessagingResponse()), content_type="application/xml"
            )
        elif message_body in ("no", "n", "deny", "0"):
            # Denied
            if (
                from_number in _pending_approvals
                and tool_call_id in _pending_approvals[from_number]
            ):
                _pending_approvals[from_number].pop(tool_call_id).set_result(
                    ApprovalResult(approved=False)
                )
            _waiting_for_approval.pop(from_number, None)
            return web.Response(
                text=str(MessagingResponse()), content_type="application/xml"
            )

    # Not an approval response, check for regular chat
    ui = _sessions.get(from_number)

    if ui:
        if ui.waiting:
            # Response to ask_user
            asyncio.create_task(ui.respond(message_body))
        else:
            # Regular chat message
            ui.chat(message_body)

    return web.Response(text=str(MessagingResponse()), content_type="application/xml")


# ─────────────────────────────────────────────────────────────────────────────
# Webhook Server
# ─────────────────────────────────────────────────────────────────────────────

_webhook_server = None


async def start_webhook_server():
    """Start webhook server in background."""
    global _webhook_server
    if _webhook_server:
        return

    app = web.Application()
    app.router.add_post("/whatsapp", handle_whatsapp)

    runner = web.AppRunner(app)
    await runner.setup()
    _webhook_server = web.TCPSite(runner, "0.0.0.0", WEBHOOK_PORT)
    await _webhook_server.start()
    print(f"🤖 WhatsApp webhook server: http://localhost:{WEBHOOK_PORT}/whatsapp")


# ─────────────────────────────────────────────────────────────────────────────
# Integrate with zrb llm chat
# ─────────────────────────────────────────────────────────────────────────────

if TWILIO_SID and TWILIO_TOKEN:

    def create_ui(
        ctx,
        llm_task_core,
        history_manager,
        ui_commands,
        initial_message,
        initial_conversation_name,
        initial_yolo,
        initial_attachments,
    ):
        asyncio.create_task(start_webhook_server())

        # In production, you'd pass the actual phone number from the webhook
        # For now, we use a placeholder that can be overridden
        phone = getattr(ctx, "_whatsapp_phone", None) or "+1234567890"
        client = WhatsAppClient(phone)

        return WhatsAppUI(
            client=client,
            ctx=ctx,
            yolo_xcom_key="yolo",
            assistant_name="ZrbBot",
            llm_task=llm_task_core,
            history_manager=history_manager,
            initial_message=initial_message,
            conversation_session_name=initial_conversation_name,
            yolo=initial_yolo,
            initial_attachments=initial_attachments,
            exit_commands=ui_commands.get("exit", ["/exit"]),
            info_commands=ui_commands.get("info", ["/help"]),
        )

    # Global approval channel that delegates to sessions
    class WhatsAppGlobalApprovalChannel(ApprovalChannel):
        """Approval channel that routes to the correct WhatsApp session."""

        async def request_approval(self, ctx: ApprovalContext) -> ApprovalResult:
            # Find the most recently active session
            # In a production system, you'd track which session initiated the tool call
            # For now, we use the last session that received a message
            if not _sessions:
                return ApprovalResult(
                    approved=False, message="No active WhatsApp session"
                )

            # Get the last active session (most recent message)
            # This works because _sessions is keyed by phone number
            # and the webhook updates _sessions when a message arrives
            last_phone = list(_sessions.keys())[-1]
            ui = _sessions[last_phone]

            # Create a per-session approval channel and delegate
            approval_channel = WhatsAppApprovalChannel(ui.client)
            return await approval_channel.request_approval(ctx)

        async def notify(self, msg: str, ctx=None):
            # Broadcast to all active sessions
            for ui in _sessions.values():
                await ui.client.send_now(f"📢 {msg}")

    llm_chat.set_ui_factory(create_ui)
    llm_chat.set_approval_channel(WhatsAppGlobalApprovalChannel())
    print("🤖 WhatsApp webhook configured")
    print(f"   Configure Twilio webhook: http://your-server:{WEBHOOK_PORT}/whatsapp")
    print("   Tool approvals: Reply 'yes' or 'no'")
else:
    print("Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN")
    print("Get credentials: https://twilio.com/console")
