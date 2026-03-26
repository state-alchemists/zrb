import asyncio
import sys
from typing import Any, TextIO


class MultiUI:
    """UI wrapper that broadcasts output to multiple UIs and waits for first response.

    This class implements UIProtocol and delegates to multiple child UIs:
    - Output is broadcast to ALL child UIs
    - Input waits for FIRST response from ANY child UI
    - Main UI (first by default) runs the LLM message loop
    - Other UIs (EventDriven) have their event loops started

    Usage:
        multi_ui = MultiUI([terminal_ui, telegram_ui])
        llm_task.set_ui(multi_ui)
    """

    def __init__(self, uis: list[Any], main_ui_index: int = 0):
        self._uis = uis
        self._main_ui_index = main_ui_index
        self._responses: dict[int, asyncio.Future[str]] = {}
        self.last_output: str = ""
        self._shutdown_event: asyncio.Event | None = None
        self._child_tasks: list[asyncio.Task] = []

    @property
    def _main_ui(self) -> Any:
        return self._uis[self._main_ui_index] if self._uis else None

    def append_to_output(
        self,
        *values,
        sep=" ",
        end="\n",
        file: TextIO | None = None,
        flush: bool = False,
        **kwargs
    ):
        for ui in self._uis:
            try:
                ui.append_to_output(
                    *values, sep=sep, end=end, file=file, flush=flush, **kwargs
                )
            except Exception:
                pass

    async def ask_user(self, prompt: str) -> str:
        if is_shutdown_requested():
            return ""

        self._responses.clear()
        loop = asyncio.get_running_loop()

        # Prompt all UIs that support input
        for i, ui in enumerate(self._uis):
            if i == self._main_ui_index:
                continue
            try:
                if hasattr(ui, "ask_user"):
                    ui.ask_user(prompt)
            except Exception:
                pass

        # Main UI blocks for input
        try:
            return await self._main_ui.ask_user(prompt)
        except Exception:
            return ""

    def stream_to_parent(
        self,
        *values,
        sep=" ",
        end="\n",
        file: TextIO | None = None,
        flush: bool = False,
        **kwargs
    ):
        for ui in self._uis:
            try:
                ui.stream_to_parent(
                    *values, sep=sep, end=end, file=file, flush=flush, **kwargs
                )
            except Exception:
                pass

    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
        return await self._main_ui.run_interactive_command(cmd, shell=shell)

    async def _start_child_ui(self, ui: Any) -> None:
        """Start a child UI's event loop if it has one."""
        if hasattr(ui, "start_event_loop"):
            await ui.start_event_loop()
        elif hasattr(ui, "run_async") and ui is not self._main_ui:
            await ui.run_async()

    async def run_async(self) -> str:
        """Run all child UIs and the main UI's message loop."""
        if not self._main_ui:
            return ""

        self._shutdown_event = asyncio.Event()

        # Start all child UIs' event loops (except main UI)
        for i, ui in enumerate(self._uis):
            if i != self._main_ui_index:
                task = asyncio.create_task(self._start_child_ui(ui))
                self._child_tasks.append(task)

        # Run main UI's async loop (which includes LLM message loop)
        main_task = asyncio.create_task(self._main_ui.run_async())

        try:
            await main_task
        except asyncio.CancelledError:
            main_task.cancel()
            await main_task
        except Exception:
            pass
        finally:
            # Cancel child tasks
            for task in self._child_tasks:
                task.cancel()
            await asyncio.gather(*self._child_tasks, return_exceptions=True)
            self._child_tasks = []

        self.last_output = getattr(self._main_ui, "last_output", "")
        return self.last_output

    def on_exit(self):
        if self._shutdown_event:
            self._shutdown_event.set()
        for task in self._child_tasks:
            task.cancel()
        try:
            self._main_ui.on_exit()
        except Exception:
            pass


def is_shutdown_requested() -> bool:
    return getattr(sys, "_zrb_shutdown_requested", False)
