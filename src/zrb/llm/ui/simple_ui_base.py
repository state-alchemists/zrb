import asyncio
import logging
from abc import abstractmethod
from typing import TYPE_CHECKING, Any, TextIO

from zrb.config.config import CFG
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.task.llm_task import LLMTask
from zrb.llm.ui.base.ui import BaseUI
from zrb.llm.ui.ui_config import UIConfig

if TYPE_CHECKING:
    from pydantic_ai import UserContent

    from zrb.context.any_context import AnyContext
    from zrb.llm.tool_call.middleware import (
        ArgumentFormatter,
        ResponseHandler,
        ToolPolicy,
    )

logger = logging.getLogger(__name__)


class SimpleUI(BaseUI):
    """Simplified UI for basic request-response backends.

    This class reduces boilerplate by providing:
    - Default run_async() implementation
    - Simplified abstract methods (print, get_input vs append_to_output, ask_user)
    - Configuration via UIConfig dataclass
    - Flexible __init__ that accepts **kwargs for easy subclassing

    You only need to implement:
    - print(text: str, kind: str) -> None  # Display output
    - get_input(prompt: str) -> str        # Get user input (async)

    Constructor Parameters:
        ctx: Required context (AnyContext)
        llm_task: Required LLM task (LLMTask)
        history_manager: Required history manager (AnyHistoryManager)
        config: Optional UIConfig for customizing commands and behavior
        initial_message: Optional initial message to send
        initial_attachments: Optional file attachments
        model: Optional model override
        **kwargs: Additional kwargs passed through (for subclass use)

    Example:
        class MyUI(SimpleUI):
            async def print(self, text: str, kind: str) -> None:
                print(text, end="", flush=True)

            async def get_input(self, prompt: str) -> str:
                return await asyncio.to_thread(input, prompt)

        # In your zrb_init.py:
        from zrb.llm.ui import create_ui_factory

        llm_chat.set_ui_factory(create_ui_factory(MyUI))
    """

    def __init__(
        self,
        ctx: "AnyContext",
        llm_task: LLMTask,
        history_manager: AnyHistoryManager,
        config: UIConfig | None = None,
        initial_message: str = "",
        initial_attachments: "list[UserContent] | None" = None,
        model: str | None = None,
        response_handlers: "list[ResponseHandler] | None" = None,
        tool_policies: "list[ToolPolicy] | None" = None,
        argument_formatters: "list[ArgumentFormatter] | None" = None,
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
            is_yolo=self._config.is_yolo,
            triggers=[],  # Empty list for triggers
            response_handlers=response_handlers or [],
            tool_policies=tool_policies or [],
            argument_formatters=argument_formatters or [],
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

    @abstractmethod
    async def print(self, text: str, kind: str) -> None:
        """Display output to user.

        This is a simplified version of append_to_output().
        Just print/emit/send the text, using ``kind`` for visual distinction.

        IMPORTANT: This MUST be an async method (use `async def print()`).
        SimpleUI.append_to_output() uses asyncio.create_task() to schedule
        this method, which requires a coroutine object.

        If you need synchronous output during initialization (before the
        event loop starts), override append_to_output() directly.

        Args:
            text: The text to display (already formatted).
            kind: Output kind — one of "text", "progress", "tool_call",
                  "usage", or "thinking".  Use this to apply visual
                  distinction (e.g. faint/italic for non-"text" kinds).
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

    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ):
        """Default implementation - calls simplified print().

        This method is called synchronously by BaseUI during streaming.
        It schedules the async print() method using create_task().

        Sync Fallback: If no event loop is running (e.g., during initialization
        or in tests), this falls back to writing directly to stdout. This
        bypasses the subclass print() method entirely.

        If you need to handle output before the event loop starts, override
        this method directly instead of print().
        """
        text = sep.join(str(v) for v in values) + end
        # Schedule the async print in the running event loop
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.print(text, kind))
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
        await self.print(
            "\n⚠️ Interactive commands not supported in this UI\n", kind="text"
        )
        return 1

    async def run_async(self) -> str:
        """Default implementation - handles common pattern."""
        # Start message processing
        self._process_messages_task = asyncio.create_task(self._process_messages_loop())
        # Add to background tasks to prevent premature garbage collection
        if hasattr(self, "_background_tasks"):
            self._background_tasks.add(self._process_messages_task)

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
            finally:
                # Remove from background tasks
                if hasattr(self, "_background_tasks"):
                    self._background_tasks.discard(self._process_messages_task)

        return self.last_output

    async def _run_loop(self):
        """Override this for custom event loop (e.g., WebSocket listener)."""
        while True:
            await asyncio.sleep(CFG.LLM_UI_STATUS_INTERVAL / 1000)
