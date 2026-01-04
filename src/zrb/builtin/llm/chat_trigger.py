import asyncio
import os
from asyncio import StreamReader
from typing import TYPE_CHECKING, Any, Callable, Coroutine

from zrb.builtin.llm.chat_completion import get_chat_completer
from zrb.config.llm_config import llm_config
from zrb.context.any_context import AnyContext
from zrb.util.git import get_current_branch
from zrb.util.run import run_async

if TYPE_CHECKING:
    from prompt_toolkit import PromptSession


ChatTrigger = Callable[[AnyContext], Coroutine[Any, Any, str] | str]


class LLMChatTrigger:

    def __init__(self):
        self._triggers: list[ChatTrigger] = []

    def add_trigger(self, *trigger: ChatTrigger):
        self.append_trigger(*trigger)

    def append_trigger(self, *trigger: ChatTrigger):
        for single_trigger in trigger:
            self._triggers.append(single_trigger)

    async def wait(
        self,
        ctx: AnyContext,
        reader: "PromptSession[Any] | StreamReader",
        current_session_name: str | None,
        is_first_time: bool,
    ) -> str:
        trigger_tasks = [
            asyncio.create_task(
                run_async(
                    self._read_next_line(
                        ctx, reader, current_session_name, is_first_time
                    )
                )
            )
        ] + [asyncio.create_task(run_async(trigger(ctx))) for trigger in self._triggers]
        final_result: str = ""
        try:
            done, pending = await asyncio.wait(
                trigger_tasks, return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                final_result = await task
            if pending:
                for task in pending:
                    task.cancel()
            for task in done:
                break
        except asyncio.CancelledError:
            ctx.print("Task cancelled.", plain=True)
            final_result = "/bye"
        except KeyboardInterrupt:
            ctx.print("KeyboardInterrupt detected. Exiting...", plain=True)
            final_result = "/bye"
        return final_result

    async def _read_next_line(
        self,
        ctx: AnyContext,
        reader: "PromptSession[Any] | StreamReader",
        current_session_name: str | None,
        is_first_time: bool,
    ) -> str:
        """Reads one line of input using the provided reader."""
        from prompt_toolkit import PromptSession

        try:
            if isinstance(reader, PromptSession):
                bottom_toolbar = await self._get_bottom_toolbar(
                    ctx, current_session_name, is_first_time
                )
                return await reader.prompt_async(
                    completer=get_chat_completer(),
                    bottom_toolbar=bottom_toolbar,
                )
            line_bytes = await reader.readline()
            if not line_bytes:
                return "/bye"  # Signal to exit
            user_input = line_bytes.decode().strip()
            ctx.print(user_input, plain=True)
            return user_input
        except KeyboardInterrupt:
            ctx.print("KeyboardInterrupt detected. Exiting...", plain=True)
            return "/bye"

    async def _get_bottom_toolbar(
        self, ctx: AnyContext, current_session_name: str | None, is_first_time: bool
    ) -> str:
        import shutil

        terminal_width = shutil.get_terminal_size().columns
        previous_session_name = self._get_previous_session_name(
            ctx, current_session_name, is_first_time
        )
        current_branch = await self._get_current_branch()
        current_model = self._get_current_model(ctx)
        left_text = f"📌 {os.getcwd()} ({current_branch}) | 🧠 {current_model}"
        right_text = f"📚 Previous Session: {previous_session_name}"
        padding = (
            terminal_width
            - self._get_display_width(left_text)
            - self._get_display_width(right_text)
            - 1
        )
        if padding > 0:
            return f"{left_text}{' ' * padding}{right_text}"
        return f"{left_text} {right_text}"

    def _get_display_width(self, text: str) -> int:
        import unicodedata

        width = 0
        for char in text:
            eaw = unicodedata.east_asian_width(char)
            if eaw in ("F", "W"):  # Fullwidth or Wide
                width += 2
            elif eaw == "A":  # Ambiguous
                width += 1  # Usually 1 in non-East Asian contexts
            else:  # Narrow, Halfwidth, Neutral
                width += 1
        return width

    def _get_current_model(self, ctx: AnyContext) -> str:
        if "model" in ctx.input and ctx.input.model:
            return ctx.input.model
        return str(llm_config.default_model_name)

    def _get_previous_session_name(
        self, ctx: AnyContext, current_session_name: str | None, is_first_time: bool
    ) -> str:
        if is_first_time:
            start_new: bool = ctx.input.start_new
            if (
                not start_new
                and "previous_session" in ctx.input
                and ctx.input.previous_session is not None
            ):
                return ctx.input.previous_session
            return "<No Session>"
        if not current_session_name:
            return "<No Session>"
        return current_session_name

    async def _get_current_branch(self) -> str:
        try:
            return await get_current_branch(os.getcwd(), print_method=lambda x: x)
        except Exception:
            return "<Not a git repo>"


llm_chat_trigger = LLMChatTrigger()
