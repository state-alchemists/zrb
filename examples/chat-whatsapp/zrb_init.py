"""
WhatsApp UI Example for Zrb LLM Chat

This example demonstrates how to create a WhatsApp Business bot UI for LLM chat
using BaseUI. This is an EVENT-DRIVEN pattern where ask_user() CANNOT block.

WhatsApp Business API uses webhooks for receiving messages:
    - Twilio webhook -> your server -> route to handler
    - ask_user() puts question in queue, returns immediately
    - Webhook must respond to ack quickly

Architecture:
    ┌─────────────────┐                    ┌─────────────────┐
    │ WhatsApp Client │                    │   WhatsAppUI     │
    │   (Messages)    │                    │   (BaseUI)      │
    └────────┬────────┘                    └────────┬────────┘
             │                                      │
             │  Twilio Webhook                      │
             │ ──────────────────────────────────────>│
             │                                      │
             │                    Route to handler   │
             │                                      │
             │  Twilio API (send message)           │
             │ <─────────────────────────────────────│
             │                                      │

Key Requirements:
    - Twilio account with WhatsApp Business API
    - Public HTTPS endpoint for webhook
    - Quick webhook response (within 15 seconds)

Usage:
    # Set environment variables:
    export TWILIO_ACCOUNT_SID="your-account-sid"
    export TWILIO_AUTH_TOKEN="your-auth-token"
    export TWILIO_PHONE_NUMBER="whatsapp:+1234567890"
    export WEBHOOK_URL="https://your-domain.com/whatsapp"

    cd examples/chat-whatsapp
    zrb llm chat
"""

import asyncio
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from aiohttp import web
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

from zrb.builtin.llm.chat import llm_chat
from zrb.context.any_context import AnyContext
from zrb.llm.app.base_ui import BaseUI
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.task.llm_task import LLMTask

# =============================================================================
# Configuration
# =============================================================================

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
WILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.environ.get(
    "TWILIO_PHONE_NUMBER", ""
)  # e.g., "whatsapp:+1234567890"
WEBHOOK_URL = os.environ.get(
    "WEBHOOK_URL", ""
)  # e.g., "https://your-domain.com/whatsapp"

HTTP_HOST = os.environ.get("ZRB_HTTP_HOST", "0.0.0.0")
HTTP_PORT = int(os.environ.get("ZRB_HTTP_PORT", "8080"))


# =============================================================================
# WhatsApp Session Storage
# =============================================================================


@dataclass
class WhatsAppSession:
    """State for a single WhatsApp conversation (per phone number)."""

    phone_number: str
    ui: "WhatsAppUI" | None = None
    ask_user_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    waiting_for_response: bool = False
    current_question_id: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)


# Global session storage
_sessions: dict[str, WhatsAppSession] = {}


def get_session_key(phone_number: str) -> str:
    """Get session key from phone number."""
    # Normalize phone number
    return phone_number.replace("whatsapp:", "").strip()


# =============================================================================
# WhatsApp UI Implementation
# =============================================================================


