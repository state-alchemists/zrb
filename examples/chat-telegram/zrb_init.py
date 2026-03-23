"""
Telegram UI - Simplified with EventDrivenUI and Buffered Output

This example shows how to create a Telegram bot UI with minimal boilerplate
using the new EventDrivenUI base class with BufferedOutputMixin for
clean message batching.

══════════════════════════════════════════════════════════════════════════════
KEY CONCEPT: EventDrivenUI + BufferedOutputMixin
══════════════════════════════════════════════════════════════════════════════

EventDrivenUI handles the queue pattern automatically:
- When ask_user() is called, it blocks on an internal queue
- When messages arrive, call handle_incoming_message() to route them

BufferedOutputMixin batches output to avoid fragmented messages:
- Output is accumulated in a buffer
- Flushed periodically (every 0.5s by default)
- Or when buffer exceeds max size

══════════════════════════════════════════════════════════════════════════════

Usage:
    export TELEGRAM_BOT_TOKEN="your-token"
    export TELEGRAM_CHAT_ID="your-chat-id"
    zrb llm chat
"""

import asyncio
import json
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, MessageHandler, filters

from zrb.builtin.llm.chat import llm_chat
from zrb.llm.app.simple_ui import (
    BufferedOutputMixin,
    EventDrivenUI,
    UIConfig,
    create_ui_factory,
)
from zrb.llm.approval import ApprovalChannel, ApprovalContext, ApprovalResult
from zrb.util.cli.style import remove_style

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


# =============================================================================
# Telegram Bot Singleton
# =============================================================================


class TelegramBot:
    """Shared bot instance - manages the telegram application."""

    _instance = None

    def __init__(self, token: str):
        self.token = token
        self._app: Application | None = None

    @classmethod
    def get(cls, token: str | None = None) -> "TelegramBot":
        if cls._instance is None:
            cls._instance = cls(token or BOT_TOKEN)
        return cls._instance

    async def start(self):
        """Initialize and start the bot."""
        self._app = Application.builder().token(self.token).build()
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling()
        return self._app

    async def send(self, chat_id: str, text: str, **kwargs):
        """Send a message (auto-splits long messages)."""
        if not self._app:
            return
        clean = remove_style(text).strip()
        if not clean:
            return
        for chunk in self._split(clean, 4000):
            await self._app.bot.send_message(chat_id=chat_id, text=chunk, **kwargs)

    @staticmethod
    def _split(text: str, max_len: int) -> list[str]:
        if len(text) <= max_len:
            return [text]
        return [text[i : i + max_len] for i in range(0, len(text), max_len)]


# =============================================================================
# Telegram UI - With buffered output for clean messages
# =============================================================================


class TelegramUI(EventDrivenUI, BufferedOutputMixin):
    """Telegram UI with buffered output for clean message batching.

    Uses:
    - EventDrivenUI: Automatic queue + event loop management
    - BufferedOutputMixin: Batches output to avoid fragmented messages
    """

    def __init__(self, bot: TelegramBot, chat_id: str, **kwargs):
        # Initialize parent classes
        super().__init__(**kwargs)
        BufferedOutputMixin.__init__(self, flush_interval=0.3, max_buffer_size=3000)
        self.bot = bot
        self.chat_id = chat_id

    async def _send_buffered(self, text: str) -> None:
        """Send buffered content to Telegram (called by BufferedOutputMixin)."""
        await self.bot.send(self.chat_id, text)

    async def print(self, text: str) -> None:
        """Buffer output (called by append_to_output during streaming)."""
        self.buffer_output(text)

    async def start_event_loop(self) -> None:
        """Start the bot and the flush loop."""
        # Start the bot (only happens once)
        if not self.bot._app:
            await self.bot.start()

        # Start the periodic flush loop
        await self.start_flush_loop()

        # Register message handler
        async def handle_message(update, context):
            """Route incoming messages to handle_incoming_message()."""
            text = update.message.text
            self.handle_incoming_message(text)

        self.bot._app.add_handler(MessageHandler(filters.TEXT, handle_message))

        # Keep running
        while True:
            await asyncio.sleep(1)


# =============================================================================
# Telegram Approval Channel - Approval via inline buttons
# =============================================================================


class TelegramApproval(ApprovalChannel):
    """Handle tool approvals via Telegram inline buttons."""

    _instances: dict[str, "TelegramApproval"] = {}

    def __init__(self, bot: TelegramBot, chat_id: str):
        self.bot = bot
        self.chat_id = chat_id
        self._pending: dict[str, asyncio.Future] = {}

    async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
        """Send approval request with inline buttons."""
        await self._ensure_handler()

        args = json.dumps(context.tool_args, indent=2, default=str)[:3000]
        text = f"🔔 Tool: `{context.tool_name}`\n```\n{args}\n```"

        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Approve", callback_data=f"yes:{context.tool_call_id}"
                ),
                InlineKeyboardButton(
                    "❌ Deny", callback_data=f"no:{context.tool_call_id}"
                ),
            ]
        ]

        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._pending[context.tool_call_id] = future

        await self.bot.send(
            self.chat_id,
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

        try:
            async with asyncio.timeout(300):
                return await future
        except asyncio.TimeoutError:
            self._pending.pop(context.tool_call_id, None)
            return ApprovalResult(approved=False, message="Timeout")

    async def notify(
        self, message: str, context: ApprovalContext | None = None
    ) -> None:
        """Send notification."""
        await self.bot.send(self.chat_id, message)

    async def _ensure_handler(self):
        """Register callback handler once."""
        if self.chat_id in TelegramApproval._instances:
            return

        TelegramApproval._instances[self.chat_id] = self

        async def handle_callback(update, context):
            query = update.callback_query
            await query.answer()
            action, tool_call_id = query.data.split(":", 1)
            approved = action == "yes"

            chat_id = str(query.message.chat_id)
            if chat_id in TelegramApproval._instances:
                TelegramApproval._instances[chat_id].resolve(tool_call_id, approved)

            await query.edit_message_text("✅ Approved" if approved else "❌ Denied")

        if self.bot._app:
            self.bot._app.add_handler(CallbackQueryHandler(handle_callback))

    def resolve(self, tool_call_id: str, approved: bool):
        """Resolve a pending approval request."""
        if tool_call_id in self._pending:
            future = self._pending.pop(tool_call_id)
            future.set_result(ApprovalResult(approved=approved))


# =============================================================================
# Integration with zrb llm chat
# =============================================================================

bot = TelegramBot.get(BOT_TOKEN)

if BOT_TOKEN and CHAT_ID:
    # Create UI factory - ONE LINE!
    llm_chat.set_ui_factory(create_ui_factory(TelegramUI, bot=bot, chat_id=CHAT_ID))

    # Set approval channel
    llm_chat.set_approval_channel(TelegramApproval(bot, CHAT_ID))

    print(f"🤖 Telegram ready for chat: {CHAT_ID}")
else:
    print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables")
