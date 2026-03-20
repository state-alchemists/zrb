"""
Telegram + CLI Dual UI/Approval for Zrb LLM Chat

This example demonstrates how to create a multiplexed UI that serves both
Telegram and CLI simultaneously using a SHARED message queue architecture.

## Architecture (Critical Understanding)

```
                    ┌──────────────────────────┐
                    │     MultiplexerUI        │
                    │  (extends BaseUI)        │
                    │                          │
                    │  ┌────────────────────┐  │
                    │  │ _message_queue      │  │  ◄── SINGLE SHARED QUEUE
                    │  │ _process_messages_  │  │
                    │  │ loop()              │  │
                    │  └────────────────────┘  │
                    │           ▲              │
                    │           │              │
                    │  _submit_user_message()   │
                    │           │              │
                    └───────────┼──────────────┘
                                │
              ┌─────────────────┴─────────────────┐
              │                                   │
    ┌─────────┴─────────┐           ┌───────────┴───────────┐
    │  TerminalChildUI  │           │  TelegramChildUI      │
    │  (NOT BaseUI)     │           │  (NOT BaseUI)         │
    │                   │           │                       │
    │  _multiplexer ────┼───────────┼───► _multiplexer     │
    │                   │           │                       │
    │  stdin ───────────┼──┐    ┌───┼─── Telegram message  │
    │                   │  │    │   │                       │
    └───────────────────┘  │    │   └───────────────────────┘
                           │    │
                    On user input, both call:
                    _multiplexer._submit_from_child(message)
                                 │
                                 ▼
                    MultiplexerUI._submit_user_message()
                                 │
                                 ▼
                    MultiplexerUI._message_queue.put_nowait(job)
```

## Key Insight

Both TerminalChildUI and TelegramChildUI are **NOT** BaseUI subclasses.
They are simple protocol implementations that:
- Receive input from their respective channels (stdin/Telegram)
- Forward ALL input to the shared MultiplexerUI via `_submit_from_child()`
- The MultiplexerUI handles command parsing, message queue, and LLM processing

This ensures ALL messages flow through a single queue, preventing race conditions
and ensuring only one LLM request runs at a time.

## Approval Architecture

```
MultiplexerApprovalChannel
    │
    ├── TerminalApprovalChannel (stdin prompts)
    └── TelegramApprovalChannel (inline buttons)

First response wins! If user approves from CLI, Telegram buttons are invalidated.
```

## Usage

    export TELEGRAM_BOT_TOKEN="your_token"
    export TELEGRAM_CHAT_ID="your_chat_id"
    zrb llm chat

The LLM will respond to BOTH Telegram AND terminal, and users can input from EITHER.
"""

import asyncio
import json
import os
import sys
from typing import Any, Callable

from zrb.context.any_context import AnyContext
from zrb.llm.app.base_ui import BaseUI
from zrb.llm.approval import ApprovalChannel, ApprovalContext, ApprovalResult
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.task.llm_task import LLMTask
from zrb.util.cli.style import remove_style

# =============================================================================
# Child UI Protocol - Interface for UI adapters
# =============================================================================


class ChildUIProtocol:
    """Protocol for child UIs attached to a MultiplexerUI.

    Child UIs are NOT BaseUI instances - they're simple adapters that:
    1. Receive input from their channel (stdin, Telegram, etc)
    2. Forward input to the multiplexer via _submit_from_child()
    3. Display output received via send_output()

    Crucially, child UIs do NOT have their own message queue or LLM processing.
    All that happens in the parent MultiplexerUI.
    """

    def send_output(self, message: str) -> None:
        """Display output to this UI channel."""
        ...

    async def ask_user(self, prompt: str) -> str:
        """Block and wait for user input from this channel."""
        ...


# =============================================================================
# Multiplexer UI - Single shared queue, multiple I/O channels
# =============================================================================


