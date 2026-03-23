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
import sys
from typing import Protocol, runtime_checkable

from zrb.builtin.llm.chat import llm_chat
from zrb.llm.app.base_ui import BaseUI
from zrb.llm.approval import ApprovalChannel, ApprovalContext, ApprovalResult
from zrb.util.cli.style import remove_style

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL SHUTDOWN FLAG - Used across all async tasks for clean exit
# ─────────────────────────────────────────────────────────────────────────────

_shutdown_requested = False


def is_shutdown_requested() -> bool:
    """Check if shutdown has been requested."""
    return _shutdown_requested


def request_shutdown():
    """Request shutdown from all components."""
    global _shutdown_requested
    _shutdown_requested = True


# ─────────────────────────────────────────────────────────────────────────────
# Child UI Protocol - Thin adapters for output only
# ─────────────────────────────────────────────────────────────────────────────


@runtime_checkable
class ChildUIProtocol(Protocol):
    """Protocol for child UIs - thin output adapters."""

    def send_output(self, message: str) -> None:
        """Display output to this channel."""
        ...


class TerminalChildUI:
    """Terminal adapter - writes to stdout."""

    def __init__(self):
        self._loop = asyncio.get_event_loop()

    def send_output(self, message: str) -> None:
        """Print to terminal."""
        print(message, end="", flush=True)

    async def flush(self):
        """Flush terminal output."""
        sys.stdout.flush()


class TelegramChildUI:
    """Telegram adapter with buffered output."""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._bot = None
        self._app = None
        self._buffer: list[str] = []
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
        self._flush_task = asyncio.create_task(self._flush_loop())

    async def stop(self):
        """Stop the Telegram bot and cleanup - fast shutdown."""
        # Cancel flush task first
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except (asyncio.CancelledError, KeyboardInterrupt):
                pass
        
        # Skip buffer flush during shutdown (not critical)
        
        # Stop the app with fast timeouts (shutdown speed matters more than graceful)
        if self._app:
            try:
                async with asyncio.timeout(1.0):
                    await self._app.updater.stop()
            except (asyncio.CancelledError, KeyboardInterrupt, asyncio.TimeoutError):
                pass
            
            try:
                async with asyncio.timeout(0.5):
                    await self._app.stop()
            except (asyncio.CancelledError, KeyboardInterrupt, asyncio.TimeoutError):
                pass
            
            try:
                async with asyncio.timeout(0.5):
                    await self._app.shutdown()
            except (asyncio.CancelledError, KeyboardInterrupt, asyncio.TimeoutError):
                pass

    def send_output(self, message: str) -> None:
        """Buffer output for Telegram."""
        if is_shutdown_requested():
            return  # Don't buffer during shutdown
        self._buffer.append(message)
        if len(self._buffer) > 100 or sum(len(s) for s in self._buffer) > 4000:
            asyncio.create_task(self._flush_buffer())

    async def _flush_loop(self):
        """Periodically flush buffer."""
        while not is_shutdown_requested():
            try:
                await asyncio.sleep(0.5)
                if self._buffer and not is_shutdown_requested():
                    await self._flush_buffer()
            except asyncio.CancelledError:
                break
            except KeyboardInterrupt:
                break
        # Final flush on exit (only if not shutting down)
        if self._buffer and not is_shutdown_requested():
            try:
                await self._flush_buffer()
            except (asyncio.CancelledError, KeyboardInterrupt):
                pass

    async def _flush_buffer(self):
        """Send buffered content as single message."""
        if not self._buffer or not self._bot:
            return
        if is_shutdown_requested():
            return  # Don't send during shutdown
        content = remove_style("".join(self._buffer)).strip()
        self._buffer = []
        if not content:
            return
        for chunk in self._split(content, 4000):
            await self._bot.send_message(chat_id=self.chat_id, text=chunk)

    async def send_immediate(self, message: str, **kwargs):
        """Send immediately (for prompts, approvals)."""
        if is_shutdown_requested():
            return
        if not self._bot:
            await self.start()
        clean = remove_style(message).strip()
        if clean:
            for chunk in self._split(clean, 4000):
                await self._bot.send_message(chat_id=self.chat_id, text=chunk, **kwargs)

    async def flush(self):
        """Manually flush buffer."""
        if self._buffer:
            await self._flush_buffer()

    @staticmethod
    def _split(text: str, max_len: int) -> list[str]:
        if len(text) <= max_len:
            return [text]
        return [text[i : i + max_len] for i in range(0, len(text), max_len)]


