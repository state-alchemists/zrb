"""
Telegram + CLI Dual UI - Event-Driven Multiplexing

This implements Level 2+: EventDrivenUI with terminal input routing
- TelegramUI uses EventDrivenUI (event-driven, buffered output)
- Terminal stdin is routed to the same message queue as Telegram
- Approval channel broadcasts to both, first response wins
- Terminal supports [Y/n/e] with edit mode via editor

Usage:
    export TELEGRAM_BOT_TOKEN="your-token"
    export TELEGRAM_CHAT_ID="your-chat-id"
    zrb llm chat
"""

import asyncio
import json
import os
import tempfile
import traceback
from typing import Callable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, MessageHandler, filters

from zrb.builtin.llm.chat import llm_chat
from zrb.llm.app.ui import (
    BufferedOutputMixin,
    EventDrivenUI,
)
from zrb.llm.approval import ApprovalChannel, ApprovalContext, ApprovalResult
from zrb.util.cli.style import remove_style

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


# =============================================================================
# Global State
# =============================================================================

_shutdown_requested = False


def is_shutdown_requested() -> bool:
    return _shutdown_requested


def request_shutdown():
    global _shutdown_requested
    _shutdown_requested = True


# =============================================================================
# Shared Telegram Bot
# =============================================================================


class TelegramBot:
    """Shared bot instance."""

    _instance: "TelegramBot | None" = None

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
        if self._app:
            return self._app
        print(f"[BOT] Starting with token: {self.token[:10]}...", flush=True)
        self._app = Application.builder().token(self.token).build()
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling()
        print("[BOT] Started and polling!", flush=True)
        return self._app

    async def send(self, chat_id: str, text: str, **kwargs):
        """Send a message (auto-splits long messages)."""
        print(f"[BOT.send] chat_id={chat_id}, text_len={len(text)}", flush=True)
        if not self._app:
            print("[BOT.send] No app!", flush=True)
            return
        clean = remove_style(text).strip()
        if not clean:
            print("[BOT.send] Empty after strip", flush=True)
            return

        chunks = self._split(clean, 4000)
        for i, chunk in enumerate(chunks):
            chunk_kwargs = kwargs.copy()
            if "reply_markup" in chunk_kwargs and i < len(chunks) - 1:
                del chunk_kwargs["reply_markup"]

            try:
                print(f"[BOT.send] Sending chunk {i+1}/{len(chunks)}", flush=True)
                await self._app.bot.send_message(
                    chat_id=chat_id, text=chunk, **chunk_kwargs
                )
                print(f"[BOT.send] Chunk {i+1} sent!", flush=True)
            except Exception as e:
                print(f"[BOT.send] Error: {e}", flush=True)
                if "parse_mode" in chunk_kwargs:
                    del chunk_kwargs["parse_mode"]
                    try:
                        await self._app.bot.send_message(
                            chat_id=chat_id, text=chunk, **chunk_kwargs
                        )
                    except Exception:
                        pass

    @staticmethod
    def _split(text: str, max_len: int) -> list[str]:
        if len(text) <= max_len:
            return [text]
        return [text[i : i + max_len] for i in range(0, len(text), max_len)]


# =============================================================================
# Telegram UI - EventDriven with buffered output and terminal input routing
# =============================================================================