class MultiplexerUI(BaseUI):
    """BaseUI that broadcasts to multiple child UIs with a SHARED message queue.

    ARCHITECTURE:
    - Extends BaseUI → inherits _message_queue, _llm_task, _stream_ai_response
    - Child UIs are attached and call _submit_from_child() on user input
    - All child input routes through MultiplexerUI._submit_user_message()
    - All output broadcasts to every child UI via send_output()

    This ensures:
    - Single source of truth for LLM state
    - Only one LLM request at a time (queue serialization)
    - All channels see all responses
    """

    def __init__(
        self,
        ctx: AnyContext,
        yolo_xcom_key: str,
        assistant_name: str,
        llm_task: LLMTask,
        history_manager: AnyHistoryManager,
        child_uis: list[ChildUIProtocol] | None = None,
        primary_ui_index: int = 0,
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
        # Child UIs for input/output (NOT BaseUI instances!)
        self.child_uis: list[ChildUIProtocol] = child_uis or []
        # Primary UI index: which child handles ask_user() prompts
        self.primary_ui_index = primary_ui_index
        # Output buffer for batching
        self._output_buffer: list[str] = []
        self._flush_task: asyncio.Task | None = None
        # Child listener tasks (for Telegram polling, etc)
        self._child_tasks: list[asyncio.Task] = []

    @property
    def primary_ui(self) -> ChildUIProtocol | None:
        """Get the primary UI for ask_user prompts."""
        if 0 <= self.primary_ui_index < len(self.child_uis):
            return self.child_uis[self.primary_ui_index]
        return None

    # =========================================================================
    # Child Input Routing - Called by child UIs when user sends input
    # =========================================================================

    def _submit_from_child(self, child_ui: ChildUIProtocol, message: str) -> None:
        """Called by child UIs when user sends a message.

        This is THE KEY METHOD that merges all input channels.
        All child UIs call this method, which routes through
        MultiplexerUI._submit_user_message() to the shared queue.

        Args:
            child_ui: The child UI that received the input (unused, for logging)
            message: The user message received from the child UI
        """
        # Check for commands first (handled by BaseUI)
        if self._handle_exit_command(message):
            return
        if self._handle_info_command(message):
            return
        if self._handle_save_command(message):
            return
        if self._handle_load_command(message):
            return
        if self._handle_redirect_command(message):
            return
        if self._handle_attach_command(message):
            return
        if self._handle_toggle_yolo(message):
            return
        if self._handle_set_model_command(message):
            return
        if self._handle_exec_command(message):
            return
        if self._handle_custom_command(message):
            return

        # Route through the shared queue - this is where magic happens
        # _submit_user_message is defined in BaseUI and uses self._message_queue
        self._submit_user_message(self._llm_task, message)

    # =========================================================================
    # BaseUI Abstract Method Implementations - Broadcast to all children
    # =========================================================================

    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file=None,
        flush: bool = False,
    ) -> None:
        """Buffer output for broadcasting to all child UIs."""
        self._output_buffer.append(sep.join(str(v) for v in values) + end)
        if flush:
            asyncio.create_task(self.flush_output())

    def stream_to_parent(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file=None,
        flush: bool = False,
    ) -> None:
        """Stream immediately to all child UIs (no buffering)."""
        msg = sep.join(str(v) for v in values) + end
        self._broadcast_to_children(msg)

    async def ask_user(self, prompt: str) -> str:
        """Ask via primary UI, but broadcast prompt to all children."""
        # Broadcast prompt to all UIs
        for child in self.child_uis:
            try:
                child.send_output(f"\n❓ {prompt}\n")
            except Exception:
                pass

        # Only primary UI waits for response
        if self.primary_ui:
            return await self.primary_ui.ask_user(prompt)
        return ""

    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
        """Disabled in multiplexer mode for security."""
        self._broadcast_to_children(
            "⚠️ Command execution disabled in multiplexer mode\n"
        )
        return {"error": "Disabled"}

    # =========================================================================
    # Output Broadcasting
    # =========================================================================

    def _broadcast_to_children(self, message: str) -> None:
        """Send message to all child UIs immediately."""
        for child in self.child_uis:
            try:
                child.send_output(message)
            except Exception:
                pass  # Don't let one child failure break others

    async def flush_output(self) -> None:
        """Flush buffered output to all children."""
        if self._output_buffer:
            msg = "".join(self._output_buffer)
            self._output_buffer = []
            self._broadcast_to_children(msg)

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def run_async(self) -> None:
        """Run the multiplexer - start all child listeners and process queue."""
        # Start child UI listeners (e.g., Telegram polling)
        for child in self.child_uis:
            if hasattr(child, "start_listener"):
                task = asyncio.create_task(child.start_listener(self))
                self._child_tasks.append(task)

        # Start the inherited BaseUI message processor
        # This processes jobs from self._message_queue
        self._process_messages_task = asyncio.create_task(self._process_messages_loop())

        # Start output flush loop
        self._flush_task = asyncio.create_task(self._flush_loop())

        # Send initial message if any
        if self._initial_message:
            self._submit_user_message(self._llm_task, self._initial_message)

        try:
            # Keep running until cancelled
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            # Cleanup
            for task in self._child_tasks:
                task.cancel()
            if self._process_messages_task:
                self._process_messages_task.cancel()
            if self._flush_task:
                self._flush_task.cancel()
            await self.shutdown()

    async def _flush_loop(self) -> None:
        """Periodically flush buffered output."""
        while True:
            await asyncio.sleep(0.3)
            await self.flush_output()

    def on_exit(self) -> None:
        """Handle exit - notify all children."""
        self._broadcast_to_children("Shutting down... 👋\n")
        for child in self.child_uis:
            if hasattr(child, "on_exit"):
                try:
                    child.on_exit()
                except Exception:
                    pass

    async def shutdown(self) -> None:
        """Shutdown all child UIs."""
        for child in self.child_uis:
            if hasattr(child, "shutdown"):
                try:
                    await child.shutdown()
                except Exception:
                    pass


