"""Abstract base class for every chat UI in zrb.

Owns conversation state that all concrete UIs share: history manager,
snapshot manager, message queue, confirmation queue, attachments, system
info, hook execution, and the slash-command dispatch (composed via
`BaseUICommands`). Concrete subclasses pick a rendering layer:

  default/ui.py          - prompt-toolkit TUI (the `zrb llm chat` default)
  simple_ui_base.py      - bring-your-own print/input (for headless callers)
  std_ui.py              - stdout streaming (e.g. CI / non-interactive)
  multi_ui.py            - fan-out to multiple UIs at once
  runner/chat/http_ui.py - SSE-streamed UI for the web chat endpoint

For how slash commands are dispatched, see `commands.py`. For how a
single chat turn flows from CLI down through this class, see
docs/llm/llm-chat-lifecycle.md.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections.abc import AsyncIterable, Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any, NamedTuple, TextIO, cast

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.context.shared_context import SharedContext
from zrb.llm.agent_state import get_current_ui
from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent
from zrb.llm.input_source import KEYBOARD_INPUT, InputProvenance
from zrb.llm.permission.state import (
    AgentMode,
    get_current_agent_mode,
    set_current_agent_mode,
)
from zrb.llm.snapshot.manager import SnapshotManager
from zrb.llm.tool_call import (
    ArgumentFormatter,
    ResponseHandler,
    ToolCallHandler,
    ToolPolicy,
    default_response_handler,
)
from zrb.llm.tool_call.choice_spec_format import format_choice_spec
from zrb.llm.ui.any_ui import AnyUI
from zrb.llm.ui.base.commands import BaseUICommands
from zrb.llm.ui.base.confirmation_state import BaseUIConfirmationState
from zrb.llm.ui.base.message_queue import (
    MessageQueue,
    QueuedMessage,
    submit_user_message_via_queue,
)
from zrb.llm.ui.base.persona_state import BaseUIPersonaState
from zrb.llm.ui.base.replay import BaseUIReplay
from zrb.llm.ui.base.system_info import BaseUISystemInfo
from zrb.llm.ui.base.triggers import BaseUITriggers
from zrb.llm.ui.base.usage import BaseUIUsage
from zrb.llm.ui.multi_ui import create_combined_ui
from zrb.llm.ui.state_defaults import UIStateDefaultsMixin
from zrb.llm.ui.turn_hooks import get_turn_hook_manager
from zrb.llm.ui.turn_snapshot import take_pre_turn_snapshot
from zrb.llm.ui.ui_config import UIConfig
from zrb.session.any_session import AnySession
from zrb.session.session import Session
from zrb.task.any_task import AnyTask
from zrb.util.cli.markdown import render_markdown
from zrb.util.cli.style import stylize_muted
from zrb.util.exception import exception_summary
from zrb.util.string.name import get_random_name
from zrb.util.todo.duration import parse_duration
from zrb.xcom.xcom import Xcom

InputSource = InputProvenance | None

if TYPE_CHECKING:
    from rich.theme import Theme

    from zrb.llm.agent.types import (
        Model,
        RequestUsage,
        RunUsage,
        ToolApproved,
        ToolCallPart,
        ToolDenied,
        UserContent,
    )
    from zrb.llm.task.llm_task import LLMTask
    from zrb.llm.ui.any_ui import ChoiceSpec

logger = logging.getLogger(__name__)


class RunningTool(NamedTuple):
    """A tool call currently executing; ``started_at`` is ``time.monotonic()``."""

    tool_name: str
    tool_call_id: str
    started_at: float


def _default_list(value: "Any") -> list:
    """`list(value or [])`; keeps `__init__` under the complexity ratchet."""
    return list(value or [])


def _command_alias_property(key: str, label: str) -> property:
    """A `list[str]` property backed by `self._ui_config.{key}_commands`."""

    def getter(self: "BaseUI") -> list[str]:
        return getattr(self._ui_config, f"{key}_commands")

    def setter(self: "BaseUI", value: list[str]) -> None:
        setattr(self._ui_config, f"{key}_commands", value)

    getter.__doc__ = f"Get the list of {label} commands."
    return property(getter, setter)


def _broadcast_echo(ui: AnyUI, call: Callable[[AnyUI], object]) -> None:
    """Call `call` on every UI holding its own echo of a queued message.

    That is every `MultiUI` child, or the UI alone. A child that raises does
    not stop the rest.
    """
    parent = ui.multi_ui_parent
    for target in parent.children if parent else [ui]:
        try:
            call(target)
        except Exception as e:
            CFG.LOGGER.debug(f"Child UI echo update failed: {e}")


class BaseUI(UIStateDefaultsMixin, AnyUI):
    """The chat session itself, minus how it draws.

    `BaseUI` runs the message loop, slash-command dispatch, tool approvals,
    history and model switching. A subclass supplies rendering and input for
    one backend — a terminal, Telegram, a websocket, a test double — and
    inherits the rest.

    Override `append_to_output` and `ask_user`; `run_interactive_command`
    and `run_async` as the backend needs. `SimpleUI` (blocking input) and
    `EventDrivenUI` (callback input) are smaller entry points that already
    implement `run_async`. Register with `create_ui_factory(MyUI)`; see
    `docs/llm/llm-custom-ui.md`.

    Example:
        A backend that reads and writes one line at a time::

            class MyUI(BaseUI):
                def append_to_output(
                    self, *values, sep=" ", end="\\n", kind="text", **kwargs
                ):
                    print(sep.join(str(v) for v in values), end=end)

                async def ask_user(self, prompt, output_to_parent="", agent_id=None) -> str:
                    if prompt:
                        print(prompt, end="", flush=True)
                    return await asyncio.to_thread(input)

                async def run_interactive_command(self, cmd, shell=False):
                    proc = await asyncio.create_subprocess_shell(cmd)
                    await proc.wait()

                async def run_async(self):
                    self.process_messages_task = asyncio.create_task(
                        self.process_messages_loop()
                    )
                    if self.initial_message:
                        self.submit_user_message(self.llm_task, self.initial_message)
                    try:
                        while True:
                            await asyncio.sleep(CFG.LLM_UI_STATUS_INTERVAL / 1000)
                    except asyncio.CancelledError:
                        pass
                    finally:
                        self.process_messages_task.cancel()
    """

    def __init__(
        self,
        ctx: AnyContext,
        llm_task: LLMTask,
        history_manager: AnyHistoryManager,
        initial_message: Any = "",
        initial_attachments: "list[UserContent] | None" = None,
        ui_config: UIConfig | None = None,
        triggers: list[Callable[[], AsyncIterable[Any]]] | None = None,
        response_handlers: list[ResponseHandler] | None = None,
        tool_policies: list[ToolPolicy] | None = None,
        argument_formatters: list[ArgumentFormatter] | None = None,
        markdown_theme: "Theme | None" = None,
        custom_commands: list[AnyCustomCommand] | None = None,
        model: "Model | str | None" = None,
        enable_rewind: bool = False,
        snapshot_dir: str = "",
    ):
        self._ui_config = ui_config or UIConfig()
        self._ctx = ctx
        # Per-instance fallback so ad-hoc UIs never share an xcom slot.
        self._yolo_xcom_key = self._ui_config.yolo_xcom_key or f"_yolo_{id(self)}"
        self._running_llm_task: asyncio.Task | None = None
        self.llm_task = llm_task
        self._history_manager = history_manager
        self._assistant_name = self._ui_config.assistant_name
        self._initial_message = initial_message
        self._conversation_session_name = self._ui_config.conversation_session_name
        if not self._conversation_session_name:
            self._conversation_session_name = get_random_name()
        self.model = model
        self._small_model: Any = None
        self._multimodal_model: Any = None
        self.persona = BaseUIPersonaState()
        self._triggers = _default_list(triggers)
        self._markdown_theme = markdown_theme
        self._custom_commands = _default_list(custom_commands)
        self._plan_mode_active = False
        self._status_badges: dict[str, str] = {}
        self._trigger_tasks: list[asyncio.Task] = []
        self._base_triggers = BaseUITriggers(self)
        self.usage = BaseUIUsage()
        self._message_queue: MessageQueue = MessageQueue()
        self._active_run_context: Any = None
        self._process_messages_task: asyncio.Task | None = None
        self._last_result_data: str | None = None
        # Status-bar timers; running tools are keyed by tool_call_id.
        self._working_started_at: float | None = None
        self._running_tools: dict[str, RunningTool] = {}

        self._cwd = os.getcwd()
        self._git_info = "Checking..."
        self._system_info_task: asyncio.Task | None = None

        self._snapshot_manager = None
        if enable_rewind and snapshot_dir and self._conversation_session_name:
            self._snapshot_manager = SnapshotManager(
                snapshot_dir=snapshot_dir,
                # Read at each operation, so rewind follows `/load` and `/save`.
                session_name=lambda: self._conversation_session_name,
                workdir=self._cwd,
                retention_seconds=parse_duration(CFG.LLM_SNAPSHOT_RETENTION),
            )

        self._pending_attachments: list["UserContent"] = _default_list(
            initial_attachments
        )

        self._tool_call_handler = ToolCallHandler(
            tool_policies=_default_list(tool_policies),
            argument_formatters=_default_list(argument_formatters),
            response_handlers=_default_list(response_handlers)
            + [default_response_handler],
        )
        self.confirmation = BaseUIConfirmationState()

        # Strong references so fire-and-forget tasks aren't GC'd mid-run.
        self._background_tasks: set[asyncio.Task] = set()
        # Subset that teardown drains instead of cancelling.
        self._hook_tasks: set[asyncio.Task] = set()

        self._base_commands = BaseUICommands(self)
        self._conversation = self.conversation = self._base_commands.conversation
        self.models = self._base_commands.models
        self._exec = self._base_commands.exec
        self._base_replay = BaseUIReplay(self)
        self._base_system_info = BaseUISystemInfo(self)

        if self._ui_config.is_yolo:
            self.yolo = self._ui_config.is_yolo

    @property
    def small_model(self) -> Any:
        """Get the current small model."""
        return self._small_model

    @small_model.setter
    def small_model(self, value: Any):
        """Set the small model."""
        self._small_model = value

    @property
    def multimodal_model(self) -> Any:
        """Get the current multimodal model."""
        return self._multimodal_model

    @multimodal_model.setter
    def multimodal_model(self, value: Any):
        """Set the multimodal model."""
        self._multimodal_model = value

    @property
    def conversation_session_name(self) -> str:
        """Get the conversation session name."""
        return self._conversation_session_name

    @conversation_session_name.setter
    def conversation_session_name(self, value: str):
        """Set the conversation session name."""
        self._conversation_session_name = value

    @property
    def triggers(self) -> list[Callable[[], AsyncIterable[Any]]]:
        return self._triggers

    @triggers.setter
    def triggers(self, value: list[Callable[[], AsyncIterable[Any]]]):
        self._triggers = value

    @property
    def last_output(self) -> str:
        if self._last_result_data is None:
            return ""
        return self._last_result_data

    @property
    def last_result_data(self) -> "str | None":
        """The raw last-turn result, or None before any turn has completed."""
        return self._last_result_data

    @last_result_data.setter
    def last_result_data(self, value: "str | None") -> None:
        self._last_result_data = value

    @property
    def assistant_name(self) -> str:
        """Get the assistant name."""
        return self._assistant_name

    @property
    def ui_config(self) -> UIConfig:
        """The command names and UI behavior flags this UI was built with."""
        return self._ui_config

    @property
    def initial_message(self) -> Any:
        """Get the initial message."""
        return self._initial_message

    exit_commands = _command_alias_property("exit", "exit")
    info_commands = _command_alias_property("info", "info/help")
    save_commands = _command_alias_property("save", "save")
    load_commands = _command_alias_property("load", "load")
    attach_commands = _command_alias_property("attach", "attach")
    redirect_output_commands = _command_alias_property(
        "redirect_output", "redirect output"
    )
    yolo_toggle_commands = _command_alias_property("yolo_toggle", "yolo toggle")
    set_model_commands = _command_alias_property("set_model", "set model")
    set_commands = _command_alias_property("set", "set")
    exec_commands = _command_alias_property("exec", "exec")

    @property
    def custom_commands(self) -> list[AnyCustomCommand]:
        """Get the list of custom commands."""
        return self._custom_commands

    @custom_commands.setter
    def custom_commands(self, value) -> None:
        self._custom_commands = value

    summarize_commands = _command_alias_property("summarize", "summarize")

    @property
    def history_manager(self) -> AnyHistoryManager:
        """Public read accessor for the conversation history manager."""
        return self._history_manager

    @property
    def snapshot_manager(self) -> "SnapshotManager | None":
        """Public read accessor for the snapshot manager (may be None)."""
        return self._snapshot_manager

    @property
    def background_tasks(self) -> "set[asyncio.Task]":
        """Public read accessor for the background-task set."""
        return self._background_tasks

    @property
    def hook_tasks(self) -> "set[asyncio.Task]":
        """The fire-and-forget hook tasks still running (`execute_hook`)."""
        return self._hook_tasks

    async def drain_hook_tasks(self, timeout: float) -> None:
        """Give running hook tasks *timeout* seconds to finish, then cancel.

        A Stop hook fired on exit is still running at teardown.
        """
        pending = [task for task in self._hook_tasks if not task.done()]
        if not pending:
            return
        _, unfinished = await asyncio.wait(pending, timeout=timeout)
        for task in unfinished:
            logger.warning("A hook was still running at exit; cancelling it.")
            task.cancel()

    @property
    def pending_attachments(self) -> list[Any]:
        """Public read accessor for attachments queued for the next turn."""
        return self._pending_attachments

    @property
    def plan_mode_active(self) -> bool:
        """Whether plan mode is currently active."""
        return self._plan_mode_active

    @plan_mode_active.setter
    def plan_mode_active(self, value: bool):
        self._plan_mode_active = value

    @property
    def message_queue(self) -> Any:
        """Public read accessor for the pending-message queue."""
        return self._message_queue

    btw_commands = _command_alias_property("btw", "`/btw` (side-question)")
    plan_commands = _command_alias_property("plan", "plan-mode-toggle")
    rewind_commands = _command_alias_property("rewind", "rewind/snapshot")
    copy_commands = _command_alias_property("copy", "copy-transcript")

    @property
    def running_llm_task(self) -> "asyncio.Task | None":
        """The task currently executing a turn from the message queue, if any."""
        return self._running_llm_task

    @running_llm_task.setter
    def running_llm_task(self, value: "asyncio.Task | None"):
        self._running_llm_task = value

    @property
    def cwd(self) -> str:
        """The working directory shown in the system-info status line."""
        return self._cwd

    @cwd.setter
    def cwd(self, value: str):
        self._cwd = value

    @property
    def git_info(self) -> str:
        """The git branch/status shown in the system-info status line."""
        return self._git_info

    @git_info.setter
    def git_info(self, value: str):
        self._git_info = value

    @property
    def is_thinking(self) -> bool:
        """Whether the assistant is currently producing a response."""
        return self._uidefaults_is_thinking

    @is_thinking.setter
    def is_thinking(self, value: bool) -> None:
        was_thinking = self._uidefaults_is_thinking
        self._uidefaults_is_thinking = value
        if value and not was_thinking:
            self._working_started_at = time.monotonic()
        elif not value:
            self._working_started_at = None

    @property
    def working_started_at(self) -> float | None:
        """`time.monotonic()` when the current working period began."""
        return self._working_started_at

    @property
    def running_tool(self) -> "RunningTool | None":
        """The most recently started tool call still executing, or None."""
        if not self._running_tools:
            return None
        return max(self._running_tools.values(), key=lambda item: item.started_at)

    def start_tool_call(self, tool_name: str, tool_call_id: str) -> None:
        """Record the start of `tool_name`'s execution for the status bar."""
        self._running_tools[tool_call_id] = RunningTool(
            tool_name, tool_call_id, time.monotonic()
        )

    def end_tool_call(self, tool_call_id: str | None = None) -> None:
        """Forget the finished call `tool_call_id`; ``None`` clears all."""
        if tool_call_id is None:
            self._running_tools.clear()
            return
        self._running_tools.pop(tool_call_id, None)

    @property
    def markdown_theme(self) -> Any:
        """Rich theme used to render the assistant's markdown."""
        return self._markdown_theme

    @property
    def process_messages_task(self) -> "asyncio.Task | None":
        """The task running `process_messages_loop`, if started."""
        return self._process_messages_task

    @process_messages_task.setter
    def process_messages_task(self, value: "asyncio.Task | None"):
        self._process_messages_task = value

    @property
    def trigger_tasks(self) -> "list[asyncio.Task]":
        """Tasks running each configured trigger's loop."""
        return self._trigger_tasks

    @trigger_tasks.setter
    def trigger_tasks(self, value: "list[asyncio.Task]"):
        self._trigger_tasks = value

    @property
    def system_info_task(self) -> "asyncio.Task | None":
        """The task running `update_system_info_loop`, if started."""
        return self._system_info_task

    @system_info_task.setter
    def system_info_task(self, value: "asyncio.Task | None"):
        self._system_info_task = value

    # BaseUICommands delegators (part of the `AnyUI` contract)

    @property
    def commands(self) -> BaseUICommands:
        """The slash-command dispatcher; extend via `commands.command_table()`."""
        return self._base_commands

    def classify_input(self, text: str) -> str:
        return self._base_commands.classify_input(text)

    def schedule_command(self, text: str, *, guarded: bool = True) -> None:
        self._base_commands.schedule_command(text, guarded=guarded)

    async def dispatch_command(self, text: str, *, guarded: bool = True) -> None:
        await self._base_commands.dispatch_command(text, guarded=guarded)

    def get_help_panel(
        self, art: str = "", header: str = "", max_commands: int | None = None
    ) -> Any:
        return self._base_commands.get_help_panel(art, header, max_commands)

    def print_help(self) -> None:
        self._base_commands.print_help()

    def get_help_text(self, width: int | None = None) -> str:
        return self._base_commands.get_help_text(width)

    # conversation commands
    def handle_exit_command(self, text: str) -> bool:
        return self._conversation.handle_exit_command(text)

    def handle_info_command(self, text: str) -> bool:
        return self._conversation.handle_info_command(text)

    def handle_save_command(self, text: str) -> bool:
        return self._conversation.handle_save_command(text)

    def handle_load_command(self, text: str) -> bool:
        return self._conversation.handle_load_command(text)

    def handle_rewind_command(self, text: str) -> bool:
        return self._conversation.handle_rewind_command(text)

    def last_ai_response(self) -> str:
        return self._conversation.last_ai_response()

    def write_text_to_file(self, path: str, content: str) -> None:
        self._conversation.write_text_to_file(path, content)

    def copy_to_clipboard_and_report(self, content: str, success_message: str) -> None:
        self._conversation.copy_to_clipboard_and_report(content, success_message)

    def handle_redirect_command(self, text: str) -> bool:
        return self._conversation.handle_redirect_command(text)

    def handle_copy_command(self, text: str) -> bool:
        return self._conversation.handle_copy_command(text)

    def handle_attach_command(self, text: str) -> bool:
        return self._conversation.handle_attach_command(text)

    def submit_attachment(self, path: str) -> None:
        self._conversation.submit_attachment(path)

    def apply_persona_for_session(self, name: str) -> None:
        self._conversation.apply_persona_for_session(name)

    # model commands
    def toggle_yolo(self) -> None:
        self.models.toggle_yolo()

    def handle_toggle_yolo(self, text: str) -> bool:
        return self.models.handle_toggle_yolo(text)

    def toggle_plan(self) -> None:
        self.models.toggle_plan()

    def handle_toggle_plan(self, text: str) -> bool:
        return self.models.handle_toggle_plan(text)

    def current_cycle_mode(self) -> str:
        return self.models.current_cycle_mode()

    def cycle_mode(self) -> None:
        self.models.cycle_mode()

    def handle_set_model_command(self, text: str) -> bool:
        return self.models.handle_set_model_command(text)

    def handle_set_command(self, text: str):
        return self.models.handle_set_command(text)

    # exec commands
    def handle_exec_command(self, text: str) -> bool:
        return self._exec.handle_exec_command(text)

    async def run_shell_command(self, cmd: str) -> None:
        await self._base_commands.run_shell_command(cmd)

    def handle_btw_command(self, text: str) -> bool:
        return self._exec.handle_btw_command(text)

    async def stream_btw_response(self, llm_task: LLMTask, question: str) -> None:
        await self._base_commands.stream_btw_response(llm_task, question)

    def handle_custom_command(self, text: str) -> bool:
        return self._exec.handle_custom_command(text)

    # BaseUIReplay delegators

    def replay_history(self, messages: list) -> None:
        self._base_replay.replay_history(messages)

    # BaseUISystemInfo delegators

    async def update_system_info(self) -> None:
        await self._base_system_info.update_system_info()

    def get_cwd_display(self) -> str:
        return self._base_system_info.get_cwd_display()

    async def get_git_info(self) -> tuple[str, str]:
        return await self._base_system_info.get_git_info()

    async def update_system_info_loop(self) -> None:
        await self._base_system_info.update_system_info_loop()

    @property
    def ctx(self) -> AnyContext:
        """Get the context for this UI."""
        return self._ctx

    def accumulate_usage(
        self, usage: "RunUsage", context_usage: "RequestUsage | None" = None
    ) -> None:
        """Fold one run's usage into session totals and refresh context size."""
        self.usage.accumulate(usage, context_usage)

    @property
    def tool_call_handler(self) -> Any:
        """Get the tool call handler for this UI."""
        return self._tool_call_handler

    @property
    def active_run_context(self) -> Any:
        """The live pydantic-ai `RunContext` of the streaming turn, or None.

        `submit_user_message` uses it to steer a message into the live turn.
        """
        return self._active_run_context

    @active_run_context.setter
    def active_run_context(self, ctx: Any) -> None:
        self._active_run_context = ctx

    def take_pending_attachments(self) -> "list[UserContent]":
        """Return and clear this UI's pending attachments."""
        attachments = list(self._pending_attachments)
        self._pending_attachments.clear()
        return attachments

    @property
    def is_turn_running(self) -> bool:
        """Whether this UI, or its `MultiUI` parent, is running a turn."""
        running = self._running_llm_task
        if running is not None and not running.done():
            return True
        parent = self.multi_ui_parent
        return parent is not None and parent.is_turn_running

    def cancel_current_turn(self, reason: str) -> None:
        """Release pending confirmations, cancel the turn and fire `Stop`.

        A `MultiUI` child delegates to its parent, which runs the turn.
        """
        running = self._running_llm_task
        if running is None or running.done():
            parent = self.multi_ui_parent
            if parent is not None:
                parent.cancel_current_turn(reason)
            else:
                self.cancel_pending_confirmations()
            return
        self.cancel_pending_confirmations()
        running.cancel()
        self.execute_hook(
            HookEvent.STOP,
            {"reason": reason, "session": self.conversation_session_name},
        )

    def execute_hook(
        self,
        event: HookEvent,
        event_data: Any,
        manager: HookManager | None = None,
        **kwargs,
    ) -> None:
        """Fire hooks from a sync or async context, through *manager*
        (default: the one this UI's turns run with)."""
        effective = manager or get_turn_hook_manager(self.llm_task)
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(
                effective.execute_hooks(event, event_data, **kwargs)
            )
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
            self._hook_tasks.add(task)
            task.add_done_callback(self._hook_tasks.discard)

        except RuntimeError:
            # Sync context: Runner restores the thread's previous loop state on
            # close, so no closed loop is left installed as the default.
            with asyncio.Runner() as runner:
                runner.run(effective.execute_hooks(event, event_data, **kwargs))

    async def execute_hook_blocking(
        self, event: HookEvent, event_data: Any, **kwargs
    ) -> list:
        """Run hooks and await their results, for a blocking decision."""
        manager = get_turn_hook_manager(self.llm_task)
        return await manager.execute_hooks(event, event_data, **kwargs)

    @property
    def yolo(self) -> bool | frozenset:
        if self._yolo_xcom_key not in self._ctx.xcom:
            return False
        return self._ctx.xcom[self._yolo_xcom_key].get(False)

    @yolo.setter
    def yolo(self, value: bool | frozenset):
        if self._yolo_xcom_key not in self._ctx.xcom:
            self._ctx.xcom[self._yolo_xcom_key] = Xcom()
        self._ctx.xcom[self._yolo_xcom_key].set(value)

    # REQUIRED METHODS - Must be implemented by subclasses

    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ):
        """[REQUIRED] Render output to the user.

        Args:
            *values: Objects to display (converted to string via str())
            sep: Separator between values (default: space)
            end: String appended after all values (default: newline)
            file: Ignored (for print() compatibility)
            flush: Ignored (for print() compatibility)
            kind: Output kind — "text", "progress", "tool_call", "usage", or
                  "thinking". Use this to apply visual distinction (e.g. faint
                  styling for non-"text" kinds in terminal, CSS classes in web).

        Example:
            def append_to_output(self, *values, sep=" ", end="\\n", kind="text", **kwargs):
                text = sep.join(str(v) for v in values) + end
                if kind != "text":
                    text = stylize_muted(text)
                print(text, end="")
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement append_to_output()"
        )

    async def ask_user(
        self,
        prompt: str,
        output_to_parent: str = "",
        agent_id: str | None = None,
    ) -> str:
        """[REQUIRED] Show *prompt* (if any) and block until the user answers.

        Args:
            prompt: Prompt to display; may be empty.
            output_to_parent: Written to the parent UI's output before the
                   prompt (BufferedUI relays sub-agent approvals this way).
            agent_id: The originating sub-agent's id, so the answer routes
                   back to that agent's view.

        Returns:
            The user's input as a string.

        Example:
            async def ask_user(self, prompt, output_to_parent="", agent_id=None) -> str:
                if prompt:
                    print(prompt, end="", flush=True)
                return await asyncio.to_thread(input)
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement ask_user()"
        )

    async def ask_user_choice(
        self, spec: "ChoiceSpec", agent_id: str | None = None
    ) -> str:
        """[OPTIONAL] Ask a multiple-choice question.

        The default renders numbered text through `ask_user`. Returns the
        chosen label(s), comma-joined for multi-select, or free-form text.
        """
        return await self.ask_user(format_choice_spec(spec), agent_id=agent_id)

    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
        """Execute an interactive shell command, handing it the real terminal.

        Used by the diff and argument editors on an "edit" answer. The default
        raises `NotImplementedError`.

        Args:
            cmd: Command to execute (string or list of arguments)
            shell: If True, run through shell (supports pipes, etc.)

        Returns:
            Command result (implementation-dependent)

        Example:
            async def run_interactive_command(self, cmd, shell=False):
                proc = await asyncio.create_subprocess_shell(cmd, shell=shell)
                await proc.wait()
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement run_interactive_command()"
        )

    async def run_async(self) -> str:
        """[REQUIRED] Run the UI event loop.

        It should:
        1. Start the message processing loop (via process_messages_loop)
        2. Submit initial message if provided (_initial_message)
        3. Start any trigger loops if configured
        4. Run until the UI is closed or cancelled
        5. Return the last output

        Returns:
            The last output from the conversation (or empty string).

        Example:
            async def run_async(self):
                self._process_messages_task = asyncio.create_task(
                    self.process_messages_loop()
                )
                if self._initial_message:
                    self.submit_user_message(self.llm_task, self._initial_message)
                try:
                    while self._running:
                        await asyncio.sleep(0.1)
                except asyncio.CancelledError:
                    pass
                finally:
                    self._process_messages_task.cancel()
                return self.last_output
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement run_async()"
        )

    # OPTIONAL METHODS - Can be overridden by subclasses

    def stream_to_parent(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ):
        """[OPTIONAL] Stream output immediately to the parent UI.

        Defaults to `append_to_output`; child UIs forward instead of buffering.

        Args:
            *values: Objects to stream
            sep: Separator between values
            end: String appended after all values
            file: Ignored
            flush: Ignored
            kind: Output kind — "text", "progress", "tool_call", "usage", or "thinking".
        """
        self.append_to_output(
            *values, sep=sep, end=end, file=file, flush=flush, kind=kind
        )

    def on_exit(self):
        """[OPTIONAL] Clean up when the user exits. Default: no-op."""
        pass

    @property
    def effective_message_queue(self) -> MessageQueue:
        """The queue submissions land on: the `MultiUI` parent's, else own."""
        parent = self.multi_ui_parent
        if parent is not None:
            return parent.message_queue
        return self._message_queue

    @property
    def queued_message_count(self) -> int:
        """Messages waiting for the current turn to finish."""
        return self.effective_message_queue.qsize()

    def edit_queued_message(self, entry: QueuedMessage, new_text: str) -> bool:
        """Replace a still-queued message's text and redraw its echoes.

        Returns ``False`` when its turn already started.
        """
        queue = self.effective_message_queue
        if not queue.contains(entry):
            return False
        entry.text = new_text.strip()
        _broadcast_echo(self, lambda ui: ui.redraw_echo(entry))
        return True

    def delete_queued_message(self, entry: QueuedMessage) -> None:
        """Drop a still-queued message and remove its echo from every UI.

        No-op when its turn already started.
        """
        queue = self.effective_message_queue
        if not queue.contains(entry):
            return
        queue.remove(entry)
        _broadcast_echo(self, lambda ui: ui.remove_echo(entry))

    def redraw_echo(self, entry: QueuedMessage) -> str | None:
        """Rewrite `entry`'s echoed line; returns it, or None (no buffer)."""
        return None

    def remove_echo(self, entry: QueuedMessage) -> None:
        """Remove `entry`'s echoed line. No-op here (no buffer)."""

    def append_markdown(self, markdown_text: str) -> None:
        """Render `markdown_text` at the current output width and append it."""
        self.append_to_output(
            render_markdown(
                markdown_text,
                width=self.output_field_width,
                theme=self._markdown_theme,
            )
        )

    @property
    def output_field_width(self) -> int | None:
        """Output width, or None; subclasses override `_get_output_field_width`."""
        return self._get_output_field_width()

    def _get_output_field_width(self) -> int | None:
        """[OPTIONAL] Width in characters for wrapping, or None for none."""
        return None

    async def process_messages_loop(self):
        """Process jobs from queue, ensuring only one job runs at a time."""
        while True:
            try:
                entry = await self._message_queue.get()
                await self._settle_previous_job()
                await self._run_queued_job(entry)
                self._message_queue.task_done()
            except asyncio.CancelledError:
                break
            except RuntimeError as e:
                # Event loop closed during shutdown.
                logger.error(f"RuntimeError in message queue loop: {e}")
                break
            except Exception as e:
                logger.error(f"Error in message queue loop: {e}")
                try:
                    await asyncio.sleep(CFG.LLM_UI_STATUS_INTERVAL / 1000)
                except RuntimeError:
                    break

    async def _settle_previous_job(self) -> None:
        """Await a still-running previous job, swallowing its outcome."""
        if self._running_llm_task is None or self._running_llm_task.done():
            return
        try:
            await self._running_llm_task
        except (KeyboardInterrupt, SystemExit):
            # Process-level interrupts are not a job outcome.
            raise
        except BaseException:
            # A cancel aimed at this loop must still propagate.
            current = asyncio.current_task()
            if current is not None and current.cancelling() > 0:
                raise

    async def _run_queued_job(self, entry: "QueuedMessage") -> None:
        """Run one queued job to completion, absorbing its failure."""
        current_task = asyncio.create_task(entry.run())
        self._running_llm_task = current_task
        try:
            await current_task
        except asyncio.CancelledError:
            try:
                await current_task
            except asyncio.CancelledError:
                pass
        except Exception as e:
            logger.error(f"Error executing job: {e}")
        finally:
            self._running_llm_task = None

    def track_echo_span(self, entry: QueuedMessage, echo: str) -> None:
        """Record the output-buffer span of `echo` on `entry`. No-op here."""

    def record_submitted_message(self, text: str) -> None:
        """Record a submitted user message for cross-session recall. No-op here."""

    def submit_user_message(
        self,
        llm_task: AnyTask,
        user_message: str,
        source: InputSource = KEYBOARD_INPUT,
    ) -> None:
        """Queue *user_message* for `llm_task`; prefer `submit_message` for
        this UI's own current task."""
        parent_multi_ui = self.multi_ui_parent
        if parent_multi_ui is not None:
            # The parent broadcasts and records the message once.
            return parent_multi_ui.submit_user_message(llm_task, user_message, source)
        self.record_submitted_message(user_message)
        # Mid-turn the message only joins the queue; the marker says so.
        marker = "⏳" if self.is_thinking else "💬"
        submit_user_message_via_queue(
            append_to_output=self.append_to_output,
            active_run_context=self.active_run_context,
            stream_ai_response=lambda task, text, attachments: self.stream_ai_response(
                cast("LLMTask", task), text, attachments
            ),
            queue=self._message_queue,
            attachment_sources=[self],
            echo_targets=[self],
            llm_task=llm_task,
            user_message=user_message,
            marker=marker,
            append_markdown=self.append_markdown,
            source=source,
        )

    def submit_message(self, user_message: str, source: InputSource = None) -> None:
        """Steer *user_message* into the live turn, or queue it for the next."""
        self.submit_user_message(self.llm_task, user_message, source)

    def set_status_badge(self, key: str, text: str | None) -> None:
        if text is None:
            self._status_badges.pop(key, None)
        else:
            self._status_badges[key] = text
        self.invalidate_ui()

    @property
    def status_badges(self) -> tuple[str, ...]:
        """The badges `set_status_badge` shows, in the order first set."""
        return tuple(self._status_badges.values())

    @property
    def is_waiting_for_answer(self) -> bool:
        """Whether a tool approval or a question is waiting. ``False`` here."""
        return False

    @property
    def pending_answer_since(self) -> float | None:
        """`time.monotonic()` when the pending prompt appeared, or None."""
        return None

    def is_prompt_answered_since(self, asked_at: float) -> bool:
        """Whether the first prompt asked at or after *asked_at* (monotonic)
        has been answered or cancelled. ``False`` when unknown."""
        return False

    @property
    def is_waiting_for_choice(self) -> bool:
        """Whether the pending prompt is a multiple-choice question rather
        than a tool approval."""
        return False

    def submit_answer(self, text: str) -> None:
        """Answer the pending prompt with *text*, else submit it as a message."""
        self.submit_message(text)

    def insert_input_text(self, text: str) -> None:
        """Insert *text* at the input cursor; without an input box, submit it."""
        self.submit_message(text)

    async def stream_ai_response(
        self,
        llm_task: LLMTask,
        user_message: str,
        attachments: "list[UserContent] | None" = None,
    ):
        attachments = list(attachments or [])
        # A cancelled turn can leave a stale running-tool timer behind.
        self.end_tool_call()
        self.is_thinking = True
        self.invalidate_ui()
        try:
            timestamp = datetime.now().strftime("%H:%M")
            await take_pre_turn_snapshot(
                self._snapshot_manager,
                self._history_manager,
                self._conversation_session_name,
                user_message,
                timestamp,
            )
            self.append_to_output(f"\n🤖 {timestamp} >>\n")
            session = self._create_session_for_llm_task(user_message, attachments)

            self.append_to_output(stylize_muted("\n  🔢 Streaming response..."))

            set_current_agent_mode(
                AgentMode.PLAN if self._plan_mode_active else AgentMode.BUILD
            )

            llm_task.set_ui(self)
            llm_task.tool_confirmation = cast(Any, self.confirm_tool_execution)
            result_data = await llm_task.async_run(session)

            # Tools like EnterPlanMode set the ContextVar, visible in this Task.
            self._plan_mode_active = get_current_agent_mode() == AgentMode.PLAN

            if isinstance(result_data, str):
                self._last_result_data = result_data
                self.append_to_output("\n")
                self.append_markdown(result_data)
            self._conversation.schedule_auto_name(user_message)

        except asyncio.CancelledError:
            self.append_to_output("\n[Cancelled]\n")
            raise
        except Exception as e:
            self.append_to_output(f"\n[Error: {exception_summary(e)}]\n")
        finally:
            self.is_thinking = False
            self._running_llm_task = None
            await self.update_system_info()
            self.invalidate_ui()

    def _create_session_for_llm_task(
        self,
        user_message: str,
        attachments: list["UserContent"],
    ) -> AnySession:
        session_input = {
            "message": user_message,
            "session": self._conversation_session_name,
            "yolo": self.yolo,
            "attachments": attachments,
            "model": self.model,
        }
        shared_ctx = SharedContext(
            input=session_input,
            print_fn=self.append_to_output,
            is_web_mode=True,
        )
        return Session(shared_ctx)

    async def confirm_tool_execution(
        self,
        call: "ToolCallPart",
    ) -> "ToolApproved | ToolDenied | None":
        # The ambient UI (e.g. a sub-agent's BufferedUI), not the captured main UI.
        ui = create_combined_ui(get_current_ui() or self, fallback=self)
        return await self._tool_call_handler.handle(ui, call)

    async def trigger_loop(
        self, trigger_factory: Callable[[], AsyncIterable[Any]]
    ) -> None:
        """Submit a user turn for every item *trigger_factory* yields."""
        await self._base_triggers.trigger_loop(trigger_factory)
