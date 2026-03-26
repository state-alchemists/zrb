import asyncio
import sys
from typing import Any, TextIO


class MultiUI:
    """UI wrapper that broadcasts output to multiple UIs and waits for first response.

    This class implements UIProtocol and delegates to multiple child UIs:
    - Output is broadcast to ALL child UIs
    - Input waits for FIRST response from ANY child UI
    - Approvals wait for FIRST response from ANY child UI

    Usage:
        multi_ui = MultiUI([terminal_ui, telegram_ui])
        llm_task.set_ui(multi_ui)
    """

    def __init__(self, uis: list[Any]):
        self._uis = uis
        self._pending_uis: list[Any] = []
        self._responses: dict[int, asyncio.Future[str]] = {}

    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
    ):
        for ui in self._uis:
            try:
                ui.append_to_output(*values, sep=sep, end=end, file=file, flush=flush)
            except Exception:
                pass

    async def ask_user(self, prompt: str) -> str:
        if is_shutdown_requested():
            return ""

        self._responses.clear()
        loop = asyncio.get_running_loop()

        for ui in self._uis:
            future = loop.create_future()
            self._responses[id(ui)] = future
            ui.ask_user(prompt)

        try:
            done, _ = await asyncio.wait(
                self._responses.values(), return_when=asyncio.FIRST_COMPLETED
            )
            for future in done:
                if not future.cancelled():
                    return future.result()
            return ""
        finally:
            for future in self._responses.values():
                if not future.done():
                    future.cancel()
            self._responses.clear()

    def stream_to_parent(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
    ):
        for ui in self._uis:
            try:
                ui.stream_to_parent(*values, sep=sep, end=end, file=file, flush=flush)
            except Exception:
                pass

    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
        for ui in self._uis:
            try:
                if hasattr(ui, "run_interactive_command"):
                    await ui.run_interactive_command(cmd, shell=shell)
            except Exception:
                pass
        return 0


def is_shutdown_requested() -> bool:
    return getattr(sys, "_zrb_shutdown_requested", False)