# =============================================================================
# Terminal Child UI - Simple stdin/stdout adapter
# =============================================================================


class TerminalChildUI(ChildUIProtocol):
    """Child UI for terminal I/O.

    This is NOT a BaseUI - it's a simple adapter that:
    - Prints output to terminal (send_output)
    - Reads from stdin in a loop (start_listener)
    - Forwards user input to the multiplexer
    - Has NO message queue or LLM processing

    The stdin reader loop runs in start_listener(), similar to how
    TelegramChildUI has _handle_message triggered by bot polling.
    """

    def __init__(self):
        self._multiplexer: MultiplexerUI | None = None
        self._stdin_task: asyncio.Task | None = None
        self._running = True

    def attach_to_multiplexer(self, multiplexer: MultiplexerUI) -> None:
        """Set reference to parent multiplexer."""
        self._multiplexer = multiplexer

    def send_output(self, message: str) -> None:
        """Print to terminal immediately."""
        print(message, end="", flush=True)

    async def start_listener(self, multiplexer: MultiplexerUI) -> None:
        """Start stdin reader loop - called by MultiplexerUI.run_async().

        This is the KEY for terminal input! We continuously read from stdin
        and forward to the multiplexer, just like Telegram does with _handle_message.
        """
        self._multiplexer = multiplexer
        loop = asyncio.get_event_loop()

        print("\n💬 Terminal ready. Type your message (or /info for help):\n")

        while self._running:
            try:
                # Read from stdin asynchronously
                line = await loop.run_in_executor(None, input, "")

                if not self._running:
                    break

                # Forward to multiplexer - this routes through the shared queue!
                if self._multiplexer and line.strip():
                    self._multiplexer._submit_from_child(self, line.strip())

            except EOFError:
                # stdin closed (e.g., piped input ended)
                break
            except asyncio.CancelledError:
                break
            except Exception:
                # Log error but continue
                import traceback

                traceback.print_exc()
                continue

    async def ask_user(self, prompt: str) -> str:
        """Read from stdin asynchronously (blocks until input)."""
        if prompt:
            print(f"\n❓ {prompt}")
        print("> ", end="", flush=True)
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, input, "")
            return response.strip()
        except EOFError:
            return ""
        except asyncio.CancelledError:
            return ""

    def on_exit(self) -> None:
        """Handle exit."""
        self._running = False
        print("\n👋 Goodbye!")

    async def shutdown(self) -> None:
        """Stop stdin reader."""
        self._running = False
        if self._stdin_task and not self._stdin_task.done():
            self._stdin_task.cancel()


