"""Slash-command dispatch for `BaseUI`.

Routes recognized commands to handlers and fires PreCommand/PostCommand
hooks. The concrete `_handle_*` handlers live in sibling mixins that this
class composes (so the dispatch table and the handlers share one `self`):

  conversation_commands_mixin.py - exit/info/save/load/rewind/redirect/copy/attach
  model_commands_mixin.py        - yolo/plan toggles + model switching
  exec_commands_mixin.py         - shell exec, /btw side questions, custom cmds

Each `_handle_*` returns `True` if the input was consumed (a command matched),
`False` otherwise.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from zrb.llm.custom_command.resolver import resolve_custom_command
from zrb.llm.hook.types import HookEvent
from zrb.llm.ui.base.conversation_commands_mixin import ConversationCommandsMixin
from zrb.llm.ui.base.exec_commands_mixin import ExecCommandsMixin
from zrb.llm.ui.base.model_commands_mixin import ModelCommandsMixin
from zrb.util.cli.style import stylize_muted

if TYPE_CHECKING:
    from typing import Any, Callable

    from pydantic_ai.messages import UserContent
    from pydantic_ai.models import Model
    from rich.theme import Theme

    from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
    from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
    from zrb.llm.snapshot.manager import SnapshotManager
    from zrb.llm.task.llm_task import LLMTask
    from zrb.task.any_task import AnyTask

logger = logging.getLogger(__name__)


class CommandsMixin(ConversationCommandsMixin, ModelCommandsMixin, ExecCommandsMixin):
    """Slash-command dispatch for BaseUI (handlers live in composed mixins)."""

    # Host-class contract: state and methods owned by `BaseUI` (and concrete
    # subclasses). Declared here so static type checkers can verify accesses;
    # the block does not run at runtime.
    if TYPE_CHECKING:
        # Command lists (set in `BaseUI.__init__`)
        _attach_commands: list[str]
        _btw_commands: list[str]
        _copy_commands: list[str]
        _plan_commands: list[str]
        _plan_mode_active: bool
        _custom_commands: list["AnyCustomCommand"]
        _exec_commands: list[str]
        _exit_commands: list[str]
        _info_commands: list[str]
        _load_commands: list[str]
        _redirect_output_commands: list[str]
        _rewind_commands: list[str]
        _save_commands: list[str]
        _set_model_commands: list[str]
        _summarize_commands: list[str]
        _yolo_toggle_commands: list[str]
        # Misc state
        _background_tasks: set[asyncio.Task]
        _conversation_session_name: str
        _history_manager: "AnyHistoryManager"
        _is_thinking: bool
        _llm_task: "LLMTask"
        _markdown_theme: "Theme | None"
        _message_queue: asyncio.Queue
        _model: "Model | str | None"
        _small_model: "Model | str | None"
        _multimodal_model: "Model | str | None"
        _pending_attachments: list["UserContent"]
        _running_llm_task: asyncio.Task | None
        _snapshot_manager: "SnapshotManager | None"

        # Methods/properties provided by the host class (subclass of BaseUI).
        last_output: Any

        def append_to_output(self, *values: Any, **kwargs: Any) -> None: ...

        def execute_hook(self, event: Any, event_data: Any, **kwargs) -> None: ...

        async def execute_hook_blocking(
            self, event: Any, event_data: Any, **kwargs
        ) -> list: ...

        def invalidate_ui(self) -> None: ...

        def on_exit(self) -> None: ...

        def _submit_user_message(
            self, llm_task: "AnyTask", user_message: str
        ) -> None: ...

        def _replay_history(self, messages: list) -> None: ...

        async def _update_system_info(self) -> None: ...

        def _get_output_field_width(self) -> int | None: ...

        @property
        def yolo(self) -> bool | frozenset: ...

        @yolo.setter
        def yolo(self, value: bool | frozenset) -> None: ...

    # --- command dispatch (with hooks) ------------------------------------

    def _command_table(self) -> "list[tuple[Callable, list[str], bool, bool]]":
        """Single source of truth for command routing.

        Ordered ``(handler, tokens, prefix, run_while_thinking)`` tuples shared
        by :meth:`classify_input` (which matches ``tokens`` via :func:`_matches`)
        and :meth:`_run_command_chain` (which calls ``handler``). Because both
        derive from this one table, routing and execution cannot drift on which
        tokens map to which command. Custom commands are matched separately via
        ``resolve_custom_command`` (they have no fixed token list).

        ``prefix=True`` → the token may be followed by ``" <args>"``;
        ``prefix=False`` → exact-match toggle.
        """
        return [
            (self._handle_btw_command, self._btw_commands, True, True),
            (self._handle_toggle_plan, self._plan_commands, True, True),
            # prefix=True: `/yolo` toggles, `/yolo Write,Edit` sets selective yolo.
            (self._handle_toggle_yolo, self._yolo_toggle_commands, True, True),
            (self._handle_exit_command, self._exit_commands, False, False),
            (self._handle_info_command, self._info_commands, False, False),
            (self._handle_save_command, self._save_commands, True, False),
            (self._handle_load_command, self._load_commands, True, False),
            (self._handle_rewind_command, self._rewind_commands, True, False),
            (
                self._handle_redirect_command,
                self._redirect_output_commands,
                True,
                False,
            ),
            (self._handle_attach_command, self._attach_commands, True, False),
            (self._handle_set_model_command, self._set_model_commands, True, False),
            (self._handle_exec_command, self._exec_commands, True, False),
            (self._handle_copy_command, self._copy_commands, True, False),
        ]

    def classify_input(self, text: str) -> str:
        """Classify Enter input for routing — by recognition, not by prefix.

        Returns one of:
            ``"thinking_command"`` — runs even while the LLM is thinking
                (``/btw``, YOLO toggle).
            ``"command"`` — any other recognized command (fires hooks).
            ``"message"`` — plain text forwarded to the LLM (no hooks).

        Routing never assumes a ``/`` prefix — command tokens are
        user-configurable (e.g. ``>`` for redirect). Driven by
        :meth:`_command_table` so it stays in lockstep with the handler chain.
        """
        stripped = text.strip()
        if not stripped:
            return "message"
        for _handler, tokens, prefix, run_while_thinking in self._command_table():
            if _matches(stripped, tokens, prefix):
                return "thinking_command" if run_while_thinking else "command"
        if resolve_custom_command(stripped, self._custom_commands) is not None:
            return "command"
        return "message"

    def schedule_command(self, text: str, *, guarded: bool = True) -> None:
        """Run the hook-wrapped command dispatch as a background task.

        Called from the (synchronous) Enter keybinding for any recognized
        command. Scheduling is required because the PreCommand hook is async and
        may block the command.

        Guarded dispatch is serialized: ``main`` ran commands synchronously, so
        each finished before the next began. A single in-flight guarded command
        is allowed; a second is rejected (rather than racing a prior `/save`,
        `/load`, or `/exit`). The flag is set synchronously — before the task is
        created — so the single-threaded event loop cannot slip a second command
        through the gap.

        ``guarded=False`` is used for run-while-thinking commands (`/btw`, YOLO
        toggle): like ``main``, they run independently and are neither blocked
        by an in-flight command nor block one.
        """
        if guarded:
            if getattr(self, "_command_in_flight", False):
                self.append_to_output(
                    stylize_muted(
                        "\n  ⏳ A command is already running — wait for it to "
                        "finish.\n"
                    )
                )
                return
            self._command_in_flight = True
        task = asyncio.create_task(self.dispatch_command(text, guarded=guarded))
        self._background_tasks.add(task)
        task.add_done_callback(self._on_command_done)

    def _on_command_done(self, task: "asyncio.Task") -> None:
        """Drop the task reference and surface any swallowed exception."""
        self._background_tasks.discard(task)
        try:
            exc = task.exception()
        except asyncio.CancelledError:
            return
        if exc is not None:
            logger.error("Command dispatch failed: %s", exc, exc_info=exc)

    async def dispatch_command(self, text: str, *, guarded: bool = True) -> None:
        """Fire PreCommand → run handlers → fire PostCommand.

        A PreCommand hook that blocks (HookResult.block / exit code 2 / deny)
        cancels the command. If no handler consumes the input (e.g. a command
        typed without its required argument), it is forwarded to the LLM.
        PostCommand fires only when a handler actually ran.
        """
        try:
            name, args = _split_command(text)
            event_data = {
                "command": name,
                "args": args,
                "session": self._conversation_session_name,
            }
            pre_results = await self.execute_hook_blocking(
                HookEvent.PRE_COMMAND,
                event_data,
                command_name=name,
                command_args=args,
            )
            if _command_blocked(pre_results):
                reason = _command_block_reason(pre_results) or "blocked by hook"
                self.append_to_output(
                    stylize_muted(f"\n  ⛔ {name} blocked: {reason}\n")
                )
                return

            # A PreCommand hook may rewrite the argument (e.g. swap the model in
            # `/model opus` → `sonnet`). The command token itself is preserved.
            new_args = _command_arg_override(pre_results)
            if new_args is not None:
                args = new_args
                text = f"{name} {new_args}".strip()
                event_data["args"] = args

            handled = self._run_command_chain(text)
            if handled:
                self.execute_hook(
                    HookEvent.POST_COMMAND,
                    {**event_data, "handled": True},
                    command_name=name,
                    command_args=args,
                    command_handled=True,
                )
            elif not self._is_thinking:
                # Recognized token but no handler consumed it — forward to LLM.
                self._submit_user_message(self._llm_task, text)
        finally:
            if guarded:
                self._command_in_flight = False

    def _run_command_chain(self, text: str) -> bool:
        """Run the command handlers in priority order (see :meth:`_command_table`).

        Returns ``True`` if a handler consumed the input. Run-while-thinking
        commands (`/btw`, YOLO toggle) run first; everything else is gated
        behind the thinking guard. Custom commands are tried last.
        """
        for handler, _tokens, _prefix, run_while_thinking in self._command_table():
            if not run_while_thinking and self._is_thinking:
                return False
            if handler(text):
                return True
        return self._handle_custom_command(text)

    # --- help text --------------------------------------------------------

    def _get_help_text(
        self, limit: int | None = None, max_length: int | None = None
    ) -> str:
        raw_lines: list[tuple[str, str]] = []

        def add_cmd_help(commands: list[str], description: str):
            if commands and len(commands) > 0:
                cmd = commands[0]
                raw_lines.append((cmd, description.replace("{cmd}", cmd)))

        add_cmd_help(self._exit_commands, "Exit the application")
        add_cmd_help(self._info_commands, "Show this help message")
        add_cmd_help(self._attach_commands, "Attach file (usage: {cmd} <path>)")
        add_cmd_help(self._save_commands, "Save conversation (usage: {cmd} <name>)")
        add_cmd_help(self._load_commands, "Load conversation (usage: {cmd} <name>)")
        if self._snapshot_manager is not None:
            add_cmd_help(
                self._rewind_commands,
                "List snapshots or restore one (usage: {cmd} [<n>|<sha>])",
            )
        add_cmd_help(
            self._redirect_output_commands,
            "Copy last output to clipboard (bare), or save to file (usage: {cmd} <file>)",
        )
        add_cmd_help(
            self._copy_commands,
            "Copy full transcript to clipboard (bare), or save to file (usage: {cmd} <file>)",
        )
        add_cmd_help(self._summarize_commands, "Summarize conversation history")
        add_cmd_help(self._yolo_toggle_commands, "Toggle YOLO mode")
        add_cmd_help(
            self._set_model_commands,
            "Set model (usage: {cmd} <model-name>, {cmd} small <model-name>, {cmd} multimodal <model-name>)",
        )
        add_cmd_help(
            self._exec_commands, "Execute shell command (usage: {cmd} <command>)"
        )
        add_cmd_help(
            self._btw_commands,
            "Ask a side question without saving to history (usage: {cmd} <question>)",
        )
        add_cmd_help(self._plan_commands, "Toggle PLAN mode (read-only) on/off")
        for custom_cmd in self._custom_commands:
            raw_lines.append((custom_cmd.command, custom_cmd.description))

        if not raw_lines:
            return ""

        max_cmd_len = max(len(cmd) for cmd, _ in raw_lines)
        help_lines = ["\nAvailable Commands:"]
        for i, (cmd, desc) in enumerate(raw_lines):
            if limit is not None and i >= limit:
                help_lines.append("  ... and more")
                break
            capped_desc = desc
            if max_length is not None and max_length > 4:
                capped_desc = (
                    desc if len(desc) <= max_length else f"{desc[:max_length - 4]} ..."
                )
            help_lines.append(f"  {cmd:<{max_cmd_len}} : {capped_desc}")

        shortcuts: list[tuple[str, str]] = [
            ("Ctrl+J", "Insert a newline (multi-line input)"),
            ("Ctrl+V / Alt+V", "Paste text or image from clipboard"),
            ("Tab / Shift+Tab", "Cycle mode: normal -> accept-edits -> plan"),
            ("Ctrl+K", "Toggle focus between input and output"),
            ("Esc", "Cancel running task or clear input"),
            ("Ctrl+Y", "Toggle YOLO mode"),
            ("Ctrl+C", "Copy selection, clear input, or exit"),
            ("↑ / ↓", "Navigate input history"),
        ]
        max_key_len = max(len(k) for k, _ in shortcuts)
        help_lines.append("\nKeyboard Shortcuts:")
        for key, desc in shortcuts:
            help_lines.append(f"  {key:<{max_key_len}} : {desc}")

        return "\n".join(help_lines) + "\n"


def _matches(text: str, tokens: list[str], prefix: bool) -> bool:
    """Pure command-token match: exact (case-insensitive), or ``"<token> "``.

    ``prefix=False`` matches only an exact token (toggles like ``/exit``);
    ``prefix=True`` also matches ``"<token> <args>"`` (argument commands).
    """
    t = text.strip().lower()
    for token in tokens:
        c = token.lower()
        if t == c:
            return True
        if prefix and t.startswith(c + " "):
            return True
    return False


def _split_command(text: str) -> tuple[str, str]:
    """Split ``cmd rest of line`` into ``("cmd", "rest of line")``."""
    stripped = text.strip()
    parts = stripped.split(None, 1)
    name = parts[0] if parts else stripped
    args = parts[1] if len(parts) > 1 else ""
    return name, args


def _command_blocked(results: list) -> bool:
    """True if any PreCommand hook result asked to block the command."""
    for r in results or []:
        if getattr(r, "blocked", False) or getattr(r, "exit_code", 0) == 2:
            return True
        if getattr(r, "decision", None) == "block":
            return True
        if getattr(r, "permission_decision", None) == "deny":
            return True
        if not getattr(r, "continue_execution", True):
            return True
    return False


def _command_arg_override(results: list) -> "str | None":
    """A `command_args` override returned by a PreCommand hook, if any.

    Lets a hook rewrite a command's argument on the fly — e.g. swap the model
    in ``/model opus`` to ``sonnet``. The value lands in each result's ``data``
    (the executor merges hook ``modifications`` / command-hook JSON there). The
    highest-priority hook that sets it wins; the command token is unchanged.
    """
    for r in results or []:
        value = (getattr(r, "data", None) or {}).get("command_args")
        if value is not None:
            return str(value)
    return None


def _command_block_reason(results: list) -> str | None:
    """First human-readable reason from a blocking PreCommand result."""
    for r in results or []:
        reason = getattr(r, "permission_decision_reason", None) or getattr(
            r, "reason", None
        )
        if reason:
            return reason
    return None
