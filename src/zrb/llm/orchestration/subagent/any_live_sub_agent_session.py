from __future__ import annotations

from typing import Protocol


class AnyLiveSubAgentSession(Protocol):
    run_scope: str
    active_task: object | None
    cancelled_by_human: bool

    def consume_cancelled_flag(self) -> object: ...

    @property
    def buffered_ui(self) -> object: ...

    @property
    def persist_history(self) -> object | None: ...

    @persist_history.setter
    def persist_history(self, value: object | None) -> None: ...
