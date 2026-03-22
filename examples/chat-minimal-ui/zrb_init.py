"""
Minimal UI Example for Zrb LLM Chat

This example demonstrates how to create custom UI backends for LLM chat
using BaseUI - the base class for all UI implementations.

Extension Levels:
    ┌─────────────────────────────────────────────────────────────────┐
    │ Level 0: UIProtocol (minimal, 4 methods)                        │
    │         - For tool confirmations only                          │
    │         - See: src/zrb/llm/tool_call/ui_protocol.py            │
    ├─────────────────────────────────────────────────────────────────┤
    │ Level 1: BaseUI (THIS EXAMPLE - base class)                    │
    │         - Implement 4 required methods + run_async()           │
    │         - For custom backends (Telegram, Discord, WebSocket)  │
    │         - See: src/zrb/llm/app/base_ui.py                      │
    ├─────────────────────────────────────────────────────────────────┤
    │ Level 2: UI (terminal implementation)                          │
    │         - Full TUI with prompt_toolkit                         │
    │         - See: src/zrb/llm/app/ui.py                            │
    ├─────────────────────────────────────────────────────────────────┤
    │ Level 3: MultiplexerUI (multi-channel support)                 │
    │         - Manages multiple child UIs                           │
    │         - See: examples/telegram-cli/ for example               │
    └─────────────────────────────────────────────────────────────────┘

Usage:
    # Just run the built-in chat command with this minimal UI
    zrb llm chat

    # With initial message
    zrb llm chat --message "Hello, how are you?"

    # With logging to file
    ZRB_CHAT_LOG_FILE=chat.log zrb llm chat

The key insight: We hijack the built-in `llm_chat` task by setting
our own UI factory. This is exactly how telegram-cli works.
"""

import asyncio
import os
from typing import Any

from zrb.builtin.llm.chat import llm_chat
from zrb.context.any_context import AnyContext
from zrb.llm.app.base_ui import BaseUI
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.task.llm_task import LLMTask

# =============================================================================
# Configuration
# =============================================================================

LOG_FILE = os.environ.get("ZRB_CHAT_LOG_FILE", None)


# =============================================================================
# Minimal UI Implementation
# =============================================================================


