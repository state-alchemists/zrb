"""What the composite UI *is*: its children, its conversation, its bookkeeping.

The parts around this module all act on the same object, so the object's state
lives in one place they can all reach rather than being re-declared by each of
them. The session members are read and written on the main child, because that
child owns the one conversation every interface is showing.
"""

import asyncio
from typing import TYPE_CHECKING, Any

from zrb.llm.ui.any_ui import AnyUI
from zrb.llm.ui.base.message_queue import MessageQueue
from zrb.llm.ui.fallback.state_defaults import UIStateDefaultsMixin

if TYPE_CHECKING:
    from pydantic_ai.models import Model

    from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
    from zrb.llm.snapshot.manager import SnapshotManager
    from zrb.llm.ui.base.conversation_commands import BaseUIConversationCommands


class MultiUIState(UIStateDefaultsMixin):
    """The children, the shared queue, and the conversation they share."""

    def __init__(self, uis: list[AnyUI], main_ui_index: int = 0):
        if uis and not -len(uis) <= main_ui_index < len(uis):
            raise ValueError(
                f"MultiUI got main_ui_index={main_ui_index} for {len(uis)} UI(s); "
                f"it must be between {-len(uis)} and {len(uis) - 1}."
            )
        self._uis = uis
        # Normalized so `run_async` can compare it with `enumerate` positions.
        self._main_ui_index = main_ui_index % len(uis) if uis else main_ui_index
        self._last_output: str = ""
        self._child_tasks: list[asyncio.Task] = []
        self._pending_input_tasks: list[asyncio.Task] = []
        self._message_queue: MessageQueue = MessageQueue()
        self._active_run_context: Any = None
        self.shell_cut_signal = None  # the turn's cut signal, set by the runner
        self._process_messages_task: asyncio.Task | None = None
        self._running_llm_task: asyncio.Task | None = None
        # The task whose cancellation has already been announced to the memory
        # hooks, as `BaseUI` keeps it: one cut turn, one event line.
        self._announced_cancel_task: asyncio.Task | None = None
        self._is_thinking: bool = False
        self._last_result_data: str | None = None
        self._llm_task: Any = None
        self._approval_channel: Any = None
        self._last_winning_ui: Any = None
        self._tool_call_handler: Any = None
        for ui in self._uis:
            ui.multi_ui_parent = self

    def set_tool_call_handler(self, handler: Any):
        """Set the tool call handler (normally the default UI's own)."""
        self._tool_call_handler = handler

    @property
    def tool_call_handler(self) -> Any:
        """Get the tool call handler."""
        return self._tool_call_handler

    @property
    def last_winning_ui(self) -> Any:
        """The child UI whose input won the last confirmation race, if any."""
        return self._last_winning_ui

    @last_winning_ui.setter
    def last_winning_ui(self, value: Any) -> None:
        self._last_winning_ui = value

    @property
    def child_tasks(self) -> list[asyncio.Task]:
        """Background tasks spawned per-child (e.g. trigger loops)."""
        return self._child_tasks

    @child_tasks.setter
    def child_tasks(self, value: list[asyncio.Task]) -> None:
        self._child_tasks = value

    @property
    def pending_input_tasks(self) -> list[asyncio.Task]:
        """In-flight `ask_user`/`ask_user_choice` races across child UIs."""
        return self._pending_input_tasks

    @pending_input_tasks.setter
    def pending_input_tasks(self, value: list[asyncio.Task]) -> None:
        self._pending_input_tasks = value

    @property
    def process_messages_task(self) -> "asyncio.Task | None":
        """The background task running `process_messages_loop`, if started."""
        return self._process_messages_task

    @process_messages_task.setter
    def process_messages_task(self, value: "asyncio.Task | None") -> None:
        self._process_messages_task = value

    def set_approval_channel(self, channel: Any):
        """Set the approval channel for tool confirmations."""
        self._approval_channel = channel

    @property
    def children(self) -> list[Any]:
        """The wrapped child UIs."""
        return list(self._uis)

    @property
    def main_ui(self) -> Any:
        return self._uis[self._main_ui_index] if self._uis else None

    @property
    def is_local(self) -> bool:
        """Whether every child's user sits at this machine. A MultiUI is
        only as local as its least-local child: any child can submit a
        command whose capture is queued for the shared conversation, so a
        single remote child means a capture would expose the machine zrb
        runs on to a user who cannot see it."""
        return all(child.is_local for child in self._uis) if self._uis else False

    @property
    def last_output(self) -> str:
        """The last answer rendered through this MultiUI."""
        return self._last_output

    @last_output.setter
    def last_output(self, value: str) -> None:
        self._last_output = value

    # State the main child owns, read and written there.
    @property
    def model(self) -> "str | Model | None":
        return self.main_ui.model if self.main_ui is not None else None

    @model.setter
    def model(self, value: "str | Model | None") -> None:
        if self.main_ui is not None:
            self.main_ui.model = value

    @property
    def small_model(self) -> "str | Model | None":
        return self.main_ui.small_model if self.main_ui is not None else None

    @small_model.setter
    def small_model(self, value: "str | Model | None") -> None:
        if self.main_ui is not None:
            self.main_ui.small_model = value

    @property
    def multimodal_model(self) -> "str | Model | None":
        return self.main_ui.multimodal_model if self.main_ui is not None else None

    @multimodal_model.setter
    def multimodal_model(self, value: "str | Model | None") -> None:
        if self.main_ui is not None:
            self.main_ui.multimodal_model = value

    @property
    def conversation_session_name(self) -> str:
        return (
            self.main_ui.conversation_session_name if self.main_ui is not None else ""
        )

    @conversation_session_name.setter
    def conversation_session_name(self, value: str) -> None:
        if self.main_ui is not None:
            self.main_ui.conversation_session_name = value

    @property
    def plan_mode_active(self) -> bool:
        return self.main_ui.plan_mode_active if self.main_ui is not None else False

    @plan_mode_active.setter
    def plan_mode_active(self, value: bool) -> None:
        if self.main_ui is not None:
            self.main_ui.plan_mode_active = value

    @property
    def yolo(self) -> bool | frozenset:
        return self.main_ui.tools.yolo if self.main_ui is not None else False

    @property
    def conversation(self) -> "BaseUIConversationCommands | None":
        """The conversation the main child manages, or None with no child.

        Reached on the primary child for the same reason as the session
        members above: one conversation is open, and that child owns it.
        """
        return self.main_ui.conversation if self.main_ui is not None else None

    @property
    def snapshot_manager(self) -> "SnapshotManager | None":
        return self.main_ui.snapshot_manager if self.main_ui is not None else None

    @property
    def history_manager(self) -> "AnyHistoryManager | None":
        return self.main_ui.history_manager if self.main_ui is not None else None

    @property
    def llm_task(self) -> Any:
        return self._llm_task

    @llm_task.setter
    def llm_task(self, value: Any) -> None:
        self.set_llm_task(value)

    @property
    def message_queue(self) -> "MessageQueue":
        """The shared queue every child UI's turn is submitted through."""
        return self._message_queue

    @property
    def is_thinking(self) -> bool:
        """Whether a turn is currently streaming through this MultiUI."""
        return self._is_thinking

    @is_thinking.setter
    def is_thinking(self, value: bool) -> None:
        self._is_thinking = value

    @property
    def last_result_data(self) -> "str | None":
        """The raw last-turn result, or None before any turn has completed."""
        return self._last_result_data

    @last_result_data.setter
    def last_result_data(self, value: "str | None") -> None:
        self._last_result_data = value

    @property
    def active_run_context(self) -> Any:
        """The live `RunContext` of the streaming turn, or None; lets
        `submit_user_message` steer into it."""
        return self._active_run_context

    @active_run_context.setter
    def active_run_context(self, ctx: Any) -> None:
        self._active_run_context = ctx

    def set_llm_task(self, llm_task: Any):
        """Set the LLM task for shared processing."""
        self._llm_task = llm_task
        for ui in self._uis:
            ui.session.llm_task = llm_task