class WhatsAppUI(BaseUI):
    """WhatsApp-based UI for LLM Chat.

    This demonstrates the EVENT-DRIVEN pattern with webhooks:

    1. Twilio sends webhook POST to your server
    2. Server routes message to correct session handler
    3. ask_user() puts question in queue, returns immediately
    4. Webhook handler must respond quickly (within 15s)

    Key challenges:
    - Must use Twilio API to send messages (not direct reply)
    - Webhooks must respond quickly
    - Need session storage for state per phone number
    - Message chunking (WhatsApp has 1600 char limit)
    """

    def __init__(
        self,
        phone_number: str,
        ctx: AnyContext,
        llm_task: LLMTask,
        history_manager: AnyHistoryManager,
        **kwargs,
    ):
        super().__init__(
            ctx=ctx,
            yolo_xcom_key=f"_yolo_wa_{phone_number}",
            assistant_name=kwargs.get("assistant_name", "ZrbBot"),
            llm_task=llm_task,
            history_manager=history_manager,
            initial_message=kwargs.get("initial_message", ""),
            initial_attachments=kwargs.get("initial_attachments", []),
            conversation_session_name=kwargs.get(
                "conversation_session_name", phone_number
            ),
            yolo=kwargs.get("yolo", False),
            exit_commands=kwargs.get("exit_commands", ["exit", "quit", "bye"]),
            info_commands=kwargs.get("info_commands", ["help", "?"]),
        )
        self.phone_number = phone_number
        self._ask_user_queue: asyncio.Queue = asyncio.Queue()
        self._waiting_for_response: bool = False
        self._current_question_id: str | None = None
        self._running = False
        self._twilio_client: Client | None = None

    def _get_twilio_client(self) -> Client:
        """Get or create Twilio client."""
        if self._twilio_client is None:
            self._twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        return self._twilio_client

    # ==========================================================================
    # REQUIRED METHODS - BaseUI implementation
    # ==========================================================================

    async def send_whatsapp_message(self, content: str):
        """Send message via Twilio WhatsApp API.

        WhatsApp has a 1600 character limit per message.
        """
        if not TWILIO_PHONE_NUMBER:
            print(f"[WhatsApp] Would send to {self.phone_number}: {content[:100]}")
            return

        # Split long messages
        max_length = 1500  # Leave room for formatting
        chunks = []
        if len(content) <= max_length:
            chunks = [content]
        else:
            # Split by newlines to avoid breaking mid-word
            lines = content.split("\n")
            current = ""
            for line in lines:
                if len(current) + len(line) + 1 > max_length:
                    if current:
                        chunks.append(current)
                    current = line
                else:
                    current += "\n" + line
            if current:
                chunks.append(current)

        # Send each chunk
        client = self._get_twilio_client()
        for chunk in chunks:
            try:
                client.messages.create(
                    from_=TWILIO_PHONE_NUMBER,
                    body=chunk,
                    to=f"whatsapp:{self.phone_number}",
                )
            except Exception as e:
                print(f"[WhatsApp] Error sending message: {e}")

    def append_to_output(self, *values, sep=" ", end="\n", file=None, flush=False):
        """Send output via WhatsApp.

        NOTE: Called from sync context, schedules async send.
        """
        content = sep.join(str(v) for v in values) + end

        # Schedule the WhatsApp send
        asyncio.create_task(self.send_whatsapp_message(content.strip()))

        # Track for result extraction
        if content.strip() and not content.startswith("\n"):
            self._last_result_data = content.rstrip("\n")

    async def ask_user(self, prompt: str) -> str:
        """Wait for user input via WhatsApp.

        EVENT-DRIVEN PATTERN:
        1. Send question via Twilio
        2. Mark ourselves as waiting
        3. Return immediately (queue-based wait)
        4. Webhook handler will put response in queue

        NOTE: Webhook must respond within 15 seconds!
        The actual user response comes later via another webhook.
        """
        # Send question
        question_text = f"❓ *Question*\n\n{prompt}\n\n_Reply with your response._"
        await self.send_whatsapp_message(question_text)

        # Mark waiting state
        self._waiting_for_response = True
        self._current_question_id = datetime.now().isoformat()

        try:
            # BLOCKING: Wait for webhook to provide response
            # This is safe because webhook runs in separate context
            response = await self._ask_user_queue.get()
            return response
        finally:
            self._waiting_for_response = False
            self._current_question_id = None

    async def run_interactive_command(self, cmd: str | list[str], shell: bool = False):
        """Shell commands not supported in WhatsApp mode."""
        await self.send_whatsapp_message(
            "⚠️ Shell commands not supported in WhatsApp mode."
        )
        return 1

    async def run_async(self) -> str:
        """Run the WhatsApp UI event loop.

        Simple: Start message processing, initial message.
        Webhook handles everything else.
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
        asyncio.create_task(
            self.send_whatsapp_message("👋 Conversation ended. Goodbye!")
        )

    # ==========================================================================
    # WhatsApp-specific methods
    # ==========================================================================

    async def provide_ask_user_response(self, response: str):
        """Called from webhook when user responds to ask_user."""
        await self._ask_user_queue.put(response)

    def is_waiting_for_response(self) -> bool:
        """Check if waiting for ask_user response."""
        return self._waiting_for_response


# =============================================================================
# Webhook Handler (aiohttp)
# =============================================================================


async def handle_whatsapp_webhook(request: web.Request) -> web.Response:
    """Handle incoming WhatsApp webhook from Twilio.

    Twilio expects a quick response (within 15 seconds).
    We process the message asynchronously.
    """
    try:
        # Parse Twilio webhook data
        data = await request.post()

        from_number = data.get("From", "")  # e.g., "whatsapp:+1234567890"
        message_body = data.get("Body", "")

        # Normalize phone number
        phone_number = from_number.replace("whatsapp:", "").strip()

        if not phone_number or not message_body:
            return web.Response(text="", status=400)

        # Get or create session
        session_key = get_session_key(phone_number)
        if session_key not in _sessions:
            _sessions[session_key] = WhatsAppSession(phone_number=phone_number)

        session = _sessions[session_key]
        session.last_activity = datetime.now()

        # Route message
        message_lower = message_body.lower().strip()

        # Check if response to ask_user
        if session.ui and session.ui.is_waiting_for_response():
            # This is a response to a pending question
            asyncio.create_task(session.ui.provide_ask_user_response(message_body))
        elif session.ui:
            # Regular message - submit to LLM
            session.ui._submit_user_message(session.ui._llm_task, message_body)

        # Respond to Twilio quickly
        response = MessagingResponse()
        response.message("")  # Empty response - we send messages via API
        return web.Response(text=str(response), content_type="application/xml")

    except Exception as e:
        print(f"[WhatsApp] Webhook error: {e}")
        response = MessagingResponse()
        response.message("An error occurred. Please try again.")
        return web.Response(text=str(response), content_type="application/xml")


async def handle_whatsapp_status(request: web.Request) -> web.Response:
    """Handle WhatsApp delivery status webhooks."""
    # We don't need to process status callbacks
    return web.Response(text="", status=200)


# =============================================================================
# HTTP Server Setup
# =============================================================================


def create_app() -> web.Application:
    """Create the aiohttp application for webhook handling."""
    app = web.Application()

    # Twilio webhook endpoints
    app.router.add_post("/whatsapp", handle_whatsapp_webhook)
    app.router.add_post("/whatsapp/status", handle_whatsapp_status)

    # Health check
    async def health(request):
        return web.json_response({"status": "ok"})

    app.router.add_get("/health", health)

    return app


async def run_webhook_server():
    """Run the webhook HTTP server."""
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, HTTP_HOST, HTTP_PORT)

    print(f"WhatsApp webhook server starting on http://{HTTP_HOST}:{HTTP_PORT}")
    print("\nEndpoints:")
    print(f"  POST   http://{HTTP_HOST}:{HTTP_PORT}/whatsapp")
    print(f"  POST   http://{HTTP_HOST}:{HTTP_PORT}/whatsapp/status")
    print(f"  GET    http://{HTTP_HOST}:{HTTP_PORT}/health")
    print("\nConfigure Twilio webhook URL:")
    print(f"  {WEBHOOK_URL}/whatsapp")
    print("\nNote: You may need to use ngrok or similar for local testing:")
    print("  ngrok http 8080")
    print("  Then set WEBHOOK_URL to the ngrok URL")

    await site.start()
    await asyncio.Future()  # Run forever


# =============================================================================
# Running the Server
# =============================================================================

if __name__ == "__main__":
    # Validate configuration
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        print("Error: TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN must be set.")
        print("Get your credentials from: https://www.twilio.com/console")
        print("export TWILIO_ACCOUNT_SID='your-sid'")
        print("export TWILIO_AUTH_TOKEN='your-token'")
        exit(1)

    asyncio.run(run_webhook_server())


# =============================================================================
# Integration with zrb llm chat
# =============================================================================

"""
To integrate with zrb llm chat:

1. Create UI factory for WhatsApp:

def create_whatsapp_ui(phone_number: str, ctx, llm_task_core, history_manager, ...):
    return WhatsAppUI(
        phone_number=phone_number,
        ctx=ctx,
        llm_task=llm_task_core,
        history_manager=history_manager,
        ...
    )

2. Initialize session on first message:

async def handle_whatsapp_webhook(request):
    session_key = get_session_key(phone_number)
    
    if session_key not in _sessions:
        # Create new session
        ui = create_whatsapp_ui(phone_number, ...)
        _sessions[session_key] = WhatsAppState(
            phone_number=phone_number,
            ui=ui,
        )
        asyncio.create_task(ui.run_async())
    
    # Route message
    ...

3. For testing locally, use ngrok:

ngrok http 8080
# Set WEBHOOK_URL to https://your-ngrok-url.ngrok.io
# Configure Twilio webhook to: https://your-ngrok-url.ngrok.io/whatsapp
"""