# ─────────────────────────────────────────────────────────────────────────────
# Multiplexer UI - Main UI with shared queue
# ─────────────────────────────────────────────────────────────────────────────


class MultiplexerUI(BaseUI):
    """Main UI that multiplexes to multiple child UIs."""

    def __init__(self, child_uis: list[ChildUIProtocol], **kwargs):
        super().__init__(**kwargs)
        self.child_uis = child_uis
        self._shared_input_queue: asyncio.Queue[str] = asyncio.Queue()
        self._waiting_for_input: asyncio.Future | None = None
        # Track all tasks for cleanup
        self._tasks: list[asyncio.Task] = []
        self._shutdown_event: asyncio.Event | None = None
        self._cleanup_done: bool = False
        self._shutdown_lock: asyncio.Lock = asyncio.Lock()
        self._signal_handler_installed: bool = False

    def _submit_from_child(self, child_ui: ChildUIProtocol, message: str):
        """Called by child UIs when they receive input."""
        if is_shutdown_requested():
            return  # Ignore input during shutdown
        if self._waiting_for_input and not self._waiting_for_input.done():
            self._waiting_for_input.set_result(message)
            return
        self._submit_user_message(self._llm_task, message)

    def append_to_output(self, *values, sep=" ", end="\n", **kwargs):
        if is_shutdown_requested():
            return  # Don't output during shutdown
        message = sep.join(str(v) for v in values) + end
        for child_ui in self.child_uis:
            child_ui.send_output(message)

    async def ask_user(self, prompt: str) -> str:
        if is_shutdown_requested():
            return ""  # Return empty during shutdown
        
        for child_ui in self.child_uis:
            child_ui.send_output(f"\n❓ {prompt}\n")
            if hasattr(child_ui, "send_immediate"):
                asyncio.create_task(
                    child_ui.send_immediate(
                        f"❓ {prompt}\n\n_Reply to answer._", parse_mode="Markdown"
                    )
                )

        loop = asyncio.get_event_loop()
        self._waiting_for_input = loop.create_future()

        try:
            result = await self._waiting_for_input
            return result
        finally:
            self._waiting_for_input = None

    async def run_interactive_command(self, cmd, shell=False):
        for child_ui in self.child_uis:
            child_ui.send_output(f"⚙️ Running: {cmd}\n")
        return 0

    def _install_async_signal_handler(self):
        """Install asyncio signal handler for graceful shutdown."""
        if self._signal_handler_installed:
            return
        self._signal_handler_installed = True

        try:
            loop = asyncio.get_running_loop()

            def handle_sigint():
                """Handle SIGINT for graceful shutdown."""
                if is_shutdown_requested():
                    # Second Ctrl+C - force immediate exit (bypass Python cleanup)
                    print("\n⚠️ Hard exit!")
                    import os
                    os._exit(1)

                # First Ctrl+C - graceful shutdown
                print("\n👋 Shutting down...")
                request_shutdown()
                if self._shutdown_event:
                    self._shutdown_event.set()

            # Use signal.SIGINT (value 2) for cross-platform compatibility
            loop.add_signal_handler(2, handle_sigint)  # SIGINT = 2
        except (NotImplementedError, RuntimeError, ValueError, OSError):
            # Signal handlers not supported on this platform (e.g., Windows)
            pass

    async def run_async(self) -> str:
        self._shutdown_event = asyncio.Event()

        # Install asyncio signal handler for graceful shutdown
        self._install_async_signal_handler()

        # Start child UIs
        for child_ui in self.child_uis:
            if hasattr(child_ui, "start"):
                await child_ui.start()

        # Setup handlers
        for child_ui in self.child_uis:
            if hasattr(child_ui, "_app") and child_ui._app:
                await setup_telegram_handler(child_ui, self)
            elif isinstance(child_ui, TerminalChildUI):
                task = asyncio.create_task(cli_input_loop(child_ui, self))
                self._tasks.append(task)

        # Start message processing
        self._tasks.append(asyncio.create_task(self._process_messages_loop()))

        if self._initial_message:
            self._submit_user_message(self._llm_task, self._initial_message)

        try:
            print("🔄 Waiting for shutdown signal...", flush=True)
            await self._shutdown_event.wait()
            print("📤 Shutdown signal received, cleaning up...", flush=True)
        except asyncio.CancelledError:
            print("📤 Cancelled, cleaning up...", flush=True)
        except KeyboardInterrupt:
            print("📤 Interrupted, cleaning up...", flush=True)
        finally:
            await self._cleanup()
            # Signal zrb to terminate the session (stops log_session_state loop)
            if hasattr(self._ctx, 'session') and self._ctx.session is not None:
                self._ctx.session.terminate()
            # Force exit - executor threads with input() can't be cancelled gracefully
            # os._exit bypasses Python's shutdown cleanup (300s executor thread wait)
            print("🚪 Exiting...", flush=True)
            os._exit(0)
        return ""

    async def _cleanup(self):
        """Cancel all tasks and cleanup child UIs with proper shutdown handling."""
        async with self._shutdown_lock:
            if self._cleanup_done:
                return
            self._cleanup_done = True
        
        print("🧹 Cleaning up...", flush=True)
        
        # Signal shutdown to all components
        request_shutdown()
        
        # Cancel all tasks with SHORT timeout (they may be blocked on executor)
        for task in self._tasks:
            if not task.done():
                task.cancel()
        
        print(f"   Cancelling {len([t for t in self._tasks if not t.done()])} tasks...", flush=True)
        
        # Wait for tasks with short timeout - they might be blocked on input()
        if self._tasks:
            try:
                async with asyncio.timeout(1.0):  # Short: executor threads can't be cancelled
                    await asyncio.gather(*self._tasks, return_exceptions=True)
            except (asyncio.CancelledError, KeyboardInterrupt, asyncio.TimeoutError):
                pass

        print("   Tasks cancelled.", flush=True)

        # Cleanup child UIs with short timeouts
        for child_ui in self.child_uis:
            for method in ["flush", "stop"]:
                try:
                    func = getattr(child_ui, method, None)
                    if func:
                        result = func()
                        if asyncio.iscoroutine(result):
                            try:
                                async with asyncio.timeout(1.0):  # Short: fast cleanup
                                    await result
                            except (asyncio.CancelledError, KeyboardInterrupt, asyncio.TimeoutError):
                                pass
                except (asyncio.CancelledError, KeyboardInterrupt):
                    pass
                except Exception:
                    pass
        print("✓ Cleanup complete.", flush=True)

    def on_exit(self):
        """Handle exit signal - trigger immediate shutdown."""
        request_shutdown()
        if self._shutdown_event:
            self._shutdown_event.set()
        # Cancel all tasks directly
        for task in getattr(self, "_tasks", []):
            if not task.done():
                task.cancel()


