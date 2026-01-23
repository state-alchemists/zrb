from __future__ import annotations

from typing import Any, Protocol, TextIO


class UIProtocol(Protocol):
    async def ask_user(self, prompt: str) -> str: ...

    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
    ): ...

    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any: ...
