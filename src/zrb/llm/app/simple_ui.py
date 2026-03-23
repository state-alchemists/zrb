"""
Simple UI Helpers - Reduce boilerplate for custom UI implementations.

This module provides three UI base classes optimized for different patterns:

1. SimpleUI - For basic request-response UIs (CLI, minimal backends)
2. EventDrivenUI - For event-driven UIs (Telegram, Discord, WhatsApp)
3. PollingUI - For polling-based UIs (HTTP API, WebSocket)

Each class minimizes boilerplate by providing sensible defaults and
handling common patterns (queues, buffering, lifecycle management).
"""

import asyncio
import logging
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, TextIO

from zrb.llm.app.base_ui import BaseUI
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.task.llm_task import LLMTask

if TYPE_CHECKING:
    from pydantic_ai import UserContent

    from zrb.context.any_context import AnyContext

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration - Reduces 25+ __init__ params to a single dataclass
# =============================================================================


@dataclass
class UIConfig:
    """Configuration for UI backends.

    This dataclass replaces 25+ individual parameters in BaseUI.__init__.
    Use this for cleaner, more maintainable UI implementations.

    Example:
        config = UIConfig(
            assistant_name="MyBot",
            exit_commands=["/quit", "/bye"],
            yolo=False,
        )
        ui = MyUI(config=config, llm_task=task, history_manager=hist)
    """

    # Identity
    assistant_name: str = "Assistant"

    # Commands (use empty list to disable)
    exit_commands: list[str] = field(default_factory=lambda: ["/exit", "/quit"])
    info_commands: list[str] = field(default_factory=lambda: ["/help", "/?"])
    save_commands: list[str] = field(default_factory=lambda: ["/save"])
    load_commands: list[str] = field(default_factory=lambda: ["/load"])
    attach_commands: list[str] = field(default_factory=lambda: ["/attach"])
    redirect_output_commands: list[str] = field(default_factory=lambda: ["/redirect"])
    yolo_toggle_commands: list[str] = field(default_factory=lambda: ["/yolo"])
    set_model_commands: list[str] = field(default_factory=lambda: ["/model"])
    exec_commands: list[str] = field(default_factory=lambda: ["/exec"])

    # Behavior
    yolo: bool = False  # Auto-approve all tool calls
    yolo_xcom_key: str = ""  # Empty = auto-generate

    # Session
    conversation_session_name: str = ""  # Empty = random name

    @classmethod
    def default(cls) -> "UIConfig":
        """Get default configuration."""
        return cls()

    @classmethod
    def minimal(cls) -> "UIConfig":
        """Minimal config - disables most commands."""
        return cls(
            exit_commands=["/exit"],
            info_commands=[],
            save_commands=[],
            load_commands=[],
            attach_commands=[],
            redirect_output_commands=[],
            yolo_toggle_commands=[],
            set_model_commands=[],
            exec_commands=[],
        )

    def merge_commands(self, ui_commands: dict) -> "UIConfig":
        """Merge UI commands from task configuration.

        Args:
            ui_commands: Dictionary of commands from task configuration

        Returns:
            New UIConfig with merged commands
        """
        return UIConfig(
            exit_commands=ui_commands.get("exit", self.exit_commands),
            info_commands=ui_commands.get("info", self.info_commands),
            save_commands=ui_commands.get("save", self.save_commands),
            load_commands=ui_commands.get("load", self.load_commands),
            attach_commands=ui_commands.get("attach", self.attach_commands),
            redirect_output_commands=ui_commands.get(
                "redirect", self.redirect_output_commands
            ),
            yolo_toggle_commands=ui_commands.get(
                "yolo_toggle", self.yolo_toggle_commands
            ),
            set_model_commands=ui_commands.get("set_model", self.set_model_commands),
            exec_commands=ui_commands.get("exec", self.exec_commands),
            summarize_commands=self.summarize_commands,
            assistant_name=self.assistant_name,
            yolo=self.yolo,
            yolo_xcom_key=self.yolo_xcom_key,
            conversation_session_name=self.conversation_session_name,
        )

    # For compatibility with merge_commands
    summarize_commands: list[str] = field(default_factory=lambda: ["/summarize"])


# =============================================================================
# SimpleUI - For basic request-response UIs
# =============================================================================