# =============================================================================
# Telegram Child UI - Telegram bot adapter
# =============================================================================


class TelegramChildUI(ChildUIProtocol):
    """Child UI for Telegram bot I/O.

    This is NOT a BaseUI - it's a simple adapter that:
    - Sends output to Telegram chat (send_output)
    - Receives messages via Telegram bot API (start_listener)
    - Forwards received messages to the multiplexer

    The Telegram polling runs in start_listener(), which is called
    by MultiplexerUI.run_async().

    Note: Output is buffered and flushed periodically to avoid
    sending many small fragmented messages.
    """

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        timeout: int = 300,
        flush_interval: float = 0.5,
    ):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.timeout = timeout
        self.flush_interval = flush_interval
        self._bot = None
        self._application = None
        self._multiplexer: MultiplexerUI | None = None
        # For pending ask_user responses
        self._pending_questions: dict[str, asyncio.Future[str]] = {}
        # Buffer for output (to avoid fragmentation)
        self._buffer: list[str] = []
        self._flush_task: asyncio.Task | None = None

    def attach_to_multiplexer(self, multiplexer: MultiplexerUI) -> None:
        """Set reference to parent multiplexer."""
        self._multiplexer = multiplexer

    async def start_listener(self, multiplexer: MultiplexerUI) -> None:
        """Start Telegram bot polling - called by MultiplexerUI.run_async()."""
        self._multiplexer = multiplexer
        await self._ensure_bot()
        # Start flush loop for buffered output
        self._flush_task = asyncio.create_task(self._flush_loop())
        # Bot starts polling in _ensure_bot, this task just keeps running

    async def _flush_loop(self) -> None:
        """Periodically flush buffered output to Telegram."""
        while True:
            await asyncio.sleep(self.flush_interval)
            await self._flush_buffer()

    async def _flush_buffer(self) -> None:
        """Send buffered output to Telegram."""
        if not self._buffer:
            return
        msg = "".join(self._buffer)
        self._buffer = []
        await self._send_message(msg)

    async def _send_message(self, msg: str) -> None:
        """Send a message to Telegram (internal method)."""
        await self._ensure_bot()
        # Remove ANSI codes for Telegram
        clean_msg = remove_style(msg)
        if not clean_msg.strip():
            return
        # Truncate if too long
        if len(clean_msg) > 4000:
            clean_msg = clean_msg[:3997] + "..."
        await self._bot.send_message(chat_id=self.chat_id, text=clean_msg)

    async def _ensure_bot(self) -> None:
        """Initialize and start Telegram bot."""
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

    async def _handle_message(self, update, context) -> None:
        """Handle incoming Telegram message - forward to multiplexer."""
        text = update.message.text
        if not text:
            return

        # Check if this is a response to a pending question
        for qid, future in list(self._pending_questions.items()):
            if not future.done():
                future.set_result(text)
                self._pending_questions.pop(qid, None)
                return

        # Forward to multiplexer - this routes through the shared queue!
        if self._multiplexer:
            self._multiplexer._submit_from_child(self, text)

    def send_output(self, message: str) -> None:
        """Buffer output for batching (Telegram has rate limits)."""
        self._buffer.append(message)

    async def ask_user(self, prompt: str) -> str:
        """Ask via Telegram and wait for response."""
        await self._ensure_bot()
        # Flush any pending output first
        await self._flush_buffer()
        await self._bot.send_message(chat_id=self.chat_id, text=f"❓ {prompt}")

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

    async def shutdown(self) -> None:
        """Stop Telegram bot."""
        # Flush any remaining buffer
        await self._flush_buffer()
        # Cancel flush task
        if self._flush_task:
            self._flush_task.cancel()
        # Stop bot
        if self._application:
            await self._application.updater.stop()
            await self._application.stop()
            await self._application.shutdown()


# =============================================================================
# Multiplexer Approval Channel - First response wins
# =============================================================================