class TelegramUI(EventDrivenUI, BufferedOutputMixin):
    """Telegram UI with buffered output and terminal input routing.

    This UI:
    - Buffers output to Telegram for clean messages
    - Routes Telegram messages via handle_incoming_message()
    - Routes terminal stdin via a separate task calling handle_incoming_message()
    """

    def __init__(self, bot: TelegramBot, chat_id: str, **kwargs):
        super().__init__(**kwargs)
        BufferedOutputMixin.__init__(self, flush_interval=0.3, max_buffer_size=3000)
        self.bot = bot
        self.chat_id = chat_id
        self._terminal_input_task: asyncio.Task | None = None
        print(f"[UI] Created for chat_id: {chat_id}", flush=True)

    async def _send_buffered(self, text: str) -> None:
        """Send buffered content to Telegram."""
        await self.bot.send(self.chat_id, text)

    async def print(self, text: str) -> None:
        """Buffer output for Telegram and print to terminal."""
        self.buffer_output(text)
        # Also print to terminal for visibility
        print(text, end="", flush=True)

    async def start_event_loop(self) -> None:
        """Start the bot, flush loop, and terminal input routing."""
        print("[UI] Starting event loop...", flush=True)

        try:
            # Start the bot (only happens once)
            if not self.bot._app:
                print("[UI] Starting bot...", flush=True)
                await self.bot.start()
                print("[UI] Bot started!", flush=True)

            # Start the periodic flush loop
            print("[UI] Starting flush loop...", flush=True)
            await self.start_flush_loop()
            print("[UI] Flush loop started!", flush=True)

            # Register Telegram message handler
            async def handle_telegram_message(update, context):
                # Skip edit reply messages - they go to approval channel
                if update.message.reply_to_message:
                    reply_text = update.message.reply_to_message.text
                    if reply_text and "✏️ Edit arguments for" in reply_text:
                        return
                text = update.message.text
                print(f"[UI] Telegram msg: {text[:50]}...", flush=True)
                self.handle_incoming_message(text)

            self.bot._app.add_handler(
                MessageHandler(filters.TEXT, handle_telegram_message)
            )
            print("[UI] Handler registered!", flush=True)

            # Start terminal input routing
            print("[UI] Starting terminal input...", flush=True)
            self._terminal_input_task = asyncio.create_task(
                self._run_terminal_input_loop()
            )
            print("[UI] Terminal input started!", flush=True)

            print("[UI] Event loop ready!", flush=True)

            # Keep running
            while not is_shutdown_requested():
                await asyncio.sleep(1)

        except Exception as e:
            print(f"[UI] Error: {e}", flush=True)
            traceback.print_exc()

    async def _run_terminal_input_loop(self):
        """Read from terminal stdin and route to handle_incoming_message."""
        print("[TERM] Terminal input loop started", flush=True)
        loop = asyncio.get_running_loop()
        while not is_shutdown_requested():
            try:
                # Read line from terminal
                line = await loop.run_in_executor(None, input, "")
                if is_shutdown_requested():
                    break
                if line.strip():
                    print(f"[TERM] Got: {line.strip()[:50]}...", flush=True)
                    self.handle_incoming_message(line.strip())
            except (EOFError, KeyboardInterrupt):
                print("[TERM] EOF/Interrupt", flush=True)
                request_shutdown()
                break
            except asyncio.CancelledError:
                print("[TERM] Cancelled", flush=True)
                break
            except Exception as e:
                print(f"[TERM] Error: {e}", flush=True)
        print("[TERM] Loop ended", flush=True)

    async def cleanup(self):
        """Cleanup terminal input task."""
        print("[UI] Cleanup", flush=True)
        if self._terminal_input_task:
            self._terminal_input_task.cancel()
            try:
                await self._terminal_input_task
            except asyncio.CancelledError:
                pass
        await self.stop_flush_loop()


# =============================================================================
# Multiplexed Approval Channel
# =============================================================================