class SimpleUI(BaseUI):
    """Simplified UI for basic request-response backends.

    This class reduces boilerplate by providing:
    - Default run_async() implementation
    - Simplified abstract methods (print, get_input vs append_to_output, ask_user)
    - Configuration via UIConfig dataclass
    - Flexible __init__ that accepts **kwargs for easy subclassing

    You only need to implement:
    - print(text: str) -> None        # Display output
    - get_input(prompt: str) -> str   # Get user input (async)

    Example:
        class MyUI(SimpleUI):
            def print(self, text: str):
                print(text, end="", flush=True)

            async def get_input(self, prompt: str) -> str:
                return await asyncio.to_thread(input, prompt)

        # In your zrb_init.py:
        llm_chat.set_ui_factory(
            lambda ctx, task, hm, **kw: MyUI(ctx=ctx, llm_task=task, history_manager=hm)
        )
    """

    def __init__(
        self,
        ctx: "AnyContext" = None,
        llm_task: LLMTask = None,
        history_manager: AnyHistoryManager = None,
        config: UIConfig | None = None,
        initial_message: str = "",
        initial_attachments: list["UserContent"] | None = None,
        model: str | None = None,
        **kwargs,  # Accept extra kwargs for easy subclassing
    ):
        # Accept config parameter
        self._config = config or UIConfig.default()

        # Generate yolo_xcom_key if not provided
        yolo_key = self._config.yolo_xcom_key or f"_yolo_{id(self)}"

        super().__init__(
            ctx=ctx,
            llm_task=llm_task,
            history_manager=history_manager,
            yolo_xcom_key=yolo_key,
            assistant_name=self._config.assistant_name,
            initial_message=initial_message,
            initial_attachments=initial_attachments or [],
            conversation_session_name=self._config.conversation_session_name,
            yolo=self._config.yolo,
            triggers=[],  # Empty list for triggers
            response_handlers=[],  # Empty list - will be merged with default_response_handler
            tool_policies=[],  # Empty list for tool policies
            argument_formatters=[],  # Empty list for argument formatters
            markdown_theme=None,
            summarize_commands=self._config.summarize_commands,
            attach_commands=self._config.attach_commands,
            exit_commands=self._config.exit_commands,
            info_commands=self._config.info_commands,
            save_commands=self._config.save_commands,
            load_commands=self._config.load_commands,
            redirect_output_commands=self._config.redirect_output_commands,
            yolo_toggle_commands=self._config.yolo_toggle_commands,
            set_model_commands=self._config.set_model_commands,
            exec_commands=self._config.exec_commands,
            model=model,
        )

    # =========================================================================
    # Abstract methods - Simplified interface
    # =========================================================================

    @abstractmethod
    async def print(self, text: str) -> None:
        """Display output to user.

        This is a simplified version of append_to_output().
        Just print/emit/send the text.

        Args:
            text: The text to display (already formatted)
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement print()")

    @abstractmethod
    async def get_input(self, prompt: str) -> str:
        """Get user input.

        This is a simplified version of ask_user().
        Display the prompt (if any) and return the user's input.

        Args:
            prompt: Prompt to display (may be empty string)

        Returns:
            User's input as a string
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement get_input()"
        )

    # =========================================================================
    # BaseUI implementation - Maps to simplified interface
    # =========================================================================

    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
    ):
        """Default implementation - calls simplified print().

        Note: print() is async, so we schedule it in the event loop.
        """
        text = sep.join(str(v) for v in values) + end
        # Schedule the async print in the running event loop
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.print(text))
        except RuntimeError:
            # No running event loop - fall back to synchronous print
            # This can happen during initialization or in edge cases
            import sys

            sys.stdout.write(text)
            sys.stdout.flush()

    async def ask_user(self, prompt: str) -> str:
        """Default implementation - calls simplified get_input()."""
        return await self.get_input(prompt)

    async def run_interactive_command(self, cmd: str | list[str], shell: bool = False):
        """Default implementation - not supported in SimpleUI."""
        await self.print("\n⚠️ Interactive commands not supported in this UI\n")
        return 1

    async def run_async(self) -> str:
        """Default implementation - handles common pattern."""
        # Start message processing
        self._process_messages_task = asyncio.create_task(self._process_messages_loop())

        # Send initial message if provided
        if self._initial_message:
            self._submit_user_message(self._llm_task, self._initial_message)

        # Run until stopped
        try:
            await self._run_loop()
        except asyncio.CancelledError:
            pass
        finally:
            self._process_messages_task.cancel()
            try:
                await self._process_messages_task
            except asyncio.CancelledError:
                pass

        return self.last_output

    async def _run_loop(self):
        """Override this for custom event loop (e.g., WebSocket listener)."""
        while True:
            await asyncio.sleep(1)


