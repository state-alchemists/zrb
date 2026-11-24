from __future__ import annotations

from typing import Protocol


class AnyLiveSubAgentSession(Protocol):
    session_id: str
    history: list[object]
    run_scope: str
    active_task: object | None
    cancelled_by_human: bool

    def is_turn_owner(self) -> bool: ...

    def consume_cancelled_flag(self) -> object: ...

    @property
    def buffered_ui(self) -> object: ...

    @property
    def persist_history(self) -> object | None: ...

    @persist_history.setter
    def persist_history(self, value: object | None) -> None: ...