# ─────────────────────────────────────────────────────────────────────────────
# Input Handlers
# ─────────────────────────────────────────────────────────────────────────────


async def setup_telegram_handler(child_ui: TelegramChildUI, multiplexer: MultiplexerUI):
    """Register message handler for Telegram."""
    if not child_ui._app:
        return

    from telegram.ext import MessageHandler, filters

    async def handle_message(update, context):
        if not is_shutdown_requested():
            multiplexer._submit_from_child(child_ui, update.message.text)

    child_ui._app.add_handler(MessageHandler(filters.TEXT, handle_message))


async def cli_input_loop(child_ui: TerminalChildUI, multiplexer: MultiplexerUI):
    """Read from CLI and forward to multiplexer."""
    loop = asyncio.get_event_loop()

    while not is_shutdown_requested():
        try:
            # Use a thread executor for blocking input
            line = await loop.run_in_executor(None, input)
            if is_shutdown_requested():
                break
            if line.strip():
                multiplexer._submit_from_child(child_ui, line.strip())
        except (EOFError, KeyboardInterrupt):
            request_shutdown()
            break
        except asyncio.CancelledError:
            break
        except Exception:
            pass  # Ignore other errors and continue


# ─────────────────────────────────────────────────────────────────────────────
# Multiplexed Approval Channel
# ─────────────────────────────────────────────────────────────────────────────