# =============================================================================
# EventDrivenUI - For event-driven UIs (Telegram, Discord, etc.)
# =============================================================================


class EventDrivenUI(SimpleUI):
    """UI for event-driven backends (Telegram, Discord, WhatsApp).

    This class handles the queue + waiting pattern that's common in
    event-driven systems:
    - Messages arrive via handlers/callbacks
    - ask_user() blocks on an internal queue until user responds

    You need to implement:
    - print(text: str) -> None              # Send to user
    - start_event_loop()                    # Start listening for events

    And call handle_incoming_message() when messages arrive.

    Example:
        class TelegramUI(EventDrivenUI):
            async def print(self, text: str):
                await self.bot.send_message(self.chat_id, text)

            async def start_event_loop(self):
                # Register handler that calls handle_incoming_message()
                self.bot.add_handler(MessageHandler(filters.TEXT, self._on_msg))

            async def _on_msg(self, update, context):
                self.handle_incoming_message(update.message.text)
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._input_queue: asyncio.Queue[str] = asyncio.Queue()
        self._waiting_for_input = False

    # =========================================================================
    # Abstract method - Simplified event handling
    # =========================================================================

    @abstractmethod
    async def start_event_loop(self):
        """Start the event loop for this UI.

        Override this to register handlers with your backend:
        - Telegram: Add message handler
        - Discord: Register on_message callback
        - WhatsApp: Set up webhook handler

        When a message arrives, call handle_incoming_message(text).
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement start_event_loop()"
        )

    # =========================================================================
    # Queue-based input handling
    # =========================================================================

    def handle_incoming_message(self, text: str):
        """Call this when a message arrives from your backend.

        Routes the message to the appropriate handler:
        - If waiting for input (ask_user blocked), it goes to the queue
        - Otherwise, it's submitted as a new user message to the LLM
        """
        if self._waiting_for_input:
            self._input_queue.put_nowait(text)
        else:
            self._submit_user_message(self._llm_task, text)

    async def get_input(self, prompt: str) -> str:
        """Blocks until handle_incoming_message() receives a response."""
        if prompt:
            await self.print(f"❓ {prompt}")
        self._waiting_for_input = True
        try:
            return await self._input_queue.get()
        finally:
            self._waiting_for_input = False

    async def _run_loop(self):
        """Start the event loop and wait."""
        await self.start_event_loop()
        while True:
            await asyncio.sleep(1)


# =============================================================================
# BufferedOutputMixin - For backends with rate limits (Telegram, Discord)
# =============================================================================


class BufferedOutputMixin:
    """Mixin for UIs that need to batch output.

    Use this when:
    - Your backend has rate limits (Telegram: ~30 messages/sec)
    - Streaming tokens would create too many API calls
    - You want cleaner message bundling

    Usage:
        class TelegramUI(EventDrivenUI, BufferedOutputMixin):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                BufferedOutputMixin.__init__(self, flush_interval=0.5)

            async def send_text(self, text: str):
                await self.bot.send_message(self.chat_id, text)

    The print() method will buffer output and flush periodically.
    """

    def __init__(self, flush_interval: float = 0.5, max_buffer_size: int = 2000):
        self._buffer: list[str] = []
        self._flush_interval = flush_interval
        self._max_buffer_size = max_buffer_size
        self._flush_task: asyncio.Task | None = None
        self._flush_lock = asyncio.Lock()

    async def start_flush_loop(self):
        """Start the periodic flush task. Call this in run_async()."""
        self._flush_task = asyncio.create_task(self._flush_loop())

    async def stop_flush_loop(self):
        """Stop the flush task and do final flush. Call this on exit."""
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self._flush_buffer()

    def buffer_output(self, text: str):
        """Add text to buffer. Automatically flushes when full."""
        self._buffer.append(text)

        # Auto-flush when buffer is large
        total_size = sum(len(s) for s in self._buffer)
        if total_size > self._max_buffer_size:
            asyncio.create_task(self._flush_buffer())

    async def _flush_buffer(self):
        """Send buffered content to user."""
        if not self._buffer:
            return

        async with self._flush_lock:
            content = "".join(self._buffer).strip()
            self._buffer = []

            if content:
                # Call the subclass send method
                await self._send_buffered(content)

    async def _send_buffered(self, text: str):
        """Override this to send buffered content."""
        raise NotImplementedError("BufferedOutputMixin requires _send_buffered()")

    async def _flush_loop(self):
        """Periodically flush buffer."""
        while True:
            await asyncio.sleep(self._flush_interval)
            if self._buffer:
                await self._flush_buffer()


