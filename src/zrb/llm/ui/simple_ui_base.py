from __future__ import annotations

import asyncio
import logging
import sys
from abc import abstractmethod
from typing import TYPE_CHECKING, TextIO

from zrb.config.config import CFG
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.ui.base.ui import BaseUI
from zrb.llm.ui.ui_config import UIConfig

if TYPE_CHECKING:
    from zrb.context.any_context import AnyContext
    from zrb.llm.agent.types import UserContent
    from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
    from zrb.llm.task.llm_task import LLMTask
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

        llm_chat.ui_factories = [create_ui_factory(MyUI)]
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
        custom_commands: "list[AnyCustomCommand] | None" = None,
        **kwargs,  # Accept extra kwargs for easy subclassing
    ):
        self._config = config or UIConfig.default()

        super().__init__(
            ctx=ctx,
            llm_task=llm_task,
            history_manager=history_manager,
            initial_message=initial_message,
            initial_attachments=initial_attachments or [],
            ui_config=self._config,
            triggers=[],  # Empty list for triggers
            response_handlers=response_handlers or [],
            tool_policies=tool_policies or [],
            argument_formatters=argument_formatters or [],
            markdown_theme=None,
            custom_commands=custom_commands or [],
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
            task = loop.create_task(self.print(text, kind))
            # asyncio only holds a weak reference to a scheduled task — without
            # a strong reference somewhere, it can be garbage-collected mid-
            # execution. Track it the same way every other fire-and-forget
            # task in this package does (base/ui.py, base/commands.py,
            # base/conversation_commands.py).
            if hasattr(self, "_background_tasks"):
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)
        except RuntimeError:
            # No running event loop - fall back to synchronous print
            # This can happen during initialization or in edge cases

            sys.stdout.write(text)
            sys.stdout.flush()

    async def ask_user(
        self,
        prompt: str,
        output_to_parent: str = "",
        agent_id: str | None = None,
    ) -> str:
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
        self._process_messages_task = asyncio.create_task(self.process_messages_loop())
        # Add to background tasks to prevent premature garbage collection
        if hasattr(self, "_background_tasks"):
            self._background_tasks.add(self._process_messages_task)

        if self._initial_message:
            self.submit_user_message(self._llm_task, self._initial_message)

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
                if hasattr(self, "_background_tasks"):
                    self._background_tasks.discard(self._process_messages_task)

        return self.last_output

    async def _run_loop(self) -> None:
        """Override this for custom event loop (e.g., WebSocket listener)."""
        while True:
            await asyncio.sleep(CFG.LLM_UI_STATUS_INTERVAL / 1000)
