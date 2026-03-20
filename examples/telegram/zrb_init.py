"""
Telegram UI/Approval for Zrb LLM Chat

This example shows how to make `zrb llm chat` work on Telegram instead of the terminal.
By setting custom UI and approval channels, the existing llm_chat task will use Telegram.

Usage:
    export TELEGRAM_BOT_TOKEN="your_token"
    export TELEGRAM_CHAT_ID="your_chat_id"
    zrb llm chat
"""

import asyncio
import json
import os
from typing import Any

from zrb.context.any_context import AnyContext
from zrb.llm.app.base_ui import BaseUI
from zrb.llm.approval import ApprovalChannel, ApprovalContext, ApprovalResult
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.task.llm_task import LLMTask

# =============================================================================
# Telegram UI Implementation
# =============================================================================


class TelegramUI(BaseUI):
    """BaseUI implementation for Telegram.

    This inherits the full interactive chat loop (command parsing, message queue,
    session management, tools) from BaseUI, but overrides the I/O to use Telegram.
    """

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        ctx: AnyContext,
        yolo_xcom_key: str,
        assistant_name: str,
        llm_task: LLMTask,
        history_manager: AnyHistoryManager,
        timeout: int = 300,
        **kwargs,
    ):
        super().__init__(
            ctx=ctx,
            yolo_xcom_key=yolo_xcom_key,
            assistant_name=assistant_name,
            llm_task=llm_task,
            history_manager=history_manager,
            **kwargs,
        )
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.timeout = timeout
        self._bot = None
        self._application = None
        self._pending_questions: dict[str, asyncio.Future[str]] = {}
        self._buffer: list[str] = []
        self._flush_task = None

    async def _ensure_bot(self):
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
        """Handle incoming Telegram messages."""
        text = update.message.text
        if not text:
            return

        # Route message to the pending ask_user() question
        for qid, future in list(self._pending_questions.items()):
            if not future.done():
                future.set_result(text)
                self._pending_questions.pop(qid, None)
                return

        # If no pending question, check if it's a command
        if self._handle_exit_command(text):
            return
        if self._handle_info_command(text):
            return
        if self._handle_save_command(text):
            return
        if self._handle_load_command(text):
            return
        if self._handle_redirect_command(text):
            return
        if self._handle_attach_command(text):
            return
        if self._handle_toggle_yolo(text):
            return
        if self._handle_set_model_command(text):
            return
        if self._handle_exec_command(text):
            return
        if self._handle_custom_command(text):
            return

        # Not a command, submit as user message to the LLM
        self._submit_user_message(self._llm_task, text)

    async def run_async(self):
        """Run the application."""
        await self._ensure_bot()

        # Start message processor
        self._process_messages_task = asyncio.create_task(self._process_messages_loop())

        # Start flush loop
        self._flush_task = asyncio.create_task(self._flush_loop())

        if self._initial_message:
            self._submit_user_message(self._llm_task, self._initial_message)

        try:
            # Block until cancelled
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            if self._process_messages_task:
                self._process_messages_task.cancel()
            if self._flush_task:
                self._flush_task.cancel()
            await self.shutdown()

    async def _flush_loop(self):
        while True:
            await asyncio.sleep(0.5)
            await self.flush_output()

    def on_exit(self):
        """Called when user types an exit command."""
        self._send("Shutting down... 👋")
        # Give it a tiny bit to send the message before hard exit
        import sys
        import threading
        import time

        def exit_later():
            time.sleep(1)
            sys.exit(0)

        threading.Thread(target=exit_later).start()

    async def ask_user(self, prompt: str) -> str:
        """Wait for user input from Telegram."""
        await self._ensure_bot()

        # Send the prompt to Telegram
        await self._bot.send_message(chat_id=self.chat_id, text=f"❓ {prompt}")

        # Wait for the next message in _handle_message to resolve this future
        loop = asyncio.get_event_loop()
        future: asyncio.Future[str] = loop.create_future()
        self._pending_questions[f"q_{id(future)}"] = future

        try:
            async with asyncio.timeout(self.timeout):
                return await future
        except asyncio.TimeoutError:
            self._pending_questions.clear()
            await self._bot.send_message(
                chat_id=self.chat_id, text="⏰ Timed out waiting for response."
            )
            return ""

    def append_to_output(
        self, *values, sep: str = " ", end: str = "\n", file=None, flush: bool = False
    ):
        self._buffer.append(sep.join(str(v) for v in values) + end)

    def stream_to_parent(
        self, *values, sep: str = " ", end: str = "\n", file=None, flush: bool = False
    ):
        msg = sep.join(str(v) for v in values) + end
        self._send(msg)

    def _send(self, msg: str):
        import asyncio

        from zrb.util.cli.style import remove_style

        # Remove ANSI escape codes for Telegram
        clean_msg = remove_style(msg)

        # Don't send empty messages after stripping style
        if not clean_msg.strip():
            return

        async def do_send():
            await self._ensure_bot()
            msg_to_send = clean_msg
            if len(msg_to_send) > 4000:
                msg_to_send = msg_to_send[:3997] + "..."
            await self._bot.send_message(chat_id=self.chat_id, text=msg_to_send)

        # We need to run this task in the background since append_to_output is sync
        asyncio.create_task(do_send())

    async def flush_output(self):
        if self._buffer:
            msg = "".join(self._buffer)
            self._buffer = []
            self._send(msg)

    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
        self._send(f"⚠️ Command execution disabled from Telegram")
        return {"error": "Disabled"}

    async def shutdown(self):
        if self._application:
            await self._application.updater.stop()
            await self._application.stop()
            await self._application.shutdown()