class MultiplexerApprovalChannel(ApprovalChannel):
    """Approval channel that broadcasts to multiple channels."""

    def __init__(self, channels: list[ApprovalChannel]):
        self.channels = channels
        self._pending: dict[str, asyncio.Future] = {}

    async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
        if is_shutdown_requested():
            return ApprovalResult(approved=False, message="Shutdown requested")
        
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._pending[context.tool_call_id] = future

        async def request_from_channel(channel: ApprovalChannel):
            try:
                result = await channel.request_approval(context)
                if not future.done():
                    future.set_result(result)
                return result
            except Exception as e:
                if not future.done():
                    future.set_result(ApprovalResult(approved=False, message=str(e)))
                return ApprovalResult(approved=False, message=str(e))

        tasks = [asyncio.create_task(request_from_channel(ch)) for ch in self.channels]

        try:
            async with asyncio.timeout(300):
                return await future
        except asyncio.TimeoutError:
            return ApprovalResult(approved=False, message="Timeout")
        finally:
            for task in tasks:
                task.cancel()
            self._pending.pop(context.tool_call_id, None)

    async def notify(
        self, message: str, context: ApprovalContext | None = None
    ) -> None:
        if is_shutdown_requested():
            return
        for channel in self.channels:
            try:
                await channel.notify(message, context)
            except:
                pass


class TerminalApprovalChannel(ApprovalChannel):
    """Terminal-based approval."""

    async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
        if is_shutdown_requested():
            return ApprovalResult(approved=False, message="Shutdown requested")
        
        print(f"\n🔔 Tool: {context.tool_name}")
        print(
            f"Arguments: {json.dumps(context.tool_args, indent=2, default=str)[:500]}"
        )
        print("Approve? [Y/n] ", end="", flush=True)

        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(None, input)
            return ApprovalResult(approved=response.strip().lower() in ("", "y", "yes"))
        except (EOFError, KeyboardInterrupt):
            return ApprovalResult(approved=False)

    async def notify(
        self, message: str, context: ApprovalContext | None = None
    ) -> None:
        print(f"📢 {message}")


class TelegramApprovalChannel(ApprovalChannel):
    """Telegram approval via inline buttons."""

    def __init__(self, child_ui: TelegramChildUI):
        self.child_ui = child_ui
        self._pending: dict[str, asyncio.Future] = {}
        self._handler_added = False

    async def _ensure_handler(self):
        if self._handler_added or not self.child_ui._app:
            return

        from telegram.ext import CallbackQueryHandler

        async def handle_callback(update, context):
            query = update.callback_query
            await query.answer()
            action, tool_call_id = query.data.split(":", 1)

            if tool_call_id in self._pending:
                self._pending.pop(tool_call_id).set_result(
                    ApprovalResult(approved=(action == "yes"))
                )
            await query.edit_message_text(
                "✅ Approved" if action == "yes" else "❌ Denied"
            )

        self.child_ui._app.add_handler(CallbackQueryHandler(handle_callback))
        self._handler_added = True

    async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
        if is_shutdown_requested():
            return ApprovalResult(approved=False, message="Shutdown requested")
        
        await self._ensure_handler()
        await self.child_ui.flush()

        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._pending[context.tool_call_id] = future

        args_str = json.dumps(context.tool_args, indent=2, default=str)[:500]
        await self.child_ui.send_immediate(
            f"🔔 *Tool*: `{context.tool_name}`\n```\n{args_str}\n```",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "✅ Approve", callback_data=f"yes:{context.tool_call_id}"
                        ),
                        InlineKeyboardButton(
                            "❌ Deny", callback_data=f"no:{context.tool_call_id}"
                        ),
                    ]
                ]
            ),
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
        await self.child_ui.send_immediate(message)


# ─────────────────────────────────────────────────────────────────────────────
# Integration with zrb llm chat
# ─────────────────────────────────────────────────────────────────────────────

if BOT_TOKEN and CHAT_ID:
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
        return MultiplexerUI(
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