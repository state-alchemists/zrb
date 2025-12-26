import asyncio
import os
from asyncio import StreamReader
from typing import TYPE_CHECKING, Any, Callable, Coroutine

from zrb.builtin.llm.chat_completion import get_chat_completer
from zrb.context.any_context import AnyContext
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
        self, reader: "PromptSession[Any] | StreamReader", ctx: AnyContext
    ) -> str:
        trigger_tasks = [
            asyncio.create_task(run_async(self._read_next_line(reader, ctx)))
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
        self, reader: "PromptSession[Any] | StreamReader", ctx: AnyContext
    ) -> str:
        """Reads one line of input using the provided reader."""
        from prompt_toolkit import PromptSession

        try:
            if isinstance(reader, PromptSession):
                bottom_toolbar = f"📁 Current directory: {os.getcwd()}"
                return await reader.prompt_async(
                    completer=get_chat_completer(), bottom_toolbar=bottom_toolbar
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


llm_chat_trigger = LLMChatTrigger()
