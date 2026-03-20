"""
Telegram Bot Example for Zrb LLM

This example shows how to run LLMChatTask on Telegram with both
UI and approval channel routed through Telegram.

Requirements:
    - python-telegram-bot>=20.0
    - Set environment variables: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""

import asyncio
import json
import os
from typing import Any

from zrb import LLMChatTask
from zrb.llm.approval import ApprovalChannel, ApprovalContext, ApprovalResult
from zrb.llm.tool_call.ui_protocol import UIProtocol

# =============================================================================
# Telegram UI Implementation
# =============================================================================


class TelegramUI(UIProtocol):
    """UIProtocol implementation for Telegram - handles user interaction."""

    def __init__(self, bot_token: str, chat_id: str, timeout: int = 300):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.timeout = timeout
        self._bot = None
        self._application = None
        self._pending: dict[str, asyncio.Future[str]] = {}
        self._buffer: list[str] = []

    async def _ensure_bot(self):
        """Lazy initialization of Telegram bot."""
        if self._bot:
            return
        from telegram.ext import Application, MessageHandler, filters

        self._application = Application.builder().token(self.bot_token).build()
        self._application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )
        await self._application.initialize()
        await self._application.start()
        await self._application.updater.start_polling()
        self._bot = self._application.bot

    async def _handle_message(self, update, context):
        """Handle incoming text messages."""
        text = update.message.text
        # Route message to pending question
        for qid, future in list(self._pending.items()):
            if not future.done():
                future.set_result(text)
                self._pending.pop(qid, None)
                return

    async def ask_user(self, prompt: str) -> str:
        """Send a question to Telegram and wait for response."""
        await self._ensure_bot()
        await self._bot.send_message(chat_id=self.chat_id, text=f"❓ {prompt}")

        loop = asyncio.get_event_loop()
        future: asyncio.Future[str] = loop.create_future()
        self._pending[f"q_{id(future)}"] = future

        try:
            async with asyncio.timeout(self.timeout):
                return await future
        except asyncio.TimeoutError:
            self._pending.clear()
            await self._bot.send_message(chat_id=self.chat_id, text="⏰ Timed out")
            return ""

    def append_to_output(
        self, *values, sep: str = " ", end: str = "\n", file=None, flush: bool = False
    ):
        """Buffer output for later sending."""
        self._buffer.append(sep.join(str(v) for v in values) + end)

    def stream_to_parent(
        self, *values, sep: str = " ", end: str = "\n", file=None, flush: bool = False
    ):
        """Send output immediately to Telegram."""
        msg = sep.join(str(v) for v in values) + end
        asyncio.create_task(self._send(msg))

    async def _send(self, msg: str):
        """Send message to Telegram (with truncation for long messages)."""
        await self._ensure_bot()
        if len(msg) > 4000:
            msg = msg[:3997] + "..."
        await self._bot.send_message(chat_id=self.chat_id, text=msg)

    async def flush_output(self):
        """Send all buffered output."""
        if self._buffer:
            msg = "".join(self._buffer)
            self._buffer = []
            await self._send(msg)

    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
        """Run shell commands - disabled for security on Telegram."""
        await self._send(f"⚠️ Command execution disabled from Telegram")
        return {"error": "Command execution disabled"}

    async def shutdown(self):
        """Clean shutdown of the bot."""
        if self._application:
            await self._application.updater.stop()
            await self._application.stop()
            await self._application.shutdown()


# =============================================================================
# Telegram Approval Channel Implementation
# =============================================================================


class TelegramApprovalChannel(ApprovalChannel):
    """ApprovalChannel implementation for Telegram - handles tool confirmations."""

    def __init__(self, bot_token: str, chat_id: str, timeout: int = 300):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.timeout = timeout
        self._bot = None
        self._application = None
        self._pending: dict[str, asyncio.Future[ApprovalResult]] = {}

    async def _ensure_bot(self):
        """Lazy initialization of Telegram bot."""
        if self._bot:
            return
        from telegram.ext import Application, CallbackQueryHandler

        self._application = Application.builder().token(self.bot_token).build()
        self._application.add_handler(CallbackQueryHandler(self._handle_callback))
        await self._application.initialize()
        await self._application.start()
        await self._application.updater.start_polling()
        self._bot = self._application.bot

    async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
        """Send approval request with inline Approve/Deny buttons."""
        await self._ensure_bot()
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        text = self._format_message(context)
        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Approve", callback_data=f"approve:{context.tool_call_id}"
                ),
                InlineKeyboardButton(
                    "❌ Deny", callback_data=f"deny:{context.tool_call_id}"
                ),
            ]
        ]

        loop = asyncio.get_event_loop()
        future: asyncio.Future[ApprovalResult] = loop.create_future()
        self._pending[context.tool_call_id] = future

        try:
            await self._bot.send_message(
                chat_id=self.chat_id,
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )
            async with asyncio.timeout(self.timeout):
                return await future
        except asyncio.TimeoutError:
            self._pending.pop(context.tool_call_id, None)
            return ApprovalResult(approved=False, message="Timeout")

    async def _handle_callback(self, update, context):
        """Handle inline button press."""
        query = update.callback_query
        await query.answer()

        action, tool_call_id = query.data.split(":", 1)
        if tool_call_id not in self._pending:
            await query.edit_message_text("⚠️ Expired or invalid request")
            return

        approved = action == "approve"
        result = ApprovalResult(approved=approved)
        self._pending.pop(tool_call_id).set_result(result)

        emoji = "✅ Approved" if approved else "❌ Denied"
        await query.edit_message_text(
            f"{emoji}\n\nTool: `{tool_call_id}`", parse_mode="Markdown"
        )

    def _format_message(self, ctx: ApprovalContext) -> str:
        """Format the approval request message."""
        args_str = json.dumps(ctx.tool_args, indent=2, default=str)
        return f"🔔 *Tool Approval Request*\n\nTool: `{ctx.tool_name}`\n\n```\n{args_str}\n```"

    async def notify(self, message: str, context: ApprovalContext | None = None):
        """Send a notification message."""
        await self._ensure_bot()
        await self._bot.send_message(chat_id=self.chat_id, text=message)

    async def shutdown(self):
        """Clean shutdown of the bot."""
        if self._application:
            await self._application.updater.stop()
            await self._application.stop()
            await self._application.shutdown()


# =============================================================================
# Telegram Bot Wrapper
# =============================================================================


class TelegramLLMBot:
    """
    Telegram bot that runs LLMChatTask with full Telegram interaction.

    - UI (ask_user, output) goes through Telegram
    - Tool approvals go through Telegram with inline buttons
    """

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        system_prompt: str = "You are a helpful assistant.",
        model: str = "openai:gpt-4o",
        message_timeout: int = 300,
        approval_timeout: int = 300,
    ):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.system_prompt = system_prompt
        self.model = model
        self.message_timeout = message_timeout
        self.approval_timeout = approval_timeout

        self._ui: TelegramUI | None = None
        self._approval: TelegramApprovalChannel | None = None
        self._task: LLMChatTask | None = None

    async def start(self):
        """Initialize the bot components."""
        self._ui = TelegramUI(
            bot_token=self.bot_token,
            chat_id=self.chat_id,
            timeout=self.message_timeout,
        )
        self._approval = TelegramApprovalChannel(
            bot_token=self.bot_token,
            chat_id=self.chat_id,
            timeout=self.approval_timeout,
        )

        # Create LLMChatTask configured for Telegram
        self._task = LLMChatTask(
            name="telegram_bot",
            system_prompt=self.system_prompt,
            model=self.model,
            interactive=False,  # Required for non-terminal UI
        )

        # Set UI and approval channel
        self._task.set_ui(self._ui)
        self._task.set_approval_channel(self._approval)

    async def handle_message(self, user_message: str) -> str:
        """Process a user message and return the response."""
        if not self._task:
            await self.start()

        from zrb.context.shared_context import SharedContext
        from zrb.session.session import Session

        # Send "thinking" status
        await self._ui._send("🤔 Thinking...")

        try:
            # Create session context
            shared_ctx = SharedContext(
                input={"message": user_message},
                print_fn=lambda *a, **k: None,
            )
            session = Session(shared_ctx)

            # Run the task
            result = await self._task.async_run(session)

            # Flush any remaining output
            await self._ui.flush_output()

            return result or "Done."

        except Exception as e:
            await self._ui._send(f"❌ Error: {e}")
            raise

    async def run_forever(self):
        """Run the bot in polling mode, handling all incoming messages."""
        await self.start()

        # Both UI and approval channel handle their own polling via telegram.ext
        # This method can be extended for additional bot logic
        await self._ui._ensure_bot()

        try:
            # Keep running until interrupted
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            pass
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Clean shutdown."""
        if self._ui:
            await self._ui.shutdown()
        if self._approval:
            await self._approval.shutdown()


# =============================================================================
# Zrb Task Definition
# =============================================================================

# Environment variables (set these in your .env or shell)
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Create the bot instance
telegram_bot = TelegramLLMBot(
    bot_token=BOT_TOKEN or "YOUR_BOT_TOKEN",
    chat_id=CHAT_ID or "YOUR_CHAT_ID",
    system_prompt="You are a helpful AI assistant.",
    model="openai:gpt-4o",
)

# Create a Zrb task for CLI testing
llm_telegram_chat = LLMChatTask(
    name="llm-telegram-chat",
    system_prompt="You are a helpful AI assistant.",
    interactive=False,
)


# =============================================================================
# Main Entry Point
# =============================================================================


async def main():
    """Run the Telegram bot."""
    if not BOT_TOKEN or not CHAT_ID:
        print(
            "Please set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables"
        )
        return

    print(f"Starting Telegram bot for chat {CHAT_ID}...")

    await telegram_bot.start()

    # Example: handle one message
    # response = await telegram_bot.handle_message("Hello!")
    # print(f"Response: {response}")

    # Run forever in polling mode
    await telegram_bot.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