# =============================================================================
# PollingUI - For polling-based backends (HTTP API, WebSocket)
# =============================================================================


class PollingUI(SimpleUI):
    """UI for polling-based backends (HTTP API, WebSocket).

    This class provides output/input queues that external systems can use:
    - output_queue: Messages from AI (external system polls this)
    - input_queue: Responses from user (external system puts to this)

    You need to implement:
    - print(text: str) -> None   # Just queue the output

    Example:
        class HttpAPIUI(PollingUI):
            def print(self, text: str):
                self.output_queue.put_nowait(text)

        # External system uses:
        ui.output_queue.get()  # Poll for AI messages
        ui.input_queue.put("response")  # Provide user input
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.output_queue: asyncio.Queue[str] = asyncio.Queue()
        self.input_queue: asyncio.Queue[str] = asyncio.Queue()

    async def print(self, text: str) -> None:
        """Queue output for external polling.

        Note: This is async for consistency with the base class, but
        internally just puts to a queue (non-blocking).
        """
        self.output_queue.put_nowait(text)

    async def get_input(self, prompt: str) -> str:
        """Block until external system provides input."""
        if prompt:
            await self.print(f"❓ {prompt}")
        return await self.input_queue.get()


# =============================================================================
# Factory Helper - Reduces factory boilerplate to one line
# =============================================================================


def create_ui_factory(
    ui_class: type,
    config: UIConfig | None = None,
    **extra_kwargs,
) -> Callable:
    """Create a UI factory function with minimal boilerplate.

    This replaces the repetitive 8-parameter factory function with
    a one-liner.

    Args:
        ui_class: The UI class to instantiate
        config: Optional UIConfig for custom commands
        **extra_kwargs: Additional kwargs passed to the constructor

    Returns:
        A factory function compatible with llm_chat.set_ui_factory()

    Example:
        # Before (repetitive):
        def create_ui(ctx, llm_task_core, history_manager, ui_commands,
                      initial_message, initial_conversation_name,
                      initial_yolo, initial_attachments):
            return MyUI(
                ctx=ctx, llm_task=llm_task_core, history_manager=history_manager,
                initial_message=initial_message,
                conversation_session_name=initial_conversation_name,
                yolo=initial_yolo, initial_attachments=initial_attachments,
                exit_commands=ui_commands.get("exit", ["/exit"]),
                # ... 10+ more lines
            )

        # After (one liner):
        from zrb.llm.app.simple_ui import create_ui_factory, UIConfig

        config = UIConfig(assistant_name="MyBot")
        llm_chat.set_ui_factory(create_ui_factory(MyUI, config=config, bot=my_bot))
    """
    from typing import Any as AnyType

    from zrb.context.any_context import AnyContext
    from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
    from zrb.llm.task.llm_task import LLMTask

    def factory(
        ctx: AnyContext,
        llm_task_core: LLMTask,
        history_manager: AnyHistoryManager,
        ui_commands: dict[str, list[str]],
        initial_message: str,
        initial_conversation_name: str,
        initial_yolo: bool,
        initial_attachments: list[AnyType],
    ) -> BaseUI:
        # Create config with merged commands
        cfg = config or UIConfig.default()
        if ui_commands:
            cfg = cfg.merge_commands(ui_commands)

        # Set yolo and conversation name from parameters
        cfg.yolo = initial_yolo
        cfg.conversation_session_name = initial_conversation_name

        return ui_class(
            ctx=ctx,
            llm_task=llm_task_core,
            history_manager=history_manager,
            config=cfg,
            initial_message=initial_message,
            initial_attachments=initial_attachments,
            **extra_kwargs,
        )

    return factory