class MultiplexedApprovalChannel(ApprovalChannel):
    """Approval channel that broadcasts to both terminal and Telegram.

    - Terminal gets [Y/n/e] prompt, supports edit mode
    - Telegram gets inline buttons, supports edit via reply
    - First response wins
    """

    def __init__(self, telegram_ui: TelegramUI):
        self.telegram_ui = telegram_ui
        self._pending: dict[str, asyncio.Future] = {}
        self._edit_contexts: dict[str, ApprovalContext] = {}
        self._edit_messages: dict[int, str] = {}  # message_id -> tool_call_id
        self._edit_futures: dict[str, asyncio.Future] = {}
        self._handlers_registered = False
        print("[APPROVAL] MultiplexedApprovalChannel created", flush=True)

    async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
        """Request approval from both terminal and Telegram."""
        print(f"[APPROVAL] request_approval called for {context.tool_name}", flush=True)
        print(f"[APPROVAL] tool_call_id={context.tool_call_id[:20]}...", flush=True)

        if is_shutdown_requested():
            print("[APPROVAL] Shutdown, denying", flush=True)
            return ApprovalResult(approved=False, message="Shutdown requested")

        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._pending[context.tool_call_id] = future
        self._edit_contexts[context.tool_call_id] = context

        # Run both channels in parallel, first result wins
        print("[APPROVAL] Starting terminal and telegram tasks...", flush=True)
        term_task = asyncio.create_task(
            self._request_terminal_approval(context, future)
        )
        tel_task = asyncio.create_task(self._request_telegram_approval(context, future))

        try:
            print("[APPROVAL] Waiting for response...", flush=True)
            async with asyncio.timeout(300):
                result = await future
                print(f"[APPROVAL] Got result: {result.approved}", flush=True)
                return result
        except asyncio.TimeoutError:
            print("[APPROVAL] Timeout!", flush=True)
            return ApprovalResult(approved=False, message="Timeout")
        finally:
            term_task.cancel()
            tel_task.cancel()
            self._pending.pop(context.tool_call_id, None)
            self._edit_contexts.pop(context.tool_call_id, None)

    async def _request_terminal_approval(
        self, context: ApprovalContext, future: asyncio.Future
    ):
        """Handle approval via terminal [Y/n/e]."""
        print("[TERM_APPROVAL] Starting", flush=True)
        try:
            args_str = _format_args(context.tool_args)
            await self.telegram_ui.print(f"\n🔔 Tool: {context.tool_name}\n")
            await self.telegram_ui.print(f"Arguments:\n{args_str[:2000]}\n")
            await self.telegram_ui.print("Approve? [Y/n/e] ")

            print("[TERM_APPROVAL] Waiting for input...", flush=True)
            response = await self.telegram_ui.get_input("")
            print(f"[TERM_APPROVAL] Got: {response}", flush=True)

            r = response.strip().lower()

            if r in ("", "y", "yes", "ok"):
                if not future.done():
                    future.set_result(ApprovalResult(approved=True))
                return

            if r in ("n", "no", "deny", "cancel"):
                if not future.done():
                    future.set_result(
                        ApprovalResult(approved=False, message="User denied")
                    )
                return

            if r == "e":
                result = await self._handle_terminal_edit(context)
                if not future.done():
                    future.set_result(result)
                return

            if not future.done():
                future.set_result(
                    ApprovalResult(approved=False, message=f"Unknown: {response}")
                )
        except Exception as e:
            print(f"[TERM_APPROVAL] Error: {e}", flush=True)
            if not future.done():
                future.set_result(ApprovalResult(approved=False, message=str(e)))

    async def _handle_terminal_edit(self, context: ApprovalContext) -> ApprovalResult:
        """Handle edit mode in terminal - launch editor."""
        import subprocess

        from zrb.config.config import CFG

        print("[TERM_EDIT] Starting", flush=True)
        await self.telegram_ui.print("\n✏️ Edit mode - opening editor...\n")

        # Extract args
        args = _extract_args(context.tool_args)
        content_str = json.dumps(args, indent=2, ensure_ascii=False)

        with tempfile.NamedTemporaryFile(suffix=".json", mode="w+", delete=False) as tf:
            tf.write(content_str)
            tf_path = tf.name

        try:
            # Run editor with proper TTY control
            print(f"\n⚙️ Running: {CFG.EDITOR} {tf_path}\n")
            subprocess.run([CFG.EDITOR, tf_path])

            with open(tf_path, "r", encoding="utf-8") as tf:
                new_content = tf.read()
        finally:
            os.remove(tf_path)

        if new_content.strip() == content_str.strip():
            await self.telegram_ui.print("ℹ️ No changes made.\n")
            return ApprovalResult(approved=False, message="Edit cancelled")

        try:
            edited_args = json.loads(new_content)
            await self.telegram_ui.print("✅ Approved with edited arguments.\n")
            return ApprovalResult(approved=True, edited_args=edited_args)
        except json.JSONDecodeError as e:
            await self.telegram_ui.print(f"❌ Invalid JSON: {e}\n")
            return ApprovalResult(approved=False, message=f"Invalid JSON: {e}")

    async def _request_telegram_approval(
        self, context: ApprovalContext, future: asyncio.Future
    ):
        """Handle approval via Telegram inline buttons."""
        print("[TEL_APPROVAL] Starting", flush=True)
        try:
            await self._ensure_telegram_handlers()

            args_str = json.dumps(context.tool_args, indent=2, default=str)[:500]
            safe_text = f"🔔 Tool: {context.tool_name}\n\n{args_str}"

            keyboard = [
                [
                    InlineKeyboardButton(
                        "✅ Approve", callback_data=f"yes:{context.tool_call_id}"
                    ),
                    InlineKeyboardButton(
                        "❌ Deny", callback_data=f"no:{context.tool_call_id}"
                    ),
                    InlineKeyboardButton(
                        "✏️ Edit", callback_data=f"edit:{context.tool_call_id}"
                    ),
                ]
            ]

            print("[TEL_APPROVAL] Sending to Telegram...", flush=True)
            await self.telegram_ui.bot.send(
                self.telegram_ui.chat_id,
                safe_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            print("[TEL_APPROVAL] Sent!", flush=True)
        except Exception as e:
            print(f"[TEL_APPROVAL] Error: {e}", flush=True)
            traceback.print_exc()
            if not future.done():
                future.set_result(ApprovalResult(approved=False, message=str(e)))

    async def _ensure_telegram_handlers(self):
        """Register Telegram callback handlers once."""
        print(
            f"[TEL_HANDLERS] Checking: app={self.telegram_ui.bot._app is not None}, registered={self._handlers_registered}",
            flush=True,
        )

        if not self.telegram_ui.bot._app or self._handlers_registered:
            return

        self._handlers_registered = True
        app = self.telegram_ui.bot._app

        async def handle_callback(update, context):
            query = update.callback_query
            await query.answer()
            action, tool_call_id = query.data.split(":", 1)
            print(
                f"[CALLBACK] action={action}, tool_call_id={tool_call_id[:20]}...",
                flush=True,
            )

            if tool_call_id not in self._pending:
                print(f"[CALLBACK] Not pending!", flush=True)
                return

            if action == "edit":
                future = self._pending.pop(tool_call_id)
                approval_context = self._edit_contexts.pop(tool_call_id, None)
                if approval_context:
                    await self._start_telegram_edit_flow(
                        query, tool_call_id, future, approval_context
                    )
                else:
                    future.set_result(
                        ApprovalResult(approved=False, message="Edit context lost")
                    )
            else:
                approved = action == "yes"
                future = self._pending.pop(tool_call_id)
                self._edit_contexts.pop(tool_call_id, None)
                future.set_result(ApprovalResult(approved=approved))
                await query.edit_message_text(
                    "✅ Approved" if approved else "❌ Denied"
                )

        async def handle_edit_reply(update, context):
            reply_to = update.message.reply_to_message
            if not reply_to:
                return

            message_id = reply_to.message_id
            if message_id not in self._edit_messages:
                return

            tool_call_id = self._edit_messages.pop(message_id, None)
            if not tool_call_id or tool_call_id not in self._edit_futures:
                return

            future = self._edit_futures.pop(tool_call_id)

            try:
                edited_args = json.loads(update.message.text)
                await update.message.reply_text("✅ Arguments updated, executing...")
                future.set_result(
                    ApprovalResult(approved=True, edited_args=edited_args)
                )
            except json.JSONDecodeError as e:
                await update.message.reply_text(
                    f"❌ Invalid JSON: {e}\nPlease reply with valid JSON or type 'cancel'."
                )
                self._edit_messages[message_id] = tool_call_id
                self._edit_futures[tool_call_id] = future

        app.add_handler(CallbackQueryHandler(handle_callback))
        app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_reply), group=1
        )
        print("[TEL_HANDLERS] Registered!", flush=True)

    async def _start_telegram_edit_flow(
        self,
        query,
        tool_call_id: str,
        future: asyncio.Future,
        approval_context: ApprovalContext,
    ):
        """Send args as editable message and wait for user reply."""
        print("[TEL_EDIT] Starting", flush=True)
        context_json = json.dumps(approval_context.tool_args, indent=2, default=str)

        safe_text = (
            f"✏️ Edit arguments for {approval_context.tool_name}\n\n"
            f"Reply to this message with modified JSON:\n"
            f"{context_json}\n\n"
            f"Or type 'cancel' to abort."
        )

        message = await query.edit_message_text(safe_text)
        print(f"[TEL_EDIT] Sent edit message {message.message_id}", flush=True)

        self._edit_messages[message.message_id] = tool_call_id
        self._edit_futures[tool_call_id] = future

    async def notify(
        self, message: str, context: ApprovalContext | None = None
    ) -> None:
        """Send notification to both channels."""
        await self.telegram_ui.print(f"📢 {message}\n")
        await self.telegram_ui.bot.send(self.telegram_ui.chat_id, message)


