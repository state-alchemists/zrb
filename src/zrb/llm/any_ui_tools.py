"""The UI's tool-call surface: the call's lifecycle and its approval state."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AnyUITools(ABC):
    """A UI that shows a tool call is the one that confirms it."""

    @abstractmethod
    def start_tool_call(self, tool_name: str, tool_call_id: str) -> None:
        """Note that a tool call is about to run."""

    @abstractmethod
    def end_tool_call(self, tool_call_id: str | None = None) -> None:
        """Note that a tool call finished; ``None`` means every call."""

    @property
    @abstractmethod
    def tool_call_handler(self) -> Any:
        """This UI's tool-call confirmation handler, or None when it has none."""

    @property
    @abstractmethod
    def yolo(self) -> bool | frozenset:
        """Auto-approval state: False, True, or the set of auto-approved tools.

        Read-only here; `BaseUI` adds the setter.
        """

    @abstractmethod
    def cancel_pending_confirmations(self, flush: bool = True) -> None:
        """Release any `ask_user` call blocked on a tool confirmation.

        A no-op for UIs that never hold one. `flush=False` from the Ctrl+C /
        exit path, where writing buffered tokens is wasted work.
        """
