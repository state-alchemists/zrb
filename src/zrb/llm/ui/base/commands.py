"""Slash-command dispatch for `BaseUI`.

Routes recognized commands to the handlers in `conversation_commands.py`,
`model_commands.py` and `exec_commands.py`, firing PreCommand/PostCommand
hooks. Each `handle_*` returns whether it consumed the input.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from zrb.llm.custom_command.resolver import get_custom_command_match
from zrb.llm.hook.types import HookEvent
from zrb.llm.ui.base.conversation_commands import BaseUIConversationCommands
from zrb.llm.ui.base.exec_commands import BaseUIExecCommands
from zrb.llm.ui.base.model_commands import BaseUIModelCommands
from zrb.util.cli.help_panel import HelpPanel, render_help_panel
from zrb.util.cli.style import stylize_muted
from zrb.util.cli.terminal import get_terminal_size

if TYPE_CHECKING:
    from typing import Callable

    from zrb.llm.ui.base.ui import BaseUI

logger = logging.getLogger(__name__)


class BaseUICommands:
    """Slash-command dispatch for BaseUI (handlers live in composed collaborators)."""

    def __init__(self, base_ui: "BaseUI") -> None:
        self._base_ui = base_ui
        self._conversation = BaseUIConversationCommands(base_ui)
        self._models = BaseUIModelCommands(base_ui)
        self._exec = BaseUIExecCommands(base_ui)
        self._command_in_flight = False

    @property
    def conversation(self) -> BaseUIConversationCommands:
        """Handlers for exit/info/save/load/rewind/redirect/copy/attach."""
        return self._conversation

    @property
    def models(self) -> BaseUIModelCommands:
        """Handlers for the yolo/plan toggles and model switching."""
        return self._models

    @property
    def exec(self) -> BaseUIExecCommands:
        """Handlers for shell exec, `/btw` side questions, and custom commands."""
        return self._exec

    # --- command dispatch (with hooks) ------------------------------------

    def command_table(self) -> "list[tuple[Callable, list[str], bool, bool]]":
        """Single source of truth for command routing.

        Ordered ``(handler, tokens, prefix, run_while_thinking)`` tuples used
        by both :meth:`classify_input` and :meth:`_run_command_chain`. Custom
        commands are matched separately.

        ``prefix=True`` → the token may be followed by ``" <args>"``;
        ``prefix=False`` → exact-match toggle.
        """
        base_ui = self._base_ui
        return [
            (base_ui.handle_btw_command, base_ui.btw_commands, True, True),
            (base_ui.handle_toggle_plan, base_ui.plan_commands, True, True),
            # prefix=True: `/yolo` toggles, `/yolo Write,Edit` sets selective yolo.
            (base_ui.handle_toggle_yolo, base_ui.yolo_toggle_commands, True, True),
            (base_ui.handle_exit_command, base_ui.exit_commands, False, False),
            (base_ui.handle_info_command, base_ui.info_commands, False, False),
            (base_ui.handle_save_command, base_ui.save_commands, True, False),
            (base_ui.handle_load_command, base_ui.load_commands, True, False),
            (base_ui.handle_rewind_command, base_ui.rewind_commands, True, False),
            (
                base_ui.handle_redirect_command,
                base_ui.redirect_output_commands,
                True,
                False,
            ),
            (base_ui.handle_attach_command, base_ui.attach_commands, True, False),
            (base_ui.handle_set_model_command, base_ui.set_model_commands, True, False),
            (base_ui.handle_set_command, base_ui.set_commands, True, False),
            (base_ui.handle_exec_command, base_ui.exec_commands, True, False),
            (base_ui.handle_copy_command, base_ui.copy_commands, True, False),
        ]

    def classify_input(self, text: str) -> str:
        """Classify Enter input for routing — by recognition, not by prefix.

        Returns one of:
            ``"thinking_command"`` — runs even while the LLM is thinking
                (``/btw``, YOLO toggle).
            ``"command"`` — any other recognized command (fires hooks).
            ``"message"`` — plain text forwarded to the LLM (no hooks).

        Never assumes a ``/`` prefix: command tokens are user-configurable.
        """
        stripped = text.strip()
        if not stripped:
            return "message"
        for _handler, tokens, prefix, run_while_thinking in self.command_table():
            if _matches(stripped, tokens, prefix):
                return "thinking_command" if run_while_thinking else "command"
        match = get_custom_command_match(stripped, self._base_ui.custom_commands)
        if match is None:
            return "message"
        return "thinking_command" if match[0].can_run_while_thinking else "command"

    def schedule_command(self, text: str, *, guarded: bool = True) -> None:
        """Run the hook-wrapped command dispatch as a background task.

        A second guarded command is rejected while one is in flight.
        ``guarded=False`` is for run-while-thinking commands (`/btw`, YOLO
        toggle), which neither wait for nor block one.
        """
        base_ui = self._base_ui
        if guarded:
            if self._command_in_flight:
                base_ui.append_to_output(
                    stylize_muted(
                        "\n  ⏳ A command is already running — wait for it to "
                        "finish.\n"
                    )
                )
                return
            self._command_in_flight = True
        # Via `base_ui` so a patched `ui.dispatch_command` is honored.
        task = asyncio.create_task(base_ui.dispatch_command(text, guarded=guarded))
        base_ui.background_tasks.add(task)
        task.add_done_callback(self._on_command_done)

    def _on_command_done(self, task: "asyncio.Task") -> None:
        """Drop the task reference and surface any swallowed exception."""
        self._base_ui.background_tasks.discard(task)
        try:
            exc = task.exception()
        except asyncio.CancelledError:
            return
        if exc is not None:
            logger.error("Command dispatch failed: %s", exc, exc_info=exc)

    async def dispatch_command(self, text: str, *, guarded: bool = True) -> None:
        """Fire PreCommand → run handlers → fire PostCommand.

        A blocking PreCommand hook cancels the command. Input no handler
        consumes goes to the LLM. PostCommand fires only when a handler ran.
        """
        base_ui = self._base_ui
        try:
            name, args = _split_command(text)
            event_data = {
                "command": name,
                "args": args,
                "session": base_ui.conversation_session_name,
            }
            pre_results = await base_ui.execute_hook_blocking(
                HookEvent.PRE_COMMAND,
                event_data,
                command_name=name,
                command_args=args,
            )
            if _command_blocked(pre_results):
                reason = _command_block_reason(pre_results) or "blocked by hook"
                base_ui.append_to_output(
                    stylize_muted(f"\n  ⛔ {name} blocked: {reason}\n")
                )
                return

            # A PreCommand hook may rewrite the argument, not the token.
            new_args = _command_arg_override(pre_results)
            if new_args is not None:
                args = new_args
                text = f"{name} {new_args}".strip()
                event_data["args"] = args

            handled = self._run_command_chain(text)
            if handled:
                base_ui.execute_hook(
                    HookEvent.POST_COMMAND,
                    {**event_data, "handled": True},
                    command_name=name,
                    command_args=args,
                    command_handled=True,
                )
            elif base_ui.is_thinking:
                base_ui.append_to_output(
                    stylize_muted(
                        f"\n  ⏳ `{name}` is not available while the model is "
                        "thinking — resend it after the turn finishes.\n"
                    )
                )
            else:
                # Recognized token but no handler consumed it — forward to LLM.
                base_ui.submit_message(text)
        finally:
            if guarded:
                self._command_in_flight = False

    def _run_command_chain(self, text: str) -> bool:
        """Run the command handlers in :meth:`command_table` order.

        Returns ``True`` if a handler consumed the input. While thinking, only
        run-while-thinking commands run; custom commands are tried last.
        """
        for handler, _tokens, _prefix, run_while_thinking in self.command_table():
            if not run_while_thinking and self._base_ui.is_thinking:
                break
            if handler(text):
                return True
        return self._base_ui.handle_custom_command(text)

    # --- delegators to the handler parts ---------------------------------

    async def run_shell_command(self, cmd: str) -> None:
        await self._exec.run_shell_command(cmd)

    async def stream_btw_response(self, llm_task: Any, question: str) -> None:
        await self._exec.stream_btw_response(llm_task, question)

    # --- help text --------------------------------------------------------

    def get_help_panel(
        self, art: str = "", header: str = "", max_commands: int | None = None
    ) -> "HelpPanel":
        """The help content as data, re-renderable at any width."""
        return HelpPanel(
            commands=self._get_command_help_entries(),
            shortcuts=list(_KEYBOARD_SHORTCUTS),
            art=art,
            header=header,
            max_commands=max_commands,
        )

    def print_help(self) -> None:
        """Write the help panel to the output."""
        self._base_ui.append_to_output(self.get_help_text())

    def get_help_text(self, width: int | None = None) -> str:
        if not self._get_command_help_entries():
            return ""
        if width is None:
            width = _get_default_help_width()
        return render_help_panel(self.get_help_panel(), width)

    def _get_command_help_entries(self) -> list[tuple[str, str]]:
        base_ui = self._base_ui
        raw_lines: list[tuple[str, str]] = []

        def add_cmd_help(commands: list[str], description: str):
            if commands:
                cmd = commands[0]
                raw_lines.append((cmd, description.replace("{cmd}", cmd)))

        add_cmd_help(base_ui.exit_commands, "Exit the application")
        add_cmd_help(base_ui.info_commands, "Show this help message")
        add_cmd_help(base_ui.attach_commands, "Attach file (usage: {cmd} <path>)")
        add_cmd_help(base_ui.save_commands, "Save conversation (usage: {cmd} <name>)")
        add_cmd_help(base_ui.load_commands, "Load conversation (usage: {cmd} <name>)")
        add_cmd_help(
            base_ui.rewind_commands,
            "List snapshots or restore one (usage: {cmd} [<n>|<sha>])",
        )
        add_cmd_help(
            base_ui.redirect_output_commands,
            "Copy last output to clipboard (bare), or save to file (usage: {cmd} <file>)",
        )
        add_cmd_help(
            base_ui.copy_commands,
            "Copy full transcript to clipboard (bare), or save to file (usage: {cmd} <file>)",
        )
        add_cmd_help(base_ui.summarize_commands, "Summarize conversation history")
        add_cmd_help(base_ui.yolo_toggle_commands, "Toggle YOLO mode")
        add_cmd_help(
            base_ui.set_model_commands,
            "Set model (usage: {cmd} <model-name>, {cmd} small <model-name>, {cmd} multimodal <model-name>)",
        )
        add_cmd_help(
            base_ui.set_commands,
            "Set a config value or live model (usage: {cmd} <name> <value>, e.g. {cmd} LLM_MODEL gpt-4o or {cmd} model gpt-4o)",
        )
        add_cmd_help(
            base_ui.exec_commands, "Execute shell command (usage: {cmd} <command>)"
        )
        add_cmd_help(
            base_ui.btw_commands,
            "Ask a side question without saving to history (usage: {cmd} <question>)",
        )
        add_cmd_help(base_ui.plan_commands, "Toggle PLAN mode (read-only) on/off")
        seen_descriptions: set[str] = set()
        for custom_cmd in base_ui.custom_commands:
            if custom_cmd.description in seen_descriptions:
                continue
            seen_descriptions.add(custom_cmd.description)
            raw_lines.append((custom_cmd.command, custom_cmd.description))

        return raw_lines


_KEYBOARD_SHORTCUTS: list[tuple[str, str]] = [
    ("Ctrl+J", "Insert a newline (multi-line input)"),
    # Some terminals claim Ctrl+V for their own text-only paste.
    (
        "Ctrl+V / Alt+V",
        "Paste text or image from clipboard (Alt+V if your terminal captures Ctrl+V)",
    ),
    ("Shift+Tab", "Cycle mode: normal -> accept-edits -> plan"),
    ("Ctrl+K", "Toggle focus between input and output"),
    ("Esc", "Cancel running task or clear input"),
    ("Ctrl+Y", "Toggle YOLO mode"),
    ("Ctrl+O", "Expand/collapse tool call/thinking at cursor"),
    ("Ctrl+X", "Drop the queued message recalled with ↑"),
    ("Ctrl+C", "Copy selection, clear input, or exit"),
    ("↑ / ↓", "Navigate input history, or the queued messages it recalls"),
]


def _get_default_help_width() -> int | None:
    """Terminal width for UIs that print straight to the terminal."""
    try:
        return get_terminal_size().columns
    except Exception:
        return None


def _matches(text: str, tokens: list[str], prefix: bool) -> bool:
    """Case-insensitive exact token match, or ``"<token> <args>"`` when `prefix`."""
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

    Read from each result's ``data``; the highest-priority hook wins.
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