class MultiplexerApprovalChannel(ApprovalChannel):
    """Approval channel that broadcasts to multiple channels.

    Approval requests go to ALL channels simultaneously.
    The FIRST response (approve or deny) wins.
    """

    def __init__(self, channels: list[ApprovalChannel], timeout: int = 300):
        self.channels = channels
        self.timeout = timeout

    async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
        """Request approval from all channels. First response wins."""
        loop = asyncio.get_event_loop()
        result_future: asyncio.Future[ApprovalResult] = loop.create_future()

        async def channel_request(channel: ApprovalChannel) -> None:
            """Request from one channel."""
            try:
                result = await channel.request_approval(context)
                if not result_future.done():
                    result_future.set_result(result)
            except asyncio.CancelledError:
                raise
            except Exception:
                pass  # Don't let one channel failure break others

        # Start all requests concurrently
        tasks = [asyncio.create_task(channel_request(ch)) for ch in self.channels]

        try:
            async with asyncio.timeout(self.timeout):
                return await result_future
        except asyncio.TimeoutError:
            return ApprovalResult(approved=False, message="Timeout")
        finally:
            # Cancel any pending requests
            for task in tasks:
                if not task.done():
                    task.cancel()

    async def notify(
        self, message: str, context: ApprovalContext | None = None
    ) -> None:
        """Broadcast notification to all channels."""
        for channel in self.channels:
            try:
                await channel.notify(message, context)
            except Exception:
                pass


# =============================================================================
# Telegram Approval Channel - Inline buttons
# =============================================================================


class TelegramApprovalChannel(ApprovalChannel):
    """Approval channel for Telegram with inline keyboard buttons."""

    def __init__(self, bot_token: str, chat_id: str, timeout: int = 300):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.timeout = timeout
        self._bot = None
        self._application = None
        self._pending_approvals: dict[str, asyncio.Future[ApprovalResult]] = {}

    async def _ensure_bot(self) -> None:
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

    async def _handle_callback(self, update, context) -> None:
        """Handle inline button callback."""
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

    async def notify(
        self, message: str, context: ApprovalContext | None = None
    ) -> None:
        await self._ensure_bot()
        await self._bot.send_message(chat_id=self.chat_id, text=message)

    async def shutdown(self) -> None:
        if self._application:
            await self._application.updater.stop()
            await self._application.stop()
            await self._application.shutdown()


# =============================================================================
# Terminal Approval Channel - stdin prompts
# =============================================================================


class TerminalApprovalChannel(ApprovalChannel):
    """Approval channel using terminal input."""

    def __init__(self, get_input: Callable[[], str] | None = None):
        self._get_input = get_input or (lambda: input("> "))

    async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
        args_str = json.dumps(context.tool_args, indent=2, default=str)
        print(f"\n🔔 Tool Approval Request")
        print(f"Tool: {context.tool_name}")
        print(f"Arguments:\n{args_str}")
        print("\nApprove? [Y/n] ", end="", flush=True)

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, self._get_input)
            response = response.strip().lower()

            if response in ("y", "yes", "", "ok", "approve"):
                return ApprovalResult(approved=True)
            return ApprovalResult(approved=False, message=f"User denied: {response}")
        except Exception as e:
            return ApprovalResult(approved=False, message=str(e))

    async def notify(
        self, message: str, context: ApprovalContext | None = None
    ) -> None:
        print(message)


# =============================================================================
# Factory Function
# =============================================================================


