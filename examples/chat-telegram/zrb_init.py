"""
Telegram + CLI Chat - Dual Mode Example

This example provides CLI + Telegram dual mode chat.
Both Telegram and terminal receive all messages and can respond.

Setup:
1. Create Telegram bot via @BotFather
2. Get your chat ID
3. Set environment variables:
   export TELEGRAM_BOT_TOKEN="your-bot-token"
   export TELEGRAM_CHAT_ID="your-chat-id"

Usage:
    cd examples/chat-telegram
    zrb llm chat "Hello!"

Features:
- Dual Output: LLM responses appear in BOTH Telegram and terminal
- Dual Input: Reply from EITHER Telegram or terminal
- Multiplexed Approvals: Approve/deny from either channel (first response wins)
- Shared History: One conversation, synced across channels
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
from zrb.llm.approval import ApprovalChannel, ApprovalContext, ApprovalResult
from zrb.llm.ui.simple_ui import BufferedOutputMixin, EventDrivenUI


BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


class TelegramBot:
    """Telegram bot wrapper for sending messages."""

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

    def add_handler(self, handler):
        if self._app:
            self._app.add_handler(handler)


def _split(text: str, max_len: int) -> list[str]:
    if len(text) <= max_len:
        return [text]
    return [text[i : i + max_len] for i in range(0, len(text), max_len)]


class TelegramUI(EventDrivenUI, BufferedOutputMixin):
    """Telegram UI using EventDrivenUI with buffered output."""

    def __init__(self, bot: TelegramBot, chat_id: str, **kwargs):
        super().__init__(**kwargs)
        BufferedOutputMixin.__init__(self, flush_interval=0.3, max_buffer_size=3000)
        self.bot = bot
        self.chat_id = chat_id
        self._approval_channel: TelegramApproval | None = None

    def set_approval_channel(self, approval: "TelegramApproval"):
        """Set the approval channel for edit routing."""
        self._approval_channel = approval

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
            # Check if approval channel is waiting for edit input
            if (
                self._approval_channel
                and self._approval_channel._waiting_for_edit_tool_call_id
            ):
                self._approval_channel.handle_text_input(text)
            else:
                self.handle_incoming_message(text)

        self.bot.add_handler(MessageHandler(filters.TEXT, handle_message))

        while True:
            await asyncio.sleep(1)


class TelegramApproval(ApprovalChannel):
    """Telegram approval channel with inline keyboard buttons."""

    _instances: dict[str, "TelegramApproval"] = {}

    def __init__(self, bot: TelegramBot, chat_id: str):
        self.bot = bot
        self.chat_id = chat_id
        self._pending: dict[str, asyncio.Future] = {}
        self._pending_context: dict[str, ApprovalContext] = {}
        self._waiting_for_edit_tool_call_id: str | None = None

    async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
        await self._ensure_handler()

        import json

        args = json.dumps(context.tool_args, indent=2, default=str)[:3000]
        text = f"🔔 Tool: `{context.tool_name}`\n```\n{args}\n```"

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ Approve", callback_data=f"yes:{context.tool_call_id}"
                    ),
                    InlineKeyboardButton(
                        "❌ Deny", callback_data=f"no:{context.tool_call_id}"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "✏️ Edit Args", callback_data=f"edit:{context.tool_call_id}"
                    ),
                ],
            ]
        )

        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._pending[context.tool_call_id] = future
        self._pending_context[context.tool_call_id] = context

        await self.bot.send(
            self.chat_id,
            text,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )

        try:
            return await future
        except asyncio.CancelledError:
            if context.tool_call_id in self._pending:
                del self._pending[context.tool_call_id]
            raise

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

            chat_id = str(query.message.chat_id)
            if chat_id not in TelegramApproval._instances:
                return

            instance = TelegramApproval._instances[chat_id]

            if action == "yes":
                if tool_call_id in instance._pending:
                    future = instance._pending.pop(tool_call_id)
                    future.set_result(ApprovalResult(approved=True))
                await query.edit_message_text("✅ Approved")

            elif action == "no":
                if tool_call_id in instance._pending:
                    future = instance._pending.pop(tool_call_id)
                    future.set_result(
                        ApprovalResult(approved=False, message="User denied")
                    )
                await query.edit_message_text("❌ Denied")

            elif action == "edit":
                if tool_call_id in instance._pending:
                    future = instance._pending[tool_call_id]
                    instance._pending_context[tool_call_id] = (
                        instance._pending_context.get(tool_call_id)
                    )
                    context_obj = instance._pending_context.get(tool_call_id)
                    args = json.dumps(
                        context_obj.tool_args if context_obj else {},
                        indent=2,
                        default=str,
                    )
                    await instance.bot.send(
                        chat_id,
                        f"✏️ Editing `{context_obj.tool_name if context_obj else 'tool'}`\n\n"
                        f"Send new arguments (JSON or YAML format):\n"
                        f"```\n{args}\n```",
                        parse_mode="Markdown",
                    )
                    # Mark as waiting for edit input
                    instance._waiting_for_edit_tool_call_id = tool_call_id

        self.bot.add_handler(CallbackQueryHandler(handle_callback))

    def handle_text_input(self, text: str):
        """Handle text input when waiting for edit."""
        if self._waiting_for_edit_tool_call_id:
            tool_call_id = self._waiting_for_edit_tool_call_id
            self._waiting_for_edit_tool_call_id = None
            if tool_call_id in self._pending:
                future = self._pending[tool_call_id]
                new_args = self._parse_edited_content(text)
                if new_args is not None:
                    future.set_result(
                        ApprovalResult(approved=True, override_args=new_args)
                    )
                else:
                    future.set_result(
                        ApprovalResult(approved=False, message="Invalid format")
                    )

    def _parse_edited_content(self, content: str) -> dict | None:
        """Parse edited content as JSON or YAML."""
        content = content.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        try:
            import yaml

            return yaml.safe_load(content)
        except yaml.YAMLError:
            pass
        return None


if BOT_TOKEN and CHAT_ID:
    bot = TelegramBot.get(BOT_TOKEN)
    telegram_approval = TelegramApproval(bot, CHAT_ID)

    # Create a factory that wires up the approval channel
    def telegram_ui_factory(
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
        ui = TelegramUI(
            ctx=ctx,
            llm_task=llm_task,
            history_manager=history_manager,
            config=cfg,
            initial_message=initial_message,
            initial_attachments=initial_attachments,
            bot=bot,
            chat_id=CHAT_ID,
        )
        ui.set_approval_channel(telegram_approval)
        return ui

    llm_chat.append_ui_factory(telegram_ui_factory)
    llm_chat.append_approval_channel(telegram_approval)

    print(f"🤖 Telegram + CLI dual mode for chat ID: {CHAT_ID}")
    print("   Both channels receive all messages.")
    print("   Approvals work from both - first response wins!")

else:
    print("❌ Telegram + CLI dual mode requires both environment variables:")
    print('   export TELEGRAM_BOT_TOKEN="your-bot-token"')
    print('   export TELEGRAM_CHAT_ID="your-chat-id"')
    print("\nSee README.md for setup instructions.")
