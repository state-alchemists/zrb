from __future__ import annotations

from typing import Protocol


class AnyAgentResult(Protocol):
    output: object

    def new_messages(self) -> list[object]: ...
