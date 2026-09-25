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
from collections.abc import AsyncIterable, Callable, Sequence
from datetime import datetime
from typing import TYPE_CHECKING, Any, TextIO, cast

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.context.shared_context import SharedContext
from zrb.llm.agent_state import get_current_ui
from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.hook.manager import hook_manager
from zrb.llm.hook.types import HookEvent
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
from zrb.llm.ui.base.voice_state import BaseUIVoiceState
from zrb.llm.ui.multi_ui import MultiUI
from zrb.llm.ui.state_defaults import UIStateDefaultsMixin
from zrb.llm.ui.turn_snapshot import take_pre_turn_snapshot
from zrb.llm.ui.ui_config import UIConfig
from zrb.session.any_session import AnySession
from zrb.session.session import Session
from zrb.task.any_task import AnyTask
from zrb.util.cli.markdown import render_markdown
from zrb.util.cli.style import stylize_muted
from zrb.util.exception import exception_summary
from zrb.util.string.name import get_random_name
from zrb.xcom.xcom import Xcom

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


def _default_list(value: "Any") -> list:
    """`list(value or [])`, pulled out so `__init__`'s ~20 uses of the same
    fallback don't each count as their own branch against the complexity
    ratchet in zrb-test.sh."""
    return list(value or [])


def _command_alias_property(key: str, label: str) -> property:
    """A `list[str]` slash-command-alias property backed by
    `self._ui_config.{key}_commands`, in place of one hand-written
    getter/setter pair per command.
    """

    def getter(self: "BaseUI") -> list[str]:
        return getattr(self._ui_config, f"{key}_commands")

    def setter(self: "BaseUI", value: list[str]) -> None:
        setattr(self._ui_config, f"{key}_commands", value)

    getter.__doc__ = f"Get the list of {label} commands."
    return property(getter, setter)


