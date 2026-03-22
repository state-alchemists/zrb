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

    # Terminal 1: Start webhook server + ngrok
    ngrok http 8080

    # Terminal 2: Run llm chat
    zrb llm chat
"""

import asyncio
import os

from aiohttp import web
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

from zrb.builtin.llm.chat import llm_chat
from zrb.llm.app.base_ui import BaseUI
from zrb.util.cli.style import remove_style

TWILIO_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE = os.environ.get("TWILIO_PHONE_NUMBER")
WEBHOOK_PORT = int(os.environ.get("TWILIO_WEBHOOK_PORT", "8080"))

# Sessions for routing messages
_sessions: dict[str, "WhatsAppUI"] = {}


# ─────────────────────────────────────────────────────────────────────────────
# WhatsApp Client - Buffered sending
# ─────────────────────────────────────────────────────────────────────────────


class WhatsAppClient:
    """Twilio client with buffered output."""

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
# Webhook Handler
# ─────────────────────────────────────────────────────────────────────────────


async def handle_whatsapp(request):
    """Handle Twilio webhook."""
    data = await request.post()

    from_number = data.get("From", "").replace("whatsapp:", "")
    message_body = data.get("Body", "")

    if not from_number or not message_body:
        return web.Response(text="", status=400)

    ui = _sessions.get(from_number)

    if ui:
        if ui.waiting:
            asyncio.create_task(ui.respond(message_body))
        else:
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

    llm_chat.set_ui_factory(create_ui)
    print(f"🤖 WhatsApp webhook configured")
    print(f"   Configure Twilio webhook: http://your-server:{WEBHOOK_PORT}/whatsapp")
else:
    print("Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN")
    print("Get credentials: https://twilio.com/console")
