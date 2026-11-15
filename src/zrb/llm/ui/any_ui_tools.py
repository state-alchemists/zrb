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

    @property
    def sandbox_override(self) -> bool | None:
        """This session's `/sandbox` choice: True, False, or None for `CFG`.

        Read once per tool call, next to `CFG.LLM_SANDBOX_ENABLED`, because a
        toggle belongs to the conversation that made it: a second session in
        the same process must not inherit it, and the deployment's setting must
        survive it. Concrete rather than abstract so a UI with no switch of its
        own — the headless floor, a stand-in in a test — says nothing and lets
        the deployment decide. Read-only here; `BaseUI` adds the setter.
        """
        return None

    @property
    def sandbox_run_policy(self) -> bool | None:
        """What the run in this session was explicitly given, or None.

        Published by the runner and cleared when the run ends. It exists
        because a run's policy reaches the gate through `deps` — a value the
        task drawing the status bar cannot see. Concrete for the same reason
        `sandbox_override` is: a UI that never holds a run says nothing.
        """
        return None

    @property
    def judge_override(self) -> bool | None:
        """This session's `/judge` choice: True, False, or None for `CFG`.

        Read once per judged command, for the same reason `sandbox_override` is
        read per tool call: the toggle belongs to the conversation that made it.
        Concrete rather than abstract so a UI with no switch of its own says
        nothing and lets the deployment decide. Read-only here; `BaseUI` adds
        the setter.
        """
        return None

    @abstractmethod
    def cancel_pending_confirmations(self, flush: bool = True) -> None:
        """Release any `ask_user` call blocked on a tool confirmation.

        A no-op for UIs that never hold one. `flush=False` from the Ctrl+C /
        exit path, where writing buffered tokens is wasted work.
        """
