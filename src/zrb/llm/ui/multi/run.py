"""The wrapper's own event loop.

All children share one process and one conversation, so one of them — the main
child — runs the event loop and the rest are started beside it. Quitting
cancels the message loop, the child tasks and the pending input races, in that
order, so teardown never waits on something it just abandoned.
"""

import asyncio
from typing import Any

from zrb.config.config import CFG
from zrb.llm.ui.any_ui import AnyUI

from .input import MultiUIInput


class MultiUIRunLoop(MultiUIInput):
    """Start every child, run the main one, and unwind them together."""

    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
        return await self.main_ui.input.run_interactive_command(cmd, shell=shell)

    async def _start_child_ui(self, ui: AnyUI) -> None:
        """Start a child UI's event loop if it has one."""
        # `start_event_loop` is EventDrivenUI-only, hence the probe.
        start_event_loop: Any = getattr(ui, "start_event_loop", None)
        if start_event_loop is not None:
            await start_event_loop()
        elif ui is not self.main_ui:
            await ui.run_async()

    async def run_async(self) -> str:
        """Run all child UIs and the shared message loop."""
        main_ui = self.main_ui
        if main_ui is None:
            return ""

        self._last_result_data = None

        self._process_messages_task = asyncio.create_task(self.process_messages_loop())

        self.set_llm_task(main_ui.llm_task)

        for i, ui in enumerate(self._uis):
            if i != self._main_ui_index:
                task = asyncio.create_task(self._start_child_ui(ui))
                self._child_tasks.append(task)

        main_task = asyncio.create_task(main_ui.run_async())

        try:
            await self._await_main_task(main_task)
        finally:
            await self._shut_down_tasks()

        self.last_output = (
            self._last_result_data
            if self._last_result_data is not None
            else (self.main_ui.last_output if self.main_ui is not None else "")
        )
        return self.last_output

    async def _await_main_task(self, main_task: asyncio.Task) -> None:
        """Await the main UI, unwinding it on cancellation without masking that."""
        try:
            await main_task
        except asyncio.CancelledError:
            main_task.cancel()
            # A teardown error must not mask the cancellation.
            try:
                await main_task
            except asyncio.CancelledError:
                pass
            except Exception as unwind_error:
                CFG.LOGGER.warning(
                    f"Main UI error during cancel-unwind: {unwind_error!r}"
                )
            raise
        except Exception as e:
            CFG.LOGGER.debug(f"Main UI task ended with error: {e}")

    async def _shut_down_tasks(self) -> None:
        """Cancel the message loop and child tasks, then wait for them to exit."""
        if self._process_messages_task:
            self._process_messages_task.cancel()
            try:
                await self._process_messages_task
            except asyncio.CancelledError:
                pass

        for task in self._child_tasks:
            task.cancel()
        await asyncio.gather(*self._child_tasks, return_exceptions=True)
        self._child_tasks = []

        for task in self._pending_input_tasks:
            if not task.done():
                task.cancel()
        self._pending_input_tasks = []

    def on_exit(self):
        for task in self._child_tasks:
            task.cancel()
        for task in self._pending_input_tasks:
            task.cancel()
        if self._process_messages_task:
            self._process_messages_task.cancel()
        try:
            self.main_ui.on_exit()
        except Exception as e:
            CFG.LOGGER.debug(f"Main UI on_exit failed: {e}")
