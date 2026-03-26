from __future__ import annotations

import asyncio
from abc import abstractmethod
from typing import TYPE_CHECKING, TextIO

from zrb.llm.app.ui.base_ui import BaseUI
from zrb.llm.app.ui.config import UIConfig

if TYPE_CHECKING:
    from pydantic_ai import UserContent

    from zrb.context.any_context import AnyContext
    from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
    from zrb.llm.task.llm_task import LLMTask


class SimpleUI(BaseUI):
    def __init__(
        self,
        ctx: "AnyContext",
        llm_task: "LLMTask",
        history_manager: "AnyHistoryManager",
        config: UIConfig | None = None,
        initial_message: str = "",
        initial_attachments: list["UserContent"] | None = None,
        model: str | None = None,
        **kwargs,
    ):
        self._config = config or UIConfig.default()
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
            triggers=[],
            response_handlers=[],
            tool_policies=[],
            argument_formatters=[],
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
    async def print(self, text: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_input(self, prompt: str) -> str:
        raise NotImplementedError

    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
    ):
        text = sep.join(str(v) for v in values) + end
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.print(text))
        except RuntimeError:
            import sys

            sys.stdout.write(text)
            sys.stdout.flush()

    async def ask_user(self, prompt: str) -> str:
        return await self.get_input(prompt)

    async def run_interactive_command(self, cmd: str | list[str], shell: bool = False):
        await self.print("\n⚠️ Interactive commands not supported in this UI\n")
        return 1

    async def run_async(self) -> str:
        self._process_messages_task = asyncio.create_task(self._process_messages_loop())
        if self._initial_message:
            self._submit_user_message(self._llm_task, self._initial_message)
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
        while True:
            await asyncio.sleep(1)