def create_multiplexed_ui(
    ctx: AnyContext,
    llm_task_core: LLMTask,
    history_manager: AnyHistoryManager,
    ui_commands: dict,
    initial_message: str | None,
    initial_conversation_name: str | None,
    initial_yolo: bool,
    initial_attachments: list,
    telegram_bot_token: str | None = None,
    telegram_chat_id: str | None = None,
    enable_cli: bool = True,
    primary_channel: str = "cli",  # "cli" or "telegram"
) -> MultiplexerUI:
    """Create a multiplexed UI with both Telegram and CLI.

    Args:
        ctx: Task context
        llm_task_core: The LLM task
        history_manager: Conversation history manager
        ui_commands: Command configurations dict
        initial_message: Initial message to send
        initial_conversation_name: Conversation name
        initial_yolo: YOLO mode flag
        initial_attachments: Attached files
        telegram_bot_token: Telegram bot token (optional)
        telegram_chat_id: Telegram chat ID (optional)
        enable_cli: Whether to enable CLI UI
        primary_channel: Which channel handles ask_user prompts

    Returns:
        Configured MultiplexerUI with child UIs attached
    """
    # Create child UIs list
    child_uis: list[ChildUIProtocol] = []
    primary_index = 0

    # Add CLI child UI first (index 0) if enabled
    if enable_cli:
        terminal_ui = TerminalChildUI()
        child_uis.append(terminal_ui)
        if primary_channel == "cli":
            primary_index = len(child_uis) - 1

    # Add Telegram child UI second (index 1) if configured
    telegram_ui = None
    if telegram_bot_token and telegram_chat_id:
        telegram_ui = TelegramChildUI(
            bot_token=telegram_bot_token,
            chat_id=telegram_chat_id,
        )
        child_uis.append(telegram_ui)
        if primary_channel == "telegram":
            primary_index = len(child_uis) - 1

    # Create the multiplexer (inherits _message_queue from BaseUI)
    multiplexer = MultiplexerUI(
        ctx=ctx,
        yolo_xcom_key="yolo",
        assistant_name="Zrb Assistant",
        llm_task=llm_task_core,
        history_manager=history_manager,
        child_uis=child_uis,
        primary_ui_index=primary_index,
        initial_message=initial_message,
        conversation_session_name=initial_conversation_name,
        initial_attachments=initial_attachments,
        yolo=initial_yolo,
        summarize_commands=ui_commands.get("summarize", []),
        attach_commands=ui_commands.get("attach", []),
        exit_commands=ui_commands.get("exit", []),
        info_commands=ui_commands.get("info", []),
        save_commands=ui_commands.get("save", []),
        load_commands=ui_commands.get("load", []),
        yolo_toggle_commands=ui_commands.get("yolo_toggle", []),
        set_model_commands=ui_commands.get("set_model", []),
        redirect_output_commands=ui_commands.get("redirect_output", []),
        exec_commands=ui_commands.get("exec", []),
    )

    # Attach multiplexer reference to each child UI
    for child in child_uis:
        if hasattr(child, "attach_to_multiplexer"):
            child.attach_to_multiplexer(multiplexer)

    return multiplexer


# =============================================================================
# Integration with llm_chat task
# =============================================================================

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

if BOT_TOKEN and CHAT_ID:
    from zrb.builtin.llm.chat import llm_chat

    # Create approval channels for both Telegram and CLI
    telegram_approval = TelegramApprovalChannel(bot_token=BOT_TOKEN, chat_id=CHAT_ID)
    terminal_approval = TerminalApprovalChannel()

    # Multiplexer approval: first response wins
    multiplexer_approval = MultiplexerApprovalChannel(
        channels=[terminal_approval, telegram_approval],
    )

    def create_dual_ui(
        ctx,
        llm_task_core,
        history_manager,
        ui_commands,
        initial_message,
        initial_conversation_name,
        initial_yolo,
        initial_attachments,
    ):
        """Factory function for multiplexed Telegram + CLI UI."""
        return create_multiplexed_ui(
            ctx=ctx,
            llm_task_core=llm_task_core,
            history_manager=history_manager,
            ui_commands=ui_commands,
            initial_message=initial_message,
            initial_conversation_name=initial_conversation_name,
            initial_yolo=initial_yolo,
            initial_attachments=initial_attachments,
            telegram_bot_token=BOT_TOKEN,
            telegram_chat_id=CHAT_ID,
            enable_cli=True,
            primary_channel="cli",  # CLI handles ask_user by default
        )

    llm_chat.set_ui_factory(create_dual_ui)
    llm_chat.set_approval_channel(multiplexer_approval)

    print(f"🤖 Telegram + CLI multiplexed UI for chat ID: {CHAT_ID}")
    print("   Chat from Telegram AND terminal!")
    print("   Both channels receive all responses.")
    print("   Approvals sent to both - first response wins!")
else:
    print(
        "⚠️  Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID "
        "environment variables."
    )