# =============================================================================
# Helper functions
# =============================================================================


def _format_args(raw) -> str:
    """Format arguments for display."""
    try:
        args = _extract_args(raw)
        return json.dumps(args, indent=2, ensure_ascii=False)
    except Exception:
        return str(raw)


def _extract_args(raw) -> dict:
    """Extract clean args dict from wrapped format."""
    try:
        if isinstance(raw, dict):
            if "args_dict" in raw:
                return raw["args_dict"]
            elif "args_json" in raw and isinstance(raw["args_json"], str):
                return json.loads(raw["args_json"])
            elif "args" in raw and isinstance(raw["args"], str):
                return json.loads(raw["args"])
        elif isinstance(raw, str):
            try:
                return json.loads(raw)
            except Exception:
                pass
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


# =============================================================================
# UI Factory
# =============================================================================

_telegram_bot: TelegramBot | None = None
_telegram_ui: TelegramUI | None = None
_approval_channel: MultiplexedApprovalChannel | None = None


def create_ui_factory() -> Callable:
    """Create UI factory."""

    def factory(
        ctx,
        llm_task_core,
        history_manager,
        ui_commands,
        initial_message,
        initial_conversation_name,
        initial_yolo,
        initial_attachments,
    ) -> TelegramUI:
        global _telegram_bot, _telegram_ui, _approval_channel

        print(
            f"[FACTORY] Creating for session: {initial_conversation_name}", flush=True
        )

        # Create config
        from zrb.llm.app.ui.config import UIConfig

        cfg = UIConfig.default()
        if ui_commands:
            cfg = cfg.merge_commands(ui_commands)
        cfg.yolo = initial_yolo
        cfg.conversation_session_name = initial_conversation_name

        # Create bot
        print("[FACTORY] Creating bot...", flush=True)
        _telegram_bot = TelegramBot.get(BOT_TOKEN)

        # Create Telegram UI
        print("[FACTORY] Creating UI...", flush=True)
        _telegram_ui = TelegramUI(
            ctx=ctx,
            llm_task=llm_task_core,
            history_manager=history_manager,
            config=cfg,
            initial_message=initial_message,
            initial_attachments=initial_attachments,
            bot=_telegram_bot,
            chat_id=CHAT_ID,
        )

        # Set up approval channel once
        if _approval_channel is None:
            print("[FACTORY] Creating approval channel...", flush=True)
            _approval_channel = MultiplexedApprovalChannel(telegram_ui=_telegram_ui)
            print("[FACTORY] Setting on llm_chat...", flush=True)
            llm_chat.set_approval_channel(_approval_channel)
            print(
                f"[FACTORY] Approval channel set! _approval_channel={_approval_channel}",
                flush=True,
            )

        return _telegram_ui

    return factory


# =============================================================================
# Integration
# =============================================================================

if BOT_TOKEN and CHAT_ID:
    print("[INIT] Setting up...", flush=True)
    llm_chat.set_ui_factory(create_ui_factory())
    print("[INIT] Ready!", flush=True)

    print(f"🤖 Telegram + CLI multiplexed UI for chat ID: {CHAT_ID}")
    print(f"   Chat from Telegram AND terminal!")
    print(f"   Both channels receive all responses.")
    print(f"   Approvals sent to both - first response wins!")
else:
    print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