# =============================================================================
# Telegram Approval Channel Implementation
# =============================================================================


class TelegramApprovalChannel(ApprovalChannel):
    """ApprovalChannel implementation for Telegram."""

    def __init__(self, bot_token: str, chat_id: str, timeout: int = 300):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.timeout = timeout
        self._bot = None
        self._application = None
        self._pending_approvals: dict[str, asyncio.Future[ApprovalResult]] = {}

    async def _ensure_bot(self):
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
        self._pending_approvals[context.tool_call_id] = future

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
            self._pending_approvals.pop(context.tool_call_id, None)
            return ApprovalResult(approved=False, message="Timeout")

    async def _handle_callback(self, update, context):
        query = update.callback_query
        await query.answer()

        action, tool_call_id = query.data.split(":", 1)
        if tool_call_id not in self._pending_approvals:
            await query.edit_message_text("⚠️ Expired or invalid request")
            return

        approved = action == "approve"
        result = ApprovalResult(approved=approved)
        self._pending_approvals.pop(tool_call_id).set_result(result)

        emoji = "✅ Approved" if approved else "❌ Denied"
        await query.edit_message_text(
            f"{emoji}\n\nTool: `{tool_call_id}`", parse_mode="Markdown"
        )

    def _format_message(self, ctx: ApprovalContext) -> str:
        args_str = json.dumps(ctx.tool_args, indent=2, default=str)
        return f"🔔 *Tool Approval Request*\n\nTool: `{ctx.tool_name}`\n\n```\n{args_str}\n```"

    async def notify(self, message: str, context: ApprovalContext | None = None):
        await self._ensure_bot()
        await self._bot.send_message(chat_id=self.chat_id, text=message)

    async def shutdown(self):
        if self._application:
            await self._application.updater.stop()
            await self._application.stop()
            await self._application.shutdown()


# =============================================================================
# Hijack the built-in llm_chat task
# =============================================================================

# Get environment variables
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

if BOT_TOKEN and CHAT_ID:

    # 2. Import the existing, fully-featured llm_chat task
    from zrb.builtin.llm.chat import llm_chat

    # We must configure telegram_ui inside a lazy factory so that
    # context is properly resolved when the task runs

    # 1. Create Telegram approval channel
    telegram_approval = TelegramApprovalChannel(bot_token=BOT_TOKEN, chat_id=CHAT_ID)

    # 3. Configure it for Telegram!
    # By providing a factory, we can inject the TelegramUI with the execution context (ctx).

    def create_telegram_ui(
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
            bot_token=BOT_TOKEN,
            chat_id=CHAT_ID,
            ctx=ctx,
            yolo_xcom_key="yolo",
            assistant_name="Zrb Telegram Bot",
            llm_task=llm_task_core,
            history_manager=history_manager,
            initial_message=initial_message,
            conversation_session_name=initial_conversation_name,
            initial_attachments=initial_attachments,
            yolo=initial_yolo,
            summarize_commands=ui_commands["summarize"],
            attach_commands=ui_commands["attach"],
            exit_commands=ui_commands["exit"],
            info_commands=ui_commands["info"],
            save_commands=ui_commands["save"],
            load_commands=ui_commands["load"],
            yolo_toggle_commands=ui_commands["yolo_toggle"],
            set_model_commands=ui_commands["set_model"],
            redirect_output_commands=ui_commands["redirect_output"],
            exec_commands=ui_commands["exec"],
            # add triggers, tool handlers etc here if needed
        )

    llm_chat.set_ui_factory(create_telegram_ui)
    llm_chat.set_approval_channel(telegram_approval)

    print(f"🤖 Telegram hijacked llm_chat for chat ID: {CHAT_ID}")
    print("   The LLM will now interact with you on Telegram!")

else:
    print(
        "⚠️  Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables."
    )
