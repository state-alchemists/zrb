"""
Telegram UI/Approval Example - Minimal Implementation

Pattern: Event-Driven (ask_user uses queue, messages routed by handler)

Usage:
    export TELEGRAM_BOT_TOKEN="your-token"
    export TELEGRAM_CHAT_ID="your-chat-id"
    zrb llm chat
"""

import asyncio
import json
import os

from zrb.builtin.llm.chat import llm_chat
from zrb.llm.app.base_ui import BaseUI
from zrb.llm.approval import ApprovalChannel, ApprovalContext, ApprovalResult
from zrb.util.cli.style import remove_style

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# ─────────────────────────────────────────────────────────────────────────────
# Shared Telegram Bot - Singleton for UI and Approval
# ─────────────────────────────────────────────────────────────────────────────


class TelegramBot:
    """Shared Telegram bot instance - singleton pattern."""

    _instance = None

    def __init__(self, token: str):
        self.token = token
        self._bot = None
        self._app = None

    @classmethod
    def get(cls, token: str = None) -> "TelegramBot":
        if cls._instance is None:
            cls._instance = cls(token or BOT_TOKEN)
        return cls._instance

    async def bot(self):
        if self._bot:
            return self._bot
        try:
            from telegram.ext import Application

            self._app = Application.builder().token(self.token).build()
            await self._app.initialize()
            await self._app.start()
            await self._app.updater.start_polling()
            self._bot = self._app.bot
            return self._bot
        except Exception as e:
            print(f"Warning: Failed to start Telegram bot: {e}")
            self._app = None
            self._bot = None
            raise

    async def send(self, chat_id: str, text: str, **kwargs):
        bot = await self.bot()
        clean = remove_style(text).strip()
        if not clean:
            return
        # Split long messages
        for chunk in self._split(clean, 4000):
            await bot.send_message(chat_id=chat_id, text=chunk, **kwargs)

    async def shutdown(self):
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()

    @staticmethod
    def _split(text: str, max_len: int) -> list[str]:
        if len(text) <= max_len:
            return [text]
        return [text[i : i + max_len] for i in range(0, len(text), max_len)]


# ─────────────────────────────────────────────────────────────────────────────
# Telegram UI - Buffered output for cleaner messages
# ─────────────────────────────────────────────────────────────────────────────


class TelegramUI(BaseUI):
    """Telegram UI with buffered output - batches tokens into fewer messages."""

    def __init__(self, bot: TelegramBot, chat_id: str, **kwargs):
        super().__init__(**kwargs)
        self.bot = bot
        self.chat_id = chat_id
        self.input_queue: asyncio.Queue = asyncio.Queue()
        self.waiting = False
        self._handler_added = False
        # Output buffering
        self._buffer: list[str] = []
        self._flush_task: asyncio.Task | None = None
        self._last_flush_len = 0

    # Required: Buffer output, flush periodically
    def append_to_output(self, *values, sep=" ", end="\n", **kwargs):
        content = sep.join(str(v) for v in values) + end
        self._buffer.append(content)
        # Flush when buffer gets large enough
        if len(self._buffer) > 50 or sum(len(s) for s in self._buffer) > 1000:
            asyncio.create_task(self._flush_buffer())

    async def _flush_buffer(self):
        """Send buffered output to Telegram."""
        if not self._buffer:
            return
        content = "".join(self._buffer).strip()
        self._buffer = []
        if content:
            await self.bot.send(self.chat_id, content)

    async def _flush_loop(self):
        """Periodically flush buffer."""
        while True:
            await asyncio.sleep(0.5)  # Flush every 0.5 seconds
            if self._buffer:
                await self._flush_buffer()

    # Required: Send question, wait on queue
    async def ask_user(self, prompt: str) -> str:
        # Flush any pending output first
        if self._buffer:
            await self._flush_buffer()
        await self.bot.send(self.chat_id, f"❓ {prompt}")
        self.waiting = True
        try:
            return await self.input_queue.get()
        finally:
            self.waiting = False

    # Required: Shell disabled
    async def run_interactive_command(self, cmd, shell=False):
        await self.bot.send(self.chat_id, "⚠️ Shell disabled")
        return 1

    # Required: Run the bot
    async def run_async(self) -> str:
        from telegram.ext import MessageHandler, filters

        await self.bot.bot()

        if not self._handler_added and self.bot._app:

            async def handle(update, context):
                text = update.message.text
                if self.waiting:
                    await self.input_queue.put(text)
                else:
                    self._submit_user_message(self._llm_task, text)

            self.bot._app.add_handler(MessageHandler(filters.TEXT, handle))
            self._handler_added = True

        # Start flush loop
        self._flush_task = asyncio.create_task(self._flush_loop())

        # Start processing
        self._process_messages_task = asyncio.create_task(self._process_messages_loop())
        if self._initial_message:
            self._submit_user_message(self._llm_task, self._initial_message)

        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            # Final flush
            if self._buffer:
                await self._flush_buffer()
            self._flush_task.cancel()
            self._process_messages_task.cancel()
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# Telegram Approval Channel
# ─────────────────────────────────────────────────────────────────────────────


class TelegramApproval(ApprovalChannel):
    """Approval via inline buttons."""

    def __init__(self, bot: TelegramBot, chat_id: str):
        self.bot = bot
        self.chat_id = chat_id
        self._pending: dict[str, asyncio.Future] = {}

    async def request_approval(self, ctx: ApprovalContext) -> ApprovalResult:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        args = json.dumps(ctx.tool_args, indent=2, default=str)[:3000]
        text = f"🔔 Tool: `{ctx.tool_name}`\n```\n{args}\n```"

        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Approve", callback_data=f"yes:{ctx.tool_call_id}"
                ),
                InlineKeyboardButton("❌ Deny", callback_data=f"no:{ctx.tool_call_id}"),
            ]
        ]

        future = asyncio.get_event_loop().create_future()
        self._pending[ctx.tool_call_id] = future

        await self.bot.send(
            self.chat_id,
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

        return await future

    async def notify(self, msg: str, ctx=None):
        await self.bot.send(self.chat_id, msg)

    def handle_callback(self, tool_call_id: str, approved: bool):
        if tool_call_id in self._pending:
            self._pending.pop(tool_call_id).set_result(
                ApprovalResult(approved=approved)
            )


# ─────────────────────────────────────────────────────────────────────────────
# Integrate with zrb llm chat
# ─────────────────────────────────────────────────────────────────────────────

if BOT_TOKEN and CHAT_ID:
    telegram_bot = TelegramBot.get(BOT_TOKEN)

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
        return TelegramUI(
            bot=telegram_bot,
            chat_id=CHAT_ID,
            ctx=ctx,
            yolo_xcom_key="yolo",
            assistant_name="Bot",
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
    llm_chat.set_approval_channel(TelegramApproval(telegram_bot, CHAT_ID))
    print(f"🤖 Telegram ready for chat: {CHAT_ID}")
else:
    print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
