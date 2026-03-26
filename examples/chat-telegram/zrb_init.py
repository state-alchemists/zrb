"""
Telegram + CLI Chat - Unified Example

This example supports THREE modes based on environment variables:

1. CLI only (default):
   - Just run `zrb llm chat`

2. Telegram only:
   - Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
   - Interactive=False to disable terminal UI

3. CLI + Telegram (dual):
   - Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
   - Use MultiUI to broadcast to both channels
   - Use MultiplexApprovalChannel for approvals from both

Usage:
    # CLI only
    zrb llm chat

    # Telegram only
    export TELEGRAM_BOT_TOKEN="your-token"
    export TELEGRAM_CHAT_ID="your-chat-id"
    zrb llm chat

    # CLI + Telegram
    export TELEGRAM_BOT_TOKEN="your-token"
    export TELEGRAM_CHAT_ID="your-chat-id"
    # Note: Default terminal UI + Telegram UI will both receive messages
"""

import asyncio
import json
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from zrb.builtin.llm.chat import llm_chat
from zrb.llm.approval import (
    ApprovalChannel,
    ApprovalContext,
    ApprovalResult,
    MultiplexApprovalChannel,
)
from zrb.llm.ui.simple_ui import (
    BufferedOutputMixin,
    EventDrivenUI,
    create_ui_factory,
)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


# =============================================================================
# Telegram Bot
# =============================================================================


class TelegramBot:
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
        self._app = Application.builder().token(self.token).build()
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling()
        return self._app

    async def send(self, chat_id: str, text: str, **kwargs):
        if not self._app:
            return
        from zrb.util.cli.style import remove_style

        clean = remove_style(text).strip()
        if not clean:
            return
        for chunk in _split(clean, 4000):
            await self._app.bot.send_message(chat_id=chat_id, text=chunk, **kwargs)

    async def stop(self):
        if self._app:
            try:
                await asyncio.wait_for(self._app.stop(), timeout=1.0)
            except Exception:
                pass


def _split(text: str, max_len: int) -> list[str]:
    if len(text) <= max_len:
        return [text]
    return [text[i : i + max_len] for i in range(0, len(text), max_len)]


# =============================================================================
# Telegram UI
# =============================================================================


class TelegramUI(EventDrivenUI, BufferedOutputMixin):
    def __init__(self, bot: TelegramBot, chat_id: str, **kwargs):
        super().__init__(**kwargs)
        BufferedOutputMixin.__init__(self, flush_interval=0.3, max_buffer_size=3000)
        self.bot = bot
        self.chat_id = chat_id

    async def _send_buffered(self, text: str) -> None:
        await self.bot.send(self.chat_id, text)

    async def print(self, text: str) -> None:
        self.buffer_output(text)

    async def start_event_loop(self) -> None:
        if not self.bot._app:
            await self.bot.start()

        await self.start_flush_loop()

        async def handle_message(update, context):
            text = update.message.text
            self.handle_incoming_message(text)

        self.bot._app.add_handler(MessageHandler(filters.TEXT, handle_message))

        while True:
            await asyncio.sleep(1)


# =============================================================================
# Telegram Approval Channel
# =============================================================================


class TelegramApproval(ApprovalChannel):
    _instances: dict[str, "TelegramApproval"] = {}

    def __init__(self, bot: TelegramBot, chat_id: str):
        self.bot = bot
        self.chat_id = chat_id
        self._pending: dict[str, asyncio.Future] = {}

    async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
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
        await self.bot.send(self.chat_id, message)

    async def _ensure_handler(self):
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
        if tool_call_id in self._pending:
            future = self._pending.pop(tool_call_id)
            future.set_result(ApprovalResult(approved=approved))


# =============================================================================
# Integration
# =============================================================================

bot = TelegramBot.get(BOT_TOKEN)

if BOT_TOKEN and CHAT_ID:
    # Telegram + CLI mode (dual channel)
    llm_chat.append_ui_factory(create_ui_factory(TelegramUI, bot=bot, chat_id=CHAT_ID))
    llm_chat.append_approval_channel(TelegramApproval(bot, CHAT_ID))
    # Note: Terminal approval is handled by the default UI (BaseUI._confirm_tool_execution)

    print(f"🤖 Telegram + CLI dual mode for chat ID: {CHAT_ID}")
    print("   Both channels receive all messages.")
    print("   Approvals work from both - first response wins!")

elif BOT_TOKEN or CHAT_ID:
    print("⚠️  Set both TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")

else:
    # CLI only (no telegram env vars) - this shouldn't happen for this example
    pass
