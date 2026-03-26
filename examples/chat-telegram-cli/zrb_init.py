"""
Telegram + CLI Dual UI - Multiplexer Architecture

This implements Level 3: MultiplexerUI (multi-channel support)
- Both CLI and Telegram receive output
- Input accepted from EITHER channel
- Shared message queue (serialized execution)
- Multiplexed approvals (first response wins)

Architecture:
                    ┌───────────────────────────┐
                    │      MultiplexerUI        │
                    │     (extends BaseUI)      │
                    │                           │
                    │  ┌────────────────────┐   │
                    │  │   _message_queue   │   │  ◄── SINGLE SHARED QUEUE
                    │  └────────────────────┘   │
                    │            ▲              │
                    │  _submit_user_message()   │
                    └────────────┼──────────────┘
                                 │
              ┌──────────────────┴──────────────────┐
              │                                     │
    ┌─────────┴──────────┐             ┌────────────┴───────────┐
    │  TerminalChildUI   │             │   TelegramChildUI      │
    │   (stdin/stdout)   │             │   (bot polling)        │
    └────────────────────┘             └────────────────────────┘

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
from zrb.llm.app import BaseUI
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
        if not clean:
            return

        chunks = self._split(clean, 4000)
        for i, chunk in enumerate(chunks):
            # Only attach reply_markup (like buttons) to the LAST chunk
            chunk_kwargs = kwargs.copy()
            if "reply_markup" in chunk_kwargs and i < len(chunks) - 1:
                del chunk_kwargs["reply_markup"]

            try:
                await self._bot.send_message(
                    chat_id=self.chat_id, text=chunk, **chunk_kwargs
                )
            except Exception as e:
                # If it fails (usually due to Markdown parsing errors), try without parse_mode
                if "parse_mode" in chunk_kwargs:
                    del chunk_kwargs["parse_mode"]
                    try:
                        await self._bot.send_message(
                            chat_id=self.chat_id, text=chunk, **chunk_kwargs
                        )
                    except Exception as fallback_e:
                        print(f"Fallback send failed: {fallback_e}")
                else:
                    print(f"Send failed: {e}")

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
        self.input_allowed = asyncio.Event()
        self.input_allowed.set()

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
        import os

        # Only run on terminal
        print(f"\n⚙️ Running: {cmd}\n")
        if isinstance(cmd, list):
            import subprocess

            subprocess.run(cmd)
        else:
            os.system(cmd)
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
            if hasattr(self._ctx, "session") and self._ctx.session is not None:
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

        print(
            f"   Cancelling {len([t for t in self._tasks if not t.done()])} tasks...",
            flush=True,
        )

        # Wait for tasks with short timeout - they might be blocked on input()
        if self._tasks:
            try:
                async with asyncio.timeout(
                    1.0
                ):  # Short: executor threads can't be cancelled
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
                            except (
                                asyncio.CancelledError,
                                KeyboardInterrupt,
                                asyncio.TimeoutError,
                            ):
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
        if is_shutdown_requested():
            return

        # If this is a reply to an edit request, DO NOT send to the LLM chat
        if update.message.reply_to_message:
            reply_id = update.message.reply_to_message.message_id

            # Use the global state tracked by TelegramApprovalChannel
            # If the replied message ID matches a known edit request, ignore it here
            if (
                hasattr(multiplexer, "_edit_message_ids")
                and reply_id in multiplexer._edit_message_ids
            ):
                return

        multiplexer._submit_from_child(child_ui, update.message.text)

    child_ui._app.add_handler(MessageHandler(filters.TEXT, handle_message))


async def cli_input_loop(child_ui: TerminalChildUI, multiplexer: MultiplexerUI):
    """Read from CLI and forward to multiplexer."""
    loop = asyncio.get_event_loop()

    while not is_shutdown_requested():
        try:
            # Wait until input is allowed (paused during edits)
            await multiplexer.input_allowed.wait()

            # Use a thread executor for blocking input
            line = await loop.run_in_executor(None, input)

            if is_shutdown_requested():
                break

            # Check if this input was intended for an approval
            approval_future = getattr(multiplexer, "_terminal_approval_future", None)
            if approval_future and not approval_future.done():
                approval_future.set_result(line)
                continue

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
    """Terminal-based approval with edit support."""

    def __init__(self, ui_proxy: "DeferredMultiplexedApprovalChannel" = None):
        self.ui_proxy = ui_proxy

    async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
        if is_shutdown_requested():
            return ApprovalResult(approved=False, message="Shutdown requested")

        def _format_args(raw):
            try:
                # Unwrap provider/runner wrappers for readability
                if isinstance(raw, dict):
                    if "args_dict" in raw:
                        raw = raw["args_dict"]
                    elif "args_json" in raw and isinstance(raw["args_json"], str):
                        return json.dumps(
                            json.loads(raw["args_json"]), indent=2, ensure_ascii=False
                        )
                    elif "args" in raw and isinstance(raw["args"], str):
                        return json.dumps(
                            json.loads(raw["args"]), indent=2, ensure_ascii=False
                        )
                if isinstance(raw, str):
                    # Pretty print if it's JSON string, else return as-is
                    try:
                        return json.dumps(json.loads(raw), indent=2, ensure_ascii=False)
                    except Exception:
                        return raw
                return json.dumps(raw, indent=2, ensure_ascii=False)
            except Exception:
                return str(raw)

        print(f"\n🔔 Tool: {context.tool_name}")
        print(f"Arguments:\n{_format_args(context.tool_args)[:2000]}")
        print("Approve? [Y/n/e] ", end="", flush=True)

        loop = asyncio.get_event_loop()
        try:
            # First, stop the CLI input loop from processing new text
            ui = getattr(sys.modules[__name__], "_multiplexer_ui", None)

            if ui:
                # We tell the cli_input_loop that an approval is pending.
                # However, python's native `input()` might already be blocked!
                # If we just create a future and wait, we might get blocked.
                # We need to use the multiplexer's shared input future pattern.
                ui._terminal_approval_future = loop.create_future()
                response = await ui._terminal_approval_future
                ui._terminal_approval_future = None
            else:
                response = await loop.run_in_executor(None, input)

            r = response.strip().lower()

            if r in ("", "y", "yes", "ok"):
                if ui:
                    ui.input_allowed.set()
                return ApprovalResult(approved=True)
            if r in ("n", "no", "deny", "cancel"):
                if ui:
                    ui.input_allowed.set()
                return ApprovalResult(approved=False, message="User denied")
            if r == "e":
                # Edit mode - prompt for new arguments using default text editor
                import os
                import subprocess
                import tempfile

                from zrb.config.config import CFG

                print("\n✏️ Edit mode - opening editor...")

                # Extract args securely and remember how they were wrapped
                wrap_type = None
                try:
                    args = context.tool_args
                    if isinstance(args, dict):
                        if "args_dict" in args:
                            args = args["args_dict"]
                            wrap_type = "args_dict"
                        elif "args_json" in args and isinstance(args["args_json"], str):
                            args = json.loads(args["args_json"])
                            wrap_type = "args_json"
                        elif "args" in args and isinstance(args["args"], str):
                            args = json.loads(args["args"])
                            wrap_type = "args"
                    elif isinstance(args, str):
                        try:
                            args = json.loads(args)
                            wrap_type = "str_json"
                        except Exception:
                            pass
                except Exception:
                    args = context.tool_args

                content_str = json.dumps(args, indent=2, ensure_ascii=False)

                with tempfile.NamedTemporaryFile(
                    suffix=".json", mode="w+", delete=False
                ) as tf:
                    tf.write(content_str)
                    tf_path = tf.name

                try:
                    # Clear the screen to ensure the editor draws properly
                    # os.system('clear' if os.name == 'posix' else 'cls')

                    # Run interactive command natively (bypasses run_interactive_command which assumes prompt_toolkit)
                    print(f"\n⚙️ Running: {CFG.EDITOR} {tf_path}\n")

                    # Instead of a blocking subprocess call, we use os.system
                    # This ensures the TTY handles the process foregrounding correctly
                    # Subprocess sometimes detaches the TTY when run from inside an asyncio loop thread
                    os.system(f"{CFG.EDITOR} {tf_path}")

                    with open(tf_path, "r", encoding="utf-8") as tf:
                        new_content = tf.read()
                finally:
                    if ui:
                        # Small delay to let the terminal recover before resuming the input loop
                        await asyncio.sleep(0.1)
                        ui.input_allowed.set()
                    os.remove(tf_path)

                if new_content.strip() == content_str.strip():
                    print("ℹ️ No changes made. Edit cancelled.")
                    return ApprovalResult(approved=False, message="Edit cancelled")

                try:
                    edited_args = json.loads(new_content)

                    # We must not pass raw Python dicts back if Pydantic-AI expects a string wrapper!
                    # If wrap_type was JSON string, we must return a JSON string, otherwise Pydantic-AI
                    # validator will fail when trying to parse the dict into the expected str format.
                    final_args = edited_args
                    if wrap_type == "args_dict":
                        final_args = {"args_dict": edited_args}
                    elif wrap_type == "args_json":
                        final_args = {
                            "args_json": json.dumps(edited_args, ensure_ascii=False)
                        }
                    elif wrap_type == "args":
                        final_args = {
                            "args": json.dumps(edited_args, ensure_ascii=False)
                        }
                    elif wrap_type == "str_json":
                        final_args = json.dumps(edited_args, ensure_ascii=False)

                    print(f"✅ Approved with edited arguments.")
                    return ApprovalResult(
                        approved=True,
                        edited_args=(
                            {"__local_edit__": True, "args_dict": edited_args}
                            if not wrap_type
                            else final_args
                        ),
                    )
                except json.JSONDecodeError as e:
                    print(f"❌ Invalid JSON: {e}")
                    return ApprovalResult(approved=False, message=f"Invalid JSON: {e}")

            if ui:
                ui.input_allowed.set()
            return ApprovalResult(
                approved=False, message=f"Unknown response: {response}"
            )
        except (EOFError, KeyboardInterrupt):
            if ui:
                ui.input_allowed.set()
            return ApprovalResult(approved=False)

        # Handle the case where multiplexer isn't active (e.g. fallback behavior)
        if r in ("", "y", "yes", "ok"):
            return ApprovalResult(approved=True)
        if r in ("n", "no", "deny", "cancel"):
            return ApprovalResult(approved=False, message="User denied")
        if r == "e":
            # Fallback edit mode if UI is none
            import os
            import subprocess
            import tempfile

            from zrb.config.config import CFG

            print("\n✏️ Edit mode - opening editor...")

            wrap_type = None
            try:
                args = context.tool_args
                if isinstance(args, dict):
                    if "args_dict" in args:
                        args = args["args_dict"]
                        wrap_type = "args_dict"
                    elif "args_json" in args and isinstance(args["args_json"], str):
                        args = json.loads(args["args_json"])
                        wrap_type = "args_json"
                    elif "args" in args and isinstance(args["args"], str):
                        args = json.loads(args["args"])
                        wrap_type = "args"
                elif isinstance(args, str):
                    try:
                        args = json.loads(args)
                        wrap_type = "str_json"
                    except Exception:
                        pass
            except Exception:
                args = context.tool_args

            content_str = json.dumps(args, indent=2, ensure_ascii=False)

            with tempfile.NamedTemporaryFile(
                suffix=".json", mode="w+", delete=False
            ) as tf:
                tf.write(content_str)
                tf_path = tf.name

            # Use synchronous os.system to ensure TTY control
            os.system(f"{CFG.EDITOR} {tf_path}")

            with open(tf_path, "r", encoding="utf-8") as tf:
                new_content = tf.read()
            os.remove(tf_path)

            if new_content.strip() == content_str.strip():
                print("ℹ️ No changes made. Edit cancelled.")
                return ApprovalResult(approved=False, message="Edit cancelled")

            try:
                edited_args = json.loads(new_content)

                # We must not pass raw Python dicts back if Pydantic-AI expects a string wrapper!
                # If wrap_type was JSON string, we must return a JSON string, otherwise Pydantic-AI
                # validator will fail when trying to parse the dict into the expected str format.
                final_args = edited_args
                if wrap_type == "args_dict":
                    final_args = {"args_dict": edited_args}
                elif wrap_type == "args_json":
                    final_args = {
                        "args_json": json.dumps(edited_args, ensure_ascii=False)
                    }
                elif wrap_type == "args":
                    final_args = {"args": json.dumps(edited_args, ensure_ascii=False)}
                elif wrap_type == "str_json":
                    final_args = json.dumps(edited_args, ensure_ascii=False)

                print(f"✅ Approved with edited arguments.")
                return ApprovalResult(
                    approved=True,
                    edited_args=(
                        {"__local_edit__": True, "args_dict": edited_args}
                        if not wrap_type
                        else final_args
                    ),
                )
            except json.JSONDecodeError as e:
                print(f"❌ Invalid JSON: {e}")
                return ApprovalResult(approved=False, message=f"Invalid JSON: {e}")

        return ApprovalResult(approved=False, message=f"Unknown response: {response}")

    async def notify(
        self, message: str, context: ApprovalContext | None = None
    ) -> None:
        print(f"📢 {message}")


class TelegramApprovalChannel(ApprovalChannel):
    """Telegram approval via inline buttons with edit support."""

    def __init__(self, child_ui: TelegramChildUI, multiplexer: MultiplexerUI):
        self.child_ui = child_ui
        self.multiplexer = multiplexer
        self._pending: dict[str, asyncio.Future] = {}
        self._edit_contexts: dict[str, ApprovalContext] = {}
        self._edit_futures: dict[str, asyncio.Future] = {}
        self._edit_messages: dict[int, str] = {}  # message_id -> tool_call_id

        # Share edit message IDs with multiplexer to prevent message leaks
        if not hasattr(self.multiplexer, "_edit_message_ids"):
            self.multiplexer._edit_message_ids = set()

        self._handler_added = False

    async def _ensure_handler(self):
        if self._handler_added or not self.child_ui._app:
            return

        from telegram.ext import CallbackQueryHandler, MessageHandler, filters

        async def handle_callback(update, context):
            query = update.callback_query
            await query.answer()
            action, tool_call_id = query.data.split(":", 1)

            if tool_call_id in self._pending:
                if action == "edit":
                    # Start edit flow - send args as editable message
                    future = self._pending.pop(tool_call_id)
                    approval_context = self._edit_contexts.pop(tool_call_id, None)
                    if approval_context:
                        await self._start_edit_flow(
                            query, tool_call_id, future, approval_context
                        )
                    else:
                        # Fallback - shouldn't happen
                        future.set_result(
                            ApprovalResult(approved=False, message="Edit context lost")
                        )
                else:
                    # Approve or deny
                    approved = action == "yes"
                    future = self._pending.pop(tool_call_id)
                    self._edit_contexts.pop(tool_call_id, None)
                    future.set_result(ApprovalResult(approved=approved))
                    await query.edit_message_text(
                        "✅ Approved" if approved else "❌ Denied"
                    )

        async def handle_edit_reply(update, context):
            """Handle user's edited arguments reply."""
            # Check if this is a reply to an edit request message
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

            # Parse the edited args
            try:
                edited_args = json.loads(update.message.text)
                await update.message.reply_text("✅ Arguments updated, executing...")
                future.set_result(
                    ApprovalResult(approved=True, edited_args=edited_args)
                )
                # Remove from tracking set so we don't leak memory
                self.multiplexer._edit_message_ids.discard(message_id)
            except json.JSONDecodeError as e:
                await update.message.reply_text(
                    f"❌ Invalid JSON: {e}\nPlease reply with valid JSON or type 'cancel'."
                )
                # Re-add the mapping so user can try again
                self._edit_messages[message_id] = tool_call_id
                self._edit_futures[tool_call_id] = future

        self.child_ui._app.add_handler(CallbackQueryHandler(handle_callback))
        # Add the edit reply handler to group 1 so it doesn't conflict with the main chat handler in group 0
        self.child_ui._app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_reply), group=1
        )
        self._handler_added = True

    async def _start_edit_flow(
        self,
        query,
        tool_call_id: str,
        future: asyncio.Future,
        approval_context: ApprovalContext,
    ):
        """Send args as editable message and wait for user reply."""
        context_json = json.dumps(approval_context.tool_args, indent=2, default=str)

        # Send edit request message
        # Don't use Markdown to prevent parsing errors dropping the message!
        safe_text = (
            f"✏️ Edit arguments for {approval_context.tool_name}\n\n"
            f"Reply to this message with modified JSON:\n"
            f"{context_json}\n\n"
            f"Or type 'cancel' to abort."
        )

        message = await query.edit_message_text(safe_text)

        # Store the mapping for reply detection
        self._edit_messages[message.message_id] = tool_call_id
        self._edit_futures[tool_call_id] = future
        self.multiplexer._edit_message_ids.add(message.message_id)

    async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
        if is_shutdown_requested():
            return ApprovalResult(approved=False, message="Shutdown requested")

        await self._ensure_handler()
        await self.child_ui.flush()

        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._pending[context.tool_call_id] = future
        self._edit_contexts[context.tool_call_id] = context

        args_str = json.dumps(context.tool_args, indent=2, default=str)[:500]

        # Don't use Markdown for the arguments block, because json characters
        # often break Telegram's strict MarkdownV2/Markdown parsers, causing
        # the entire message (and its buttons) to be silently dropped!
        safe_text = f"🔔 Tool: {context.tool_name}\n\n{args_str}"

        await self.child_ui.send_immediate(
            safe_text,
            reply_markup=InlineKeyboardMarkup(
                [
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
            ),
        )

        try:
            async with asyncio.timeout(300):
                return await future
        except asyncio.TimeoutError:
            self._pending.pop(context.tool_call_id, None)
            self._edit_contexts.pop(context.tool_call_id, None)
            return ApprovalResult(approved=False, message="Timeout")
        finally:
            # Cleanup
            self._pending.pop(context.tool_call_id, None)
            self._edit_contexts.pop(context.tool_call_id, None)
            self._edit_futures.pop(context.tool_call_id, None)

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

    terminal_approval = TerminalApprovalChannel()

    # We need the MultiplexerUI instance before creating TelegramApprovalChannel
    # But create_ui needs the channels to be passed in to llm_chat.
    # So we instantiate the UI first, THEN the channel.

    _multiplexer_ui = None

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
        global _multiplexer_ui
        _multiplexer_ui = MultiplexerUI(
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
        return _multiplexer_ui

    llm_chat.set_ui_factory(create_ui)

    # We must delay the channel creation until the UI exists
    # Zrb creates the UI when the LLM chat runs, which is after zrb_init.py executes.
    # To fix this dependency loop cleanly, we pass the MultiplexerUI instance at runtime.

    # A tiny proxy channel that creates the real channel on first use
    class DeferredMultiplexedApprovalChannel(ApprovalChannel):
        def __init__(self):
            self.channel = None

        async def _ensure(self):
            if self.channel is None:
                telegram_approval = TelegramApprovalChannel(
                    telegram_child, _multiplexer_ui
                )
                self.channel = MultiplexerApprovalChannel(
                    [terminal_approval, telegram_approval]
                )

        async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
            await self._ensure()
            return await self.channel.request_approval(context)

        async def notify(
            self, message: str, context: ApprovalContext | None = None
        ) -> None:
            await self._ensure()
            return await self.channel.notify(message, context)

    llm_chat.set_approval_channel(DeferredMultiplexedApprovalChannel())

    print(f"🤖 Telegram + CLI multiplexed UI for chat ID: {CHAT_ID}")
    print(f"   Chat from Telegram AND terminal!")
    print(f"   Both channels receive all responses.")
    print(f"   Approvals sent to both - first response wins!")
else:
    print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
