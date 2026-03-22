"""
Telegram + CLI Dual UI - Multiplexer Architecture

This implements Level 3: MultiplexerUI (multi-channel support)
- Both CLI and Telegram receive output
- Input accepted from EITHER channel
- Shared message queue (serialized execution)
- Multiplexed approvals (first response wins)

Architecture:
                    ┌──────────────────────────┐
                    │     MultiplexerUI        │
                    │  (extends BaseUI)        │
                    │                          │
                    │  ┌────────────────────┐  │
                    │  │ _message_queue     │  │  ◄── SINGLE SHARED QUEUE
                    │  └────────────────────┘  │
                    │           ▲              │
                    │  _submit_user_message()  │
                    └───────────┼──────────────┘
                                │
              ┌─────────────────┴─────────────────┐
              │                                   │
    ┌─────────┴─────────┐           ┌───────────┴───────────┐
    │  TerminalChildUI  │           │  TelegramChildUI      │
    │  (stdin/stdout)   │           │  (bot polling)        │
    └───────────────────┘           └───────────────────────┘

Usage:
    export TELEGRAM_BOT_TOKEN="your-token"
    export TELEGRAM_CHAT_ID="your-chat-id"
    zrb llm chat
"""

import asyncio
import json
import os
from typing import Protocol, runtime_checkable

from zrb.builtin.llm.chat import llm_chat
from zrb.llm.app.base_ui import BaseUI
from zrb.llm.approval import ApprovalChannel, ApprovalContext, ApprovalResult
from zrb.util.cli.style import remove_style

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


# ─────────────────────────────────────────────────────────────────────────────
# Child UI Protocol - Thin adapters (NOT BaseUI)
# ─────────────────────────────────────────────────────────────────────────────


@runtime_checkable
class ChildUIProtocol(Protocol):
    """Protocol for child UIs - thin adapters for different channels."""

    def send_output(self, message: str) -> None:
        """Display output to this channel."""
        ...

    async def ask_user(self, prompt: str) -> str:
        """Get input from this channel (may raise if channel can't prompt)."""
        ...


class TerminalChildUI:
    """Terminal adapter - reads from stdin, writes to stdout."""

    def __init__(self):
        self._input_queue: asyncio.Queue[str] = asyncio.Queue()
        self._loop = asyncio.get_event_loop()

    def send_output(self, message: str) -> None:
        """Print to terminal."""
        print(message, end="", flush=True)

    async def ask_user(self, prompt: str) -> str:
        """Read from stdin."""
        print(f"\n❓ {prompt}")
        print("> ", end="", flush=True)
        try:
            return await self._loop.run_in_executor(None, input)
        except EOFError:
            return ""

    def submit_input(self, message: str) -> None:
        """Called when input arrives from terminal."""
        # This would be used if we had async stdin reading
        pass


class TelegramChildUI:
    """Telegram adapter - uses bot polling for input."""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._bot = None
        self._app = None
        self._input_queue: asyncio.Queue[str] = asyncio.Queue()
        # Buffering for output
        self._buffer: list[str] = []
        self._flush_interval = 0.5
        self._flush_task: asyncio.Task | None = None

    async def start(self):
        """Start the Telegram bot."""
        if self._bot:
            return
        from telegram.ext import Application

        self._app = Application.builder().token(self.bot_token).build()
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling()
        self._bot = self._app.bot
        # Start flush loop
        self._flush_task = asyncio.create_task(self._flush_loop())

    def send_output(self, message: str) -> None:
        """Buffer output for Telegram (async flush)."""
        clean = remove_style(message).strip()
        if clean:
            self._buffer.append(clean)
            # Flush when large
            if len(self._buffer) > 50 or sum(len(s) for s in self._buffer) > 1000:
                asyncio.create_task(self._flush_buffer())

    async def _flush_loop(self):
        """Periodically flush buffer."""
        while True:
            await asyncio.sleep(self._flush_interval)
            if self._buffer:
                await self._flush_buffer()

    async def _flush_buffer(self):
        """Send buffered content."""
        if not self._buffer or not self._bot:
            return
        content = "\n".join(self._buffer)
        self._buffer = []
        for chunk in self._split(content, 4000):
            await self._bot.send_message(chat_id=self.chat_id, text=chunk)

    async def send_immediate(self, message: str, **kwargs):
        """Send immediately (for prompts, approvals)."""
        if not self._bot:
            await self.start()
        clean = remove_style(message).strip()
        if clean:
            await self._bot.send_message(
                chat_id=self.chat_id, text=clean[:4000], **kwargs
            )

    async def flush(self):
        """Manually flush buffer."""
        if self._buffer:
            await self._flush_buffer()

    async def ask_user(self, prompt: str) -> str:
        """Wait for input from Telegram."""
        await self.send_immediate(
            f"❓ {prompt}\n\n_Reply to this message._", parse_mode="Markdown"
        )
        return await self._input_queue.get()

    def submit_input(self, message: str) -> None:
        """Called when Telegram message arrives."""
        self._input_queue.put_nowait(message)

    @staticmethod
    def _split(text: str, max_len: int) -> list[str]:
        if len(text) <= max_len:
            return [text]
        return [text[i : i + max_len] for i in range(0, len(text), max_len)]


# ─────────────────────────────────────────────────────────────────────────────
# Multiplexer UI - Main UI with shared queue
# ─────────────────────────────────────────────────────────────────────────────


class MultiplexerUI(BaseUI):
    """Main UI that multiplexes to multiple child UIs.

    - Extends BaseUI (has _message_queue)
    - Broadcasts output to ALL children
    - Accepts input from ANY child (via _submit_from_child)
    - Single shared queue for serialized execution
    """

    def __init__(self, child_uis: list[ChildUIProtocol], **kwargs):
        super().__init__(**kwargs)
        self.child_uis = child_uis
        self._primary_ui = child_uis[0] if child_uis else None

    def _submit_from_child(self, child_ui: ChildUIProtocol, message: str):
        """Called by child UIs when they receive input.

        Routes through the shared message queue via _submit_user_message().
        """
        self._submit_user_message(self._llm_task, message)

    # Required: Broadcast to ALL children
    def append_to_output(self, *values, sep=" ", end="\n", **kwargs):
        message = sep.join(str(v) for v in values) + end
        for child_ui in self.child_uis:
            child_ui.send_output(message)

    # Required: Ask on primary UI
    async def ask_user(self, prompt: str) -> str:
        # Broadcast prompt to all children
        for child_ui in self.child_uis:
            if hasattr(child_ui, "send_output"):
                child_ui.send_output(f"\n❓ {prompt}\n")

        # Wait for input from primary
        if self._primary_ui:
            return await self._primary_ui.ask_user(prompt)
        raise RuntimeError("No primary UI for input")

    # Required: Shell commands via primary
    async def run_interactive_command(self, cmd, shell=False):
        if hasattr(self._primary_ui, "send_output"):
            self._primary_ui.send_output(f"⚙️ Running: {cmd}\n")
        # Delegate to primary UI's implementation if available
        return 0

    # Required: Run async loop
    async def run_async(self) -> str:
        # Start all child UIs that need async initialization
        for child_ui in self.child_uis:
            if hasattr(child_ui, "start"):
                await child_ui.start()

        # Start message processing
        self._process_messages_task = asyncio.create_task(self._process_messages_loop())

        if self._initial_message:
            self._submit_user_message(self._llm_task, self._initial_message)

        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            # Flush any pending output
            for child_ui in self.child_uis:
                if hasattr(child_ui, "flush"):
                    await child_ui.flush()
            self._process_messages_task.cancel()
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# Telegram Handler Registration
# ─────────────────────────────────────────────────────────────────────────────

_telegram_child: TelegramChildUI | None = None
_multiplexer: MultiplexerUI | None = None


async def setup_telegram_handler(child_ui: TelegramChildUI, multiplexer: MultiplexerUI):
    """Register message handler for Telegram child UI."""
    global _telegram_child, _multiplexer
    _telegram_child = child_ui
    _multiplexer = multiplexer

    await child_ui.start()

    if not child_ui._app:
        return

    from telegram.ext import MessageHandler, filters

    async def handle_message(update, context):
        """Forward Telegram messages to multiplexer."""
        text = update.message.text
        # Route through multiplexer's shared queue
        multiplexer._submit_from_child(child_ui, text)

    child_ui._app.add_handler(MessageHandler(filters.TEXT, handle_message))


async def setup_cli_input(child_ui: TerminalChildUI, multiplexer: MultiplexerUI):
    """Read from CLI and forward to multiplexer."""
    loop = asyncio.get_event_loop()

    async def cli_loop():
        while True:
            try:
                line = await loop.run_in_executor(None, input)
                if line.strip():
                    multiplexer._submit_from_child(child_ui, line.strip())
            except EOFError:
                break
            except asyncio.CancelledError:
                break

    asyncio.create_task(cli_loop())


# ─────────────────────────────────────────────────────────────────────────────
# Multiplexed Approval - Broadcasts to ALL channels
# ─────────────────────────────────────────────────────────────────────────────


class MultiplexerApprovalChannel(ApprovalChannel):
    """Approval channel that broadcasts to multiple sub-channels.

    First response wins - if user approves from CLI, Telegram button is invalidated.
    """

    def __init__(self, channels: list[ApprovalChannel]):
        self.channels = channels
        self._pending: dict[str, asyncio.Future] = {}

    async def request_approval(self, ctx: ApprovalContext) -> ApprovalResult:
        # Create a shared future for all channels
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._pending[ctx.tool_call_id] = future

        # Request from all channels concurrently
        async def request_from_channel(channel: ApprovalChannel):
            try:
                result = await channel.request_approval(ctx)
                if not future.done():
                    future.set_result(result)
                return result
            except Exception as e:
                if not future.done():
                    future.set_result(ApprovalResult(approved=False, message=str(e)))
                return ApprovalResult(approved=False, message=str(e))

        # Start all requests
        tasks = [asyncio.create_task(request_from_channel(ch)) for ch in self.channels]

        try:
            # Wait for first response (with timeout)
            async with asyncio.timeout(300):
                result = await future
            return result
        except asyncio.TimeoutError:
            return ApprovalResult(approved=False, message="Timeout")
        finally:
            # Cancel pending tasks
            for task in tasks:
                task.cancel()
            self._pending.pop(ctx.tool_call_id, None)

    async def notify(self, msg: str, ctx=None):
        """Broadcast notification to all channels."""
        for channel in self.channels:
            try:
                await channel.notify(msg, ctx)
            except:
                pass  # Don't fail if one channel fails


class TerminalApprovalChannel(ApprovalChannel):
    """Simple terminal-based approval."""

    async def request_approval(self, ctx: ApprovalContext) -> ApprovalResult:
        print(f"\n🔔 Tool: {ctx.tool_name}")
        print(f"Arguments: {json.dumps(ctx.tool_args, indent=2, default=str)[:500]}")
        print("Approve? [Y/n] ", end="", flush=True)

        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(None, input)
            approved = response.strip().lower() in ("", "y", "yes")
            return ApprovalResult(approved=approved)
        except:
            return ApprovalResult(approved=False)

    async def notify(self, msg: str, ctx=None):
        print(f"📢 {msg}")


class TelegramApprovalChannel(ApprovalChannel):
    """Telegram approval via inline buttons."""

    def __init__(self, child_ui: TelegramChildUI):
        self.child_ui = child_ui
        self._pending: dict[str, asyncio.Future] = {}
        self._handler_added = False

    async def _ensure_handler(self):
        """Register callback handler for button presses."""
        if self._handler_added or not self.child_ui._app:
            return

        from telegram.ext import CallbackQueryHandler

        async def handle_callback(update, context):
            query = update.callback_query
            await query.answer()
            action, tool_call_id = query.data.split(":", 1)
            approved = action == "yes"

            if tool_call_id in self._pending:
                self._pending.pop(tool_call_id).set_result(
                    ApprovalResult(approved=approved)
                )

            await query.edit_message_text(
                f"{'✅ Approved' if approved else '❌ Denied'}"
            )

        self.child_ui._app.add_handler(CallbackQueryHandler(handle_callback))
        self._handler_added = True

    async def request_approval(self, ctx: ApprovalContext) -> ApprovalResult:
        await self._ensure_handler()
        await self.child_ui.flush()  # Flush pending output before prompt

        # Create future for this approval
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._pending[ctx.tool_call_id] = future

        # Send approval request with buttons
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        args_str = json.dumps(ctx.tool_args, indent=2, default=str)[:500]

        await self.child_ui.send_immediate(
            f"🔔 *Tool*: `{ctx.tool_name}`\n```\n{args_str}\n```",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "✅ Approve", callback_data=f"yes:{ctx.tool_call_id}"
                        ),
                        InlineKeyboardButton(
                            "❌ Deny", callback_data=f"no:{ctx.tool_call_id}"
                        ),
                    ]
                ]
            ),
        )

        # Wait for response (may be set by callback or by multiplexer)
        try:
            async with asyncio.timeout(300):
                return await future
        except asyncio.TimeoutError:
            self._pending.pop(ctx.tool_call_id, None)
            return ApprovalResult(approved=False, message="Timeout")

    async def notify(self, msg: str, ctx=None):
        await self.child_ui.send_immediate(msg)


# ─────────────────────────────────────────────────────────────────────────────
# Integration with zrb llm chat
# ─────────────────────────────────────────────────────────────────────────────

if BOT_TOKEN and CHAT_ID:
    # Create child UIs
    telegram_child = TelegramChildUI(BOT_TOKEN, CHAT_ID)
    terminal_child = TerminalChildUI()

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
        global _multiplexer

        multiplexer = MultiplexerUI(
            child_uis=[terminal_child, telegram_child],
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
        _multiplexer = multiplexer

        # Setup async handlers
        asyncio.create_task(setup_telegram_handler(telegram_child, multiplexer))
        asyncio.create_task(setup_cli_input(terminal_child, multiplexer))

        return multiplexer

    # Setup approval channels
    terminal_approval = TerminalApprovalChannel()
    telegram_approval = TelegramApprovalChannel(telegram_child)
    multiplexed_approval = MultiplexerApprovalChannel(
        [terminal_approval, telegram_approval]
    )

    llm_chat.set_ui_factory(create_ui)
    llm_chat.set_approval_channel(multiplexed_approval)

    print(f"🤖 Telegram + CLI multiplexed UI for chat ID: {CHAT_ID}")
    print(f"   Chat from Telegram AND terminal!")
    print(f"   Both channels receive all responses.")
    print(f"   Approvals sent to both - first response wins!")
else:
    print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