class MinimalUI(BaseUI):
    """A minimal UI implementation demonstrating BaseUI usage.

    This is simpler than implementing a full terminal UI, but provides
    complete control over input/output handling. Perfect for custom
    backends like WebSocket, HTTP API, or message queues.

    Key design:
    - Uses callbacks for render and input (customizable)
    - Implements run_async() with message loop
    - Handles all BaseUI required methods

    For production backends (Telegram, Discord), see examples/telegram-cli/
    which shows event-driven patterns with bot polling.
    """

    def __init__(
        self,
        ctx: AnyContext,
        llm_task: LLMTask,
        history_manager: AnyHistoryManager,
        render_callback=None,
        input_callback=None,
        log_file=None,
        **kwargs,
    ):
        super().__init__(
            ctx=ctx,
            yolo_xcom_key=f"_yolo_{id(self)}",
            assistant_name=kwargs.get("assistant_name", "ZrbBot"),
            llm_task=llm_task,
            history_manager=history_manager,
            initial_message=kwargs.get("initial_message", ""),
            initial_attachments=kwargs.get("initial_attachments", []),
            conversation_session_name=kwargs.get("conversation_session_name", ""),
            yolo=kwargs.get("yolo", False),
            exit_commands=kwargs.get("exit_commands", ["/exit", "/quit"]),
            info_commands=kwargs.get("info_commands", ["/help", "/?"]),
            save_commands=kwargs.get("save_commands", ["/save"]),
            load_commands=kwargs.get("load_commands", ["/load"]),
            attach_commands=kwargs.get("attach_commands", ["/attach"]),
            redirect_output_commands=kwargs.get(
                "redirect_output_commands", ["/redirect"]
            ),
            yolo_toggle_commands=kwargs.get("yolo_toggle_commands", ["/yolo"]),
            set_model_commands=kwargs.get("set_model_commands", ["/model"]),
            exec_commands=kwargs.get("exec_commands", ["/exec"]),
        )
        self._render_callback = render_callback or self._default_render
        self._input_callback = input_callback or self._default_input
        self._log_file = log_file
        self._running = False

    def _default_render(self, msg: str) -> None:
        """Default render: print to stdout."""
        print(msg, end="", flush=True)

    async def _default_input(self) -> str:
        """Default input: asyncio stdin."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, input, "You> ")

    # =========================================================================
    # REQUIRED METHODS - BaseUI implementation
    # =========================================================================

    def append_to_output(self, *values, sep=" ", end="\n", file=None, flush=False):
        """Render output to user."""
        content = sep.join(str(v) for v in values) + end
        self._render_callback(content)

        # Log to file if configured
        if self._log_file:
            try:
                with open(self._log_file, "a", encoding="utf-8") as f:
                    f.write(content)
            except Exception:
                pass  # Ignore file errors

        # Track for result extraction
        if (
            content.strip()
            and not content.startswith("\n💬")
            and not content.startswith("\n🤖")
        ):
            self._last_result_data = content.rstrip("\n")

    async def ask_user(self, prompt: str) -> str:
        """Get user input with optional prompt."""
        if prompt:
            self.append_to_output(prompt, end="")

        result = self._input_callback()
        if asyncio.iscoroutine(result):
            result = await result
        return result if isinstance(result, str) else str(result)

    async def run_interactive_command(self, cmd: str | list[str], shell: bool = False):
        """Execute shell command and stream output."""
        cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)

        try:
            if shell:
                proc = await asyncio.create_subprocess_shell(
                    cmd_str,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                cmd_list = cmd if isinstance(cmd, list) else cmd_str.split()
                proc = await asyncio.create_subprocess_exec(
                    *cmd_list,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

            async def read_stream(stream, prefix=""):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    self.append_to_output(f"{prefix}{line.decode()}")

            await asyncio.gather(
                read_stream(proc.stdout),
                read_stream(proc.stderr, prefix="[stderr] "),
            )

            return await proc.wait()
        except Exception as e:
            self.append_to_output(f"\n[Error executing command: {e}]\n")
            return 1

    async def run_async(self) -> str:
        """Run the UI event loop."""
        # Start message processing
        self._process_messages_task = asyncio.create_task(self._process_messages_loop())

        # Send initial message if provided
        if self._initial_message:
            self._submit_user_message(self._llm_task, self._initial_message)

        self._running = True

        try:
            while self._running:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        finally:
            self._process_messages_task.cancel()
            try:
                await self._process_messages_task
            except asyncio.CancelledError:
                pass

        return self.last_output

    def on_exit(self):
        """Cleanup on exit."""
        self._running = False
        if self._log_file:
            print(f"\n📁 Chat log saved to: {self._log_file}")
        print("👋 Goodbye!")


# =============================================================================
# UI Factory Function
# =============================================================================


def create_minimal_ui(
    ctx: AnyContext,
    llm_task_core: LLMTask,
    history_manager: AnyHistoryManager,
    ui_commands: dict[str, list[str]],
    initial_message: str,
    initial_conversation_name: str,
    initial_yolo: bool,
    initial_attachments: list[Any],
) -> MinimalUI:
    """Factory function that creates a MinimalUI instance.

    This is called by llm_chat when it needs to create the UI.
    The parameters are provided by the task infrastructure.

    Args:
        ctx: The execution context
        llm_task_core: The LLM task to connect to
        history_manager: Conversation history manager
        ui_commands: Dictionary of command keywords (exit, save, etc.)
        initial_message: First message to send
        initial_conversation_name: Session name for history
        initial_yolo: Auto-approve all tools
        initial_attachments: Initial file attachments

    Returns:
        Configured MinimalUI instance
    """

    def render_output(msg: str) -> None:
        """Custom render function - prints to stdout."""
        print(msg, end="", flush=True)

    async def get_user_input() -> str:
        """Custom input function - async readline."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, input, "You> ")

    return MinimalUI(
        ctx=ctx,
        llm_task=llm_task_core,
        history_manager=history_manager,
        render_callback=render_output,
        input_callback=get_user_input,
        log_file=LOG_FILE,
        assistant_name="ZrbBot",
        initial_message=initial_message,
        conversation_session_name=initial_conversation_name,
        yolo=initial_yolo,
        initial_attachments=initial_attachments,
        exit_commands=ui_commands.get("exit", ["/exit", "/quit"]),
        info_commands=ui_commands.get("info", ["/help", "/?"]),
        save_commands=ui_commands.get("save", ["/save"]),
        load_commands=ui_commands.get("load", ["/load"]),
        attach_commands=ui_commands.get("attach", ["/attach"]),
        redirect_output_commands=ui_commands.get("redirect", ["/redirect"]),
        yolo_toggle_commands=ui_commands.get("yolo_toggle", ["/yolo"]),
        set_model_commands=ui_commands.get("set_model", ["/model"]),
        exec_commands=ui_commands.get("exec", ["/exec"]),
    )


# =============================================================================
# Hijack the built-in llm_chat task
# =============================================================================

# This is the key: we set our UI factory on the built-in llm_chat task.
# When user runs `zrb llm chat`, it will use our MinimalUI instead of
# the default terminal UI.

llm_chat.set_ui_factory(create_minimal_ui)

# That's it! No need to create a new task.
# User runs: zrb llm chat
