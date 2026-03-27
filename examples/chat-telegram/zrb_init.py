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
from zrb.config.config import CFG
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
            CFG.LOGGER.debug(
                f"TelegramUI handle_message: text='{text[:50]}...', "
                f"approval_channel={self._approval_channel is not None}, "
                f"approval_channel_id={id(self._approval_channel) if self._approval_channel else None}, "
                f"waiting_for_edit={self._approval_channel._waiting_for_edit_tool_call_id if self._approval_channel else None}"
            )
            if (
                self._approval_channel
                and self._approval_channel._waiting_for_edit_tool_call_id
            ):
                # Route to approval channel instead of LLM
                CFG.LOGGER.debug(
                    "TelegramUI Routing to approval channel for edit input"
                )
                self._approval_channel.handle_text_input(text)
            else:
                # Normal flow - route to LLM
                CFG.LOGGER.debug("TelegramUI Routing to LLM")
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
        self._pending_context: dict[str, ApprovalContext] = {}
        self._waiting_for_edit: dict[str, asyncio.Future] = {}
        self._waiting_for_edit_tool_call_id: str | None = None

    async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
        CFG.LOGGER.debug(
            f"TelegramApproval request_approval START for {context.tool_name}"
        )
        CFG.LOGGER.debug(f"TelegramApproval tool_call_id: {context.tool_call_id}")
        CFG.LOGGER.debug(
            f"TelegramApproval tool_args: {context.tool_args}, type: {type(context.tool_args)}"
        )
        await self._ensure_handler()

        # Convert tool_args to proper dict if needed
        tool_args = context.tool_args
        if not isinstance(tool_args, dict):
            CFG.LOGGER.debug(
                f"TelegramApproval tool_args is NOT a dict, converting from {tool_args}..."
            )
            tool_args = {}

        args = json.dumps(tool_args, indent=2, default=str)[:3000]
        text = f"🔔 Tool: `{context.tool_name}`\n```\n{args}\n```"

        keyboard = [
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

        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._pending[context.tool_call_id] = future
        self._pending_context[context.tool_call_id] = context
        CFG.LOGGER.debug(
            f"TelegramApproval Created future {id(future)}, pending count: {len(self._pending)}"
        )

        await self.bot.send(
            self.chat_id,
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        CFG.LOGGER.debug(
            f"TelegramApproval Message sent for tool_call_id={context.tool_call_id}, future.done()={future.done()}"
        )

        try:
            CFG.LOGGER.debug("TelegramApproval About to await future...")
            result = await future
            CFG.LOGGER.debug(
                f"TelegramApproval Future resolved! approved={result.approved}, message={result.message}"
            )
            return result
        except asyncio.CancelledError:
            CFG.LOGGER.debug(
                "TelegramApproval Cancelled - another channel won the race"
            )
            # Clean up pending state
            if context.tool_call_id in self._pending:
                del self._pending[context.tool_call_id]
            if context.tool_call_id in self._pending_context:
                del self._pending_context[context.tool_call_id]
            raise  # Propagate cancellation
        except BaseException as e:
            CFG.LOGGER.debug(
                f"TelegramApproval BaseException caught: {type(e).__name__}: {e}"
            )
            import traceback

            traceback.print_exc()
            # For other exceptions, re-raise
            raise

    async def notify(
        self, message: str, context: ApprovalContext | None = None
    ) -> None:
        await self.bot.send(self.chat_id, message)

    def handle_text_input(self, text: str):
        """Handle text input - used when user sends text while waiting for edit."""
        CFG.LOGGER.debug(
            f"TelegramApproval handle_text_input: text='{text[:50]}...', "
            f"waiting_for_edit_tool_call_id={self._waiting_for_edit_tool_call_id}"
        )
        if self._waiting_for_edit_tool_call_id:
            tool_call_id = self._waiting_for_edit_tool_call_id
            self._waiting_for_edit_tool_call_id = None
            CFG.LOGGER.debug(
                f"TelegramApproval Clearing waiting flag, tool_call_id={tool_call_id}"
            )

            if tool_call_id in self._waiting_for_edit:
                future = self._waiting_for_edit.pop(tool_call_id)
                # Parse the edited JSON/YAML
                new_args = self._parse_edited_content(text)
                CFG.LOGGER.debug(f"TelegramApproval Parsed args: {new_args}")
                if new_args is not None:
                    future.set_result(
                        ApprovalResult(approved=True, override_args=new_args)
                    )
                else:
                    future.set_result(
                        ApprovalResult(approved=False, message="Invalid format")
                    )
            else:
                CFG.LOGGER.debug(
                    f"TelegramApproval WARNING: tool_call_id {tool_call_id} not in _waiting_for_edit"
                )
        else:
            CFG.LOGGER.debug(
                "TelegramApproval WARNING: _waiting_for_edit_tool_call_id is None"
            )

    def _parse_edited_content(self, content: str) -> dict | None:
        """Parse edited content as JSON or YAML."""
        import yaml

        content = content.strip()

        # Try JSON first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try YAML
        try:
            return yaml.safe_load(content)
        except yaml.YAMLError:
            pass

        return None

    async def _ensure_handler(self):
        if self.chat_id in TelegramApproval._instances:
            return

        TelegramApproval._instances[self.chat_id] = self
        CFG.LOGGER.debug(
            f"TelegramApproval Registered instance {id(self)} for chat_id={self.chat_id}"
        )

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
                    instance.resolve(tool_call_id, True)
                await query.edit_message_text("✅ Approved")

            elif action == "no":
                if tool_call_id in instance._pending:
                    instance.resolve(tool_call_id, False)
                await query.edit_message_text("❌ Denied")

            elif action == "edit":
                # User wants to edit arguments
                # NOTE: We do NOT create a new future - we keep the SAME future
                # that request_approval() is waiting on. When handle_text_input
                # is called with edited args, it will resolve the original future.
                context = instance._pending_context.get(tool_call_id)
                if context:
                    # Ask for new arguments
                    args = json.dumps(context.tool_args, indent=2, default=str)
                    await instance.bot.send(
                        chat_id,
                        f"✏️ Editing `{context.tool_name}`\n\n"
                        f"Send new arguments (JSON or YAML format):\n"
                        f"```\n{args}\n```",
                        parse_mode="Markdown",
                    )
                    # Mark as waiting for edit input
                    # The future in _pending stays the SAME - request_approval awaits it
                    instance._waiting_for_edit_tool_call_id = tool_call_id
                    CFG.LOGGER.debug(
                        f"TelegramApproval Set _waiting_for_edit_tool_call_id = {tool_call_id}"
                    )
                    # Store reference to the pending future so handle_text_input can resolve it
                    instance._waiting_for_edit[tool_call_id] = instance._pending.get(
                        tool_call_id
                    )
                    CFG.LOGGER.debug(
                        "TelegramApproval Edit mode - waiting for text input"
                    )

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
    # Create approval channel first
    telegram_approval = TelegramApproval(bot, CHAT_ID)

    # Create UI factory that includes approval channel reference
    def telegram_ui_factory(
        ctx,
        llm_task_core,
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
            llm_task=llm_task_core,
            history_manager=history_manager,
            config=cfg,
            initial_message=initial_message,
            initial_attachments=initial_attachments,
            bot=bot,
            chat_id=CHAT_ID,
        )
        # Wire up approval channel for edit routing
        ui.set_approval_channel(telegram_approval)
        return ui

    # Register UI and approval
    llm_chat.append_ui_factory(telegram_ui_factory)
    llm_chat.append_approval_channel(telegram_approval)
    # Note: Terminal approval is handled by the default UI (BaseUI._confirm_tool_execution)
    # When approval_channel is used, it takes priority over CLI confirmation

    print(f"🤖 Telegram + CLI dual mode for chat ID: {CHAT_ID}")
    print("   Both channels receive all messages.")
    print("   Approvals work from both - first response wins!")
    print("   Tool argument editing available on Telegram!")

elif BOT_TOKEN or CHAT_ID:
    print("⚠️  Set both TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")

else:
    # CLI only (no telegram env vars) - this shouldn't happen for this example
    pass