class BaseUI(UIStateDefaultsMixin, AnyUI):
    """The chat session itself, minus how it draws.

    `BaseUI` runs the message loop, slash-command dispatch, tool approvals,
    history and model switching. A subclass supplies rendering and input for
    one backend — a terminal, Telegram, a websocket, a test double — and
    inherits the rest.

    Override to render and read:
        `append_to_output` and `ask_user` are the pair every backend writes.
        `run_interactive_command` hands a shell command a real terminal, and
        `run_async` drives the session's own loop. All four ship with working
        implementations, so a subclass overrides what its backend needs rather
        than being forced to answer for the rest.

    Prefer a smaller entry point when you can:
        `SimpleUI` covers a backend that owns its event loop and can block on
        input; `EventDrivenUI` covers one that delivers messages by callback.
        Both leave `run_async` alone, which is most of the work here. Reach
        for `BaseUI` when neither shape fits.

    Registering one:
        `create_ui_factory(MyUI)` adapts any of them to
        `llm_chat.ui_factories`; pass `ui_config=UIConfig(...)` to set the
        assistant's identity and slash-command aliases.

    The method set each entry point actually requires is executable rather
    than described here, in `test/llm/ui/test_extension_levels.py` — that file
    builds a minimal subclass per level the way the guide says to, so a
    changed requirement fails there instead of in a user's `zrb_init.py`.
    The full walkthrough is `docs/llm/llm-custom-ui.md`.

    Example:
        A backend that reads and writes one line at a time::

            class MyUI(BaseUI):
                def append_to_output(
                    self, *values, sep=" ", end="\\n", kind="text", **kwargs
                ):
                    print(sep.join(str(v) for v in values), end=end)

                async def ask_user(self, prompt: str) -> str:
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
        # Falls back to a per-instance key so ad-hoc UIs (SimpleUI and
        # friends, built without an LLMChatTask-provided key) never collide
        # on the same xcom slot.
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
        self.voice = BaseUIVoiceState()
        self._trigger_tasks: list[asyncio.Task] = []
        self._base_triggers = BaseUITriggers(self)
        self.usage = BaseUIUsage()
        self._message_queue: MessageQueue = MessageQueue()
        self._active_run_context: Any = None
        self._process_messages_task: asyncio.Task | None = None
        self._last_result_data: str | None = None

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

        # Strong references so fire-and-forget hook tasks aren't GC'd mid-run.
        self._background_tasks: set[asyncio.Task] = set()

        self._base_commands = BaseUICommands(self)
        self._conversation = self._base_commands.conversation
        self.models = self._base_commands.models
        self._exec = self._base_commands.exec
        self._base_replay = BaseUIReplay(self)
        self._base_system_info = BaseUISystemInfo(self)

        if self._ui_config.is_yolo:
            self.yolo = self._ui_config.is_yolo

    # =========================================================================
    # Construction-time / runtime state (own fields, read/written directly)
    # =========================================================================

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
    photo_commands = _command_alias_property("photo", "photo capture")
    redirect_output_commands = _command_alias_property(
        "redirect_output", "redirect output"
    )
    yolo_toggle_commands = _command_alias_property("yolo_toggle", "yolo toggle")
    set_model_commands = _command_alias_property("set_model", "set model")
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
    voice_commands = _command_alias_property("voice", "voice-dictation-toggle")
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

    # =========================================================================
    # BaseUICommands delegators (including its composed conversation/model/exec
    # collaborators — flattened here because the `AnyUI` contract and existing
    # callers reach these directly on `BaseUI`, not through `.commands`)
    # =========================================================================

    @property
    def commands(self) -> BaseUICommands:
        """The slash-command dispatcher, and through it the handler parts.

        A subclass reorders or extends the command set through
        `commands.command_table()`.
        """
        return self._base_commands

    def classify_input(self, text: str) -> str:
        return self._base_commands.classify_input(text)

    def schedule_command(self, text: str, *, guarded: bool = True) -> None:
        self._base_commands.schedule_command(text, guarded=guarded)

    async def dispatch_command(self, text: str, *, guarded: bool = True) -> None:
        await self._base_commands.dispatch_command(text, guarded=guarded)

    def handle_toggle_voice(self, text: str) -> bool:
        return self._base_commands.handle_toggle_voice(text)

    def get_help_panel(
        self, art: str = "", header: str = "", max_commands: int | None = None
    ) -> Any:
        return self._base_commands.get_help_panel(art, header, max_commands)

    def print_help(self) -> None:
        self._base_commands.print_help()

    def get_help_text(self, width: int | None = None) -> str:
        return self._base_commands.get_help_text(width)

    # --- conversation commands ---
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

    def handle_photo_command(self, text: str) -> bool:
        return self._conversation.handle_photo_command(text)

    async def submit_photo(self, device: str | None) -> None:
        await self._base_commands.submit_photo(device)

    def apply_persona_for_session(self, name: str) -> None:
        self._conversation.apply_persona_for_session(name)

    # --- model commands ---
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

    # --- exec commands ---
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

    # =========================================================================
    # BaseUIReplay delegators
    # =========================================================================

    def replay_history(self, messages: list) -> None:
        self._base_replay.replay_history(messages)

    # =========================================================================
    # BaseUISystemInfo delegators
    # =========================================================================

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
        """The live pydantic-ai `RunContext` for the turn currently streaming
        through this UI, or None between turns / while a turn is suspended
        (e.g. a pending tool approval). Set by `_execution_loop` for the
        duration of each `agent.run()` call; read by `submit_user_message`
        to steer a new message into the live turn instead of queuing it."""
        return self._active_run_context

    @active_run_context.setter
    def active_run_context(self, ctx: Any) -> None:
        self._active_run_context = ctx

    def take_pending_attachments(self) -> "list[UserContent]":
        """Return and clear this UI's pending attachments (public accessor)."""
        attachments = list(self._pending_attachments)
        self._pending_attachments.clear()
        return attachments

    def execute_hook(self, event: HookEvent, event_data: Any, **kwargs) -> None:
        """
        Safely execute hooks from either sync or async context.
        Maintains strong references to tasks to prevent garbage collection.
        """
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(
                hook_manager.execute_hooks(event, event_data, **kwargs)
            )
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

        except RuntimeError:
            # Sync context: Runner restores the thread's previous loop state on
            # close, so no closed loop is left installed as the default.
            with asyncio.Runner() as runner:
                runner.run(hook_manager.execute_hooks(event, event_data, **kwargs))

    async def execute_hook_blocking(
        self, event: HookEvent, event_data: Any, **kwargs
    ) -> list:
        """Run hooks and await their results.

        Unlike :meth:`execute_hook` (fire-and-forget), this awaits the manager
        so callers can inspect results for a blocking decision — used by the
        PreCommand path to cancel a command before it runs.
        """
        return await hook_manager.execute_hooks(event, event_data, **kwargs)

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

    # =========================================================================
    # REQUIRED METHODS - Must be implemented by subclasses
    # =========================================================================

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

        This method must be implemented by all UI subclasses to display
        AI responses, system messages, and other output to the user.

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
        """[REQUIRED] Block and wait for user input.

        This method must be implemented by all UI subclasses to receive
        user input. It should display the prompt (if provided) and block
        until the user provides input.

        Args:
            prompt: Optional prompt to display before waiting for input.
                   May be empty string if no prompt is needed.
            output_to_parent: When set, written to the parent UI's output
                   before the prompt is rendered.  Used by BufferedUI to
                   relay approval messages from sub-agents to the main
                   transcript.
            agent_id: The originating sub-agent's id, propagated by
                   BufferedUI so the confirmation queue can route an answer
                   back to whichever agent's live view the user is looking
                   at (see `UIConfirmation._resolve_for_agent`).

        Returns:
            The user's input as a string.

        Example:
            async def ask_user(self, prompt: str) -> str:
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
        """[OPTIONAL] Ask a structured multiple-choice question.

        Default implementation formats the spec as numbered text and delegates
        to `ask_user`, so any UI that only implements `ask_user` keeps working
        (the user types a number or free text). Terminal UIs override this to
        render an arrow-key-selectable widget.

        Returns the chosen option label(s) — comma-joined for multi-select — or
        the user's free-form text verbatim.
        """
        return await self.ask_user(format_choice_spec(spec), agent_id=agent_id)

    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
        """[REQUIRED] Execute an interactive shell command.

        This method must be implemented by UI subclasses that support
        running shell commands from within the chat (e.g., via /exec command).
        For UIs that don't support this, raise NotImplementedError or return None.

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

        This method must be implemented by all UI subclasses. It should:
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

    # =========================================================================
    # OPTIONAL METHODS - Can be overridden by subclasses
    # =========================================================================

    def stream_to_parent(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ):
        """[OPTIONAL] Stream output immediately to parent UI.

        For main UIs, this is typically the same as append_to_output().
        For child UIs in a multiplexer setup, this streams to the parent UI
        instead of buffering locally.

        Override this method if your UI needs to distinguish between
        local output and output that should be immediately forwarded.

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
        """[OPTIONAL] Handle application exit.

        Called when the user requests to exit the application. Override
        this method to perform cleanup tasks (close connections, save state, etc.)

        Default implementation does nothing.
        """
        pass

    @property
    def effective_message_queue(self) -> MessageQueue:
        """The message queue submissions land on.

        A child UI in a MultiUI routes its submissions (and edits) to the
        parent's shared queue; a standalone UI uses its own.
        """
        parent = self.multi_ui_parent
        if parent is not None:
            return parent.message_queue
        return self._message_queue

    @property
    def queued_message_count(self) -> int:
        """Messages waiting for the current turn to finish."""
        return self.effective_message_queue.qsize()

    def edit_queued_message(self, entry: QueuedMessage, new_text: str) -> bool:
        """Replace a still-queued message's text in place.

        Returns ``True`` when the message was still queued (its turn had not
        started) and was edited; ``False`` when it already started and the edit
        was refused. The entry is shared across every child UI in a MultiUI, so
        editing from one child updates the message for all; the echo redraw is
        broadcast the same way `submit_user_message` broadcasts the original
        echo.
        """
        queue = self.effective_message_queue
        if not queue.contains(entry):
            return False
        entry.text = new_text.strip()
        targets: Sequence[AnyUI] = (
            self.multi_ui_parent.children if self.multi_ui_parent else [self]
        )
        for ui in targets:
            try:
                ui.redraw_echo(entry)
            except Exception as e:
                CFG.LOGGER.debug(f"Child UI echo redraw failed: {e}")
        return True

    def redraw_echo(self, entry: QueuedMessage) -> str | None:
        """Rewrite `entry`'s echoed line after an edit; the rewritten line or
        None when it couldn't be redrawn — `AnyUI`'s echo contract. The default
        TUI overrides this to splice into its output buffer; other UIs have no
        buffer, so the base no-op returns None."""
        return None

    def append_markdown(self, markdown_text: str) -> None:
        """Render `markdown_text` at the current output width and append it.

        The default TUI overrides this (in `UIOutput`) to remember the source so
        a terminal resize can re-wrap it; every other UI just renders once.
        """
        self.append_to_output(
            render_markdown(
                markdown_text,
                width=self.output_field_width,
                theme=self._markdown_theme,
            )
        )

    @property
    def output_field_width(self) -> int | None:
        """Public width accessor — delegates to the `_get_output_field_width()`
        override hook so callers (e.g. the diff formatter) read width through a
        public name. Concrete UIs with their own terminal-derived width (the
        default TUI via `UIOutput`) override this property directly, winning
        by MRO; custom `BaseUI` subclasses just override `_get_output_field_width`.
        """
        return self._get_output_field_width()

    def _get_output_field_width(self) -> int | None:
        """[OPTIONAL] Get the width for text output formatting.

        Override this method to provide a custom width for markdown
        rendering and text wrapping. Return None for no width constraint.

        Returns:
            Width in characters, or None for no constraint.
        """
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
        """Await a still-running previous job, swallowing its outcome.

        Awaited rather than polled, so there is no check-then-act race between
        `done()` and the next assignment.
        """
        if self._running_llm_task is None or self._running_llm_task.done():
            return
        try:
            await self._running_llm_task
        except (KeyboardInterrupt, SystemExit):
            # Process-level interrupts are not a job outcome.
            raise
        except BaseException:
            # A cancel aimed at THIS loop must still land, or the queue becomes
            # uncancellable while a previous job unwinds. `cancelling()` tells
            # the two apart (same guard as monitoring._handle_threshold_reached).
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
        """Record the output-buffer span of `echo` on `entry` (`AnyUI` hook).

        The default UI overrides this so an edit can rewrite the echoed line in
        place; other UIs have no buffer to splice into, so the default is a
        no-op and their edits skip the redraw.
        """

    def submit_user_message(self, llm_task: AnyTask, user_message: str) -> None:
        """Queue *user_message* for `llm_task`, mirroring
        `MultiUI.submit_user_message`. Prefer `submit_message` when the
        message is for this UI's own current task; this explicit form exists
        for callers (e.g. keybindings set up before a persona swap) holding a
        specific task reference that may differ from `self.llm_task` by then."""
        parent_multi_ui = self.multi_ui_parent
        if parent_multi_ui is not None:
            # The parent broadcasts to every child UI.
            parent_multi_ui.submit_user_message(llm_task, user_message)
            return
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
        )

    def submit_message(self, user_message: str) -> None:
        """Queue *user_message* for the agent, mirroring `MultiUI.submit_message`:
        steer into the live turn when one is in flight, otherwise
        enqueue it for the next turn. Uses the UI's own task — sub-agent
        continuation code calls this to hand the main agent a synthesized
        report without reaching into `_llm_task`."""
        self.submit_user_message(self.llm_task, user_message)

    async def stream_ai_response(
        self,
        llm_task: LLMTask,
        user_message: str,
        attachments: "list[UserContent] | None" = None,
    ):
        attachments = list(attachments or [])
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

            # Tools like EnterPlanMode set the ContextVar, visible here in the
            # same Task context.
            self._plan_mode_active = get_current_agent_mode() == AgentMode.PLAN

            if isinstance(result_data, str):
                self._last_result_data = result_data
                self.append_to_output("\n")
                self.append_markdown(result_data)

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
        ui = get_current_ui() or self
        if isinstance(ui, list):
            if len(ui) == 0:
                ui = self
            elif len(ui) == 1:
                ui = ui[0]
            else:
                ui = MultiUI(ui)
        return await self._tool_call_handler.handle(ui, call)

    async def trigger_loop(
        self, trigger_factory: Callable[[], AsyncIterable[Any]]
    ) -> None:
        """Submit a user turn for every item *trigger_factory* yields."""
        await self._base_triggers.trigger_loop(trigger_factory)
