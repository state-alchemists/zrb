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

    Subclasses implement only `print(text, kind)` and `get_input(prompt)`,
    both async. Extra constructor keywords are accepted for subclass use.

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
        ui_config: UIConfig | None = None,
        initial_message: str = "",
        initial_attachments: "list[UserContent] | None" = None,
        model: str | None = None,
        response_handlers: "list[ResponseHandler] | None" = None,
        tool_policies: "list[ToolPolicy] | None" = None,
        argument_formatters: "list[ArgumentFormatter] | None" = None,
        custom_commands: "list[AnyCustomCommand] | None" = None,
        **kwargs,  # Accepted so subclasses can take extra keywords.
    ):
        super().__init__(
            ctx=ctx,
            llm_task=llm_task,
            history_manager=history_manager,
            initial_message=initial_message,
            initial_attachments=initial_attachments or [],
            ui_config=ui_config or UIConfig.default(),
            triggers=[],
            response_handlers=response_handlers or [],
            tool_policies=tool_policies or [],
            argument_formatters=argument_formatters or [],
            markdown_theme=None,
            custom_commands=custom_commands or [],
            model=model,
        )

    @abstractmethod
    async def print(self, text: str, kind: str) -> None:
        """Display output to the user.

        Must be async: `append_to_output` schedules it with `create_task`.
        For output before the event loop starts, override `append_to_output`.

        Args:
            text: The text to display (already formatted).
            kind: Output kind — one of "text", "progress", "tool_call",
                  "usage", or "thinking".  Use this to apply visual
                  distinction (e.g. faint/italic for non-"text" kinds).
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement print()")

    @abstractmethod
    async def get_input(self, prompt: str) -> str:
        """Display `prompt` (may be empty) and return the user's input."""
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
        """Schedule `print()`; with no running loop, write to stdout instead."""
        text = sep.join(str(v) for v in values) + end
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(self.print(text, kind))
            # asyncio holds scheduled tasks weakly; keep a strong reference.
            if hasattr(self, "_background_tasks"):
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)
        except RuntimeError:
            # No running loop (e.g. during initialization).
            sys.stdout.write(text)
            sys.stdout.flush()

    async def ask_user(
        self,
        prompt: str,
        output_to_parent: str = "",
        agent_id: str | None = None,
    ) -> str:
        """Delegate to `get_input()`."""
        return await self.get_input(prompt)

    async def run_interactive_command(self, cmd: str | list[str], shell: bool = False):
        """Not supported in SimpleUI."""
        await self.print(
            "\n❗ Interactive commands not supported in this UI\n", kind="text"
        )
        return 1

    # Re-raise a cancelled `_run_loop` instead of returning `last_output` —
    # for hosts whose shutdown must see the cancellation (the HTTP UI).
    propagates_cancellation: bool = False

    async def run_async(self) -> str:
        """Run `_run_loop` alongside the message loop; return the last output."""
        self._process_messages_task = asyncio.create_task(self.process_messages_loop())
        if hasattr(self, "_background_tasks"):
            self._background_tasks.add(self._process_messages_task)

        if self._initial_message:
            self.submit_user_message(self.llm_task, self._initial_message)

        was_cancelled = False
        try:
            await self._run_loop()
        except asyncio.CancelledError:
            was_cancelled = True
        finally:
            self._process_messages_task.cancel()
            try:
                await self._process_messages_task
            except asyncio.CancelledError:
                pass
            finally:
                if hasattr(self, "_background_tasks"):
                    self._background_tasks.discard(self._process_messages_task)

        if was_cancelled and self.propagates_cancellation:
            raise asyncio.CancelledError()
        return self.last_output

    async def _run_loop(self) -> None:
        """Override this for custom event loop (e.g., WebSocket listener)."""
        while True:
            await asyncio.sleep(CFG.LLM_UI_STATUS_INTERVAL / 1000)
