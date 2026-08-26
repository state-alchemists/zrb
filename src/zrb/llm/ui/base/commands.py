"""Slash-command dispatch for `BaseUI`.

Routes recognized commands to handlers and fires PreCommand/PostCommand
hooks. The concrete `handle_*` handlers live in sibling collaborators this
class composes (`self._conversation`, `self._models`, `self._exec`), each
taking the same `BaseUI` reference in `self._base_ui`:

  conversation_commands.py - exit/info/save/load/rewind/redirect/copy/attach
  model_commands.py        - yolo/plan toggles + model switching
  exec_commands.py         - shell exec, /btw side questions, custom cmds

Each `handle_*` returns `True` if the input was consumed (a command matched),
`False` otherwise.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.llm.custom_command.resolver import resolve_custom_command
from zrb.llm.hook.types import HookEvent
from zrb.llm.ui.base.conversation_commands import BaseUIConversationCommands
from zrb.llm.ui.base.exec_commands import BaseUIExecCommands
from zrb.llm.ui.base.model_commands import BaseUIModelCommands
from zrb.util.cli.help_panel import HelpPanel, render_help_panel
from zrb.util.cli.style import stylize_muted, stylize_warning
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
        # Dispatcher-private (not `BaseUI` state): nothing outside
        # schedule_command / dispatch_command reads or writes this.
        self._command_in_flight = False

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
        base_ui = self._base_ui
        return [
            (self._exec.handle_btw_command, base_ui.btw_commands, True, True),
            (self._models.handle_toggle_plan, base_ui.plan_commands, True, True),
            # prefix=True: `/yolo` toggles, `/yolo Write,Edit` sets selective yolo.
            (
                self._models.handle_toggle_yolo,
                base_ui.yolo_toggle_commands,
                True,
                True,
            ),
            (self.handle_toggle_voice, base_ui.voice_commands, False, True),
            (
                self._conversation.handle_exit_command,
                base_ui.exit_commands,
                False,
                False,
            ),
            (
                self._conversation.handle_info_command,
                base_ui.info_commands,
                False,
                False,
            ),
            (
                self._conversation.handle_save_command,
                base_ui.save_commands,
                True,
                False,
            ),
            (
                self._conversation.handle_load_command,
                base_ui.load_commands,
                True,
                False,
            ),
            (
                self._conversation.handle_rewind_command,
                base_ui.rewind_commands,
                True,
                False,
            ),
            (
                self._conversation.handle_redirect_command,
                base_ui.redirect_output_commands,
                True,
                False,
            ),
            (
                self._conversation.handle_attach_command,
                base_ui.attach_commands,
                True,
                False,
            ),
            (
                self._conversation.handle_photo_command,
                base_ui.photo_commands,
                True,
                False,
            ),
            (
                self._models.handle_set_model_command,
                base_ui.set_model_commands,
                True,
                False,
            ),
            (self._exec.handle_exec_command, base_ui.exec_commands, True, False),
            (
                self._conversation.handle_copy_command,
                base_ui.copy_commands,
                True,
                False,
            ),
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
        if resolve_custom_command(stripped, self._base_ui.custom_commands) is not None:
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
        # Through `self._base_ui` (not bare `self`): `dispatch_command` is also a
        # `BaseUI` delegator, and patching `ui.dispatch_command` directly (as
        # tests do) must be honored here too.
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

        A PreCommand hook that blocks (HookResult.block / exit code 2 / deny)
        cancels the command. If no handler consumes the input (e.g. a command
        typed without its required argument), it is forwarded to the LLM.
        PostCommand fires only when a handler actually ran.
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

            # A PreCommand hook may rewrite the argument (e.g. swap the model in
            # `/model opus` → `sonnet`). The command token itself is preserved.
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
                # A non-thinking command arrived mid-turn. Dropping it
                # silently would look like the TUI ate the input; say so.
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
        """Run the command handlers in priority order (see :meth:`_command_table`).

        Returns ``True`` if a handler consumed the input. Run-while-thinking
        commands (`/btw`, YOLO toggle) run first; everything else is gated
        behind the thinking guard. Custom commands are tried last.
        """
        for handler, _tokens, _prefix, run_while_thinking in self._command_table():
            if not run_while_thinking and self._base_ui.is_thinking:
                return False
            if handler(text):
                return True
        return self._exec.handle_custom_command(text)

    # --- conversation commands (delegate to `self._conversation`) --------

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
        await self._conversation.submit_photo(device)

    def apply_persona_for_session(self, name: str) -> None:
        self._conversation.apply_persona_for_session(name)

    # --- model commands (delegate to `self._models`) ----------------------

    def toggle_yolo(self) -> None:
        self._models.toggle_yolo()

    def handle_toggle_yolo(self, text: str) -> bool:
        return self._models.handle_toggle_yolo(text)

    def toggle_plan(self) -> None:
        self._models.toggle_plan()

    def handle_toggle_plan(self, text: str) -> bool:
        return self._models.handle_toggle_plan(text)

    def current_cycle_mode(self) -> str:
        return self._models.current_cycle_mode()

    def cycle_mode(self) -> None:
        self._models.cycle_mode()

    def handle_set_model_command(self, text: str) -> bool:
        return self._models.handle_set_model_command(text)

    # --- exec commands (delegate to `self._exec`) --------------------------

    def handle_exec_command(self, text: str) -> bool:
        return self._exec.handle_exec_command(text)

    async def run_shell_command(self, cmd: str) -> None:
        await self._exec.run_shell_command(cmd)

    def handle_btw_command(self, text: str) -> bool:
        return self._exec.handle_btw_command(text)

    async def stream_btw_response(self, llm_task: Any, question: str) -> None:
        await self._exec.stream_btw_response(llm_task, question)

    def handle_custom_command(self, text: str) -> bool:
        return self._exec.handle_custom_command(text)

    def handle_toggle_voice(self, text: str) -> bool:
        """Toggle voice dictation mode on/off.

        ``/voice`` when OFF → enter voice mode (press space to record).
        ``/voice`` when ON → exit voice mode without recording.
        Voice mode also auto-exits after a recording completes.
        """
        base_ui = self._base_ui
        if text.strip().lower() not in [c.lower() for c in base_ui.voice_commands]:
            return False
        auto_vosk = False
        if not CFG.LLM_VOICE_ENABLED:
            if not _voice_auto_enabled_by_vosk():
                base_ui.append_to_output(
                    stylize_warning(
                        "\n  🎤 Voice dictation is not enabled.\n"
                        f"     Set {CFG.ENV_PREFIX}_LLM_VOICE_ENABLED=on and restart.\n"
                    )
                )
                return True
            auto_vosk = True
        if base_ui.voice_mode_active:
            self._exit_voice_mode()
        else:
            base_ui.voice_mode_active = True
            ptt_key = CFG.LLM_VOICE_PUSH_TO_TALK_KEY.strip()
            backend_note = " (vosk detected)" if auto_vosk else ""
            base_ui.append_to_output(
                stylize_muted(
                    f"\n  🎤 Voice dictation: ON{backend_note}"
                    f" — press [{ptt_key}] to record\n"
                )
            )
        base_ui.invalidate_ui()
        return True

    def _exit_voice_mode(self):
        """Exit voice mode and stop any in-flight recording."""
        base_ui = self._base_ui
        base_ui.voice_mode_active = False
        base_ui.voice_recording_active = False
        if base_ui.voice_stop_event is not None:
            base_ui.voice_stop_event.set()
        base_ui.voice_stop_event = None
        base_ui.voice_task = None
        base_ui.append_to_output(stylize_muted("\n  🎤 Voice dictation: OFF\n"))

    # --- help text --------------------------------------------------------

    def get_help_panel(
        self, art: str = "", header: str = "", max_commands: int | None = None
    ) -> "HelpPanel":
        """The help content as data, ready to be rendered at any width.

        Keeping the rows unformatted is what lets the panel be re-rendered on
        every resize instead of being wrapped once and clipped to fit. Row
        *count* is still capped by `max_commands` where screen space is tight.
        """
        return HelpPanel(
            commands=self._get_command_help_entries(),
            shortcuts=list(_KEYBOARD_SHORTCUTS),
            art=art,
            header=header,
            max_commands=max_commands,
        )

    def print_help(self) -> None:
        """Write the help panel to the output (public API; overridable)."""
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
            if commands and len(commands) > 0:
                cmd = commands[0]
                raw_lines.append((cmd, description.replace("{cmd}", cmd)))

        add_cmd_help(base_ui.exit_commands, "Exit the application")
        add_cmd_help(base_ui.info_commands, "Show this help message")
        add_cmd_help(base_ui.attach_commands, "Attach file (usage: {cmd} <path>)")
        add_cmd_help(
            base_ui.photo_commands,
            "Capture a photo from the camera (usage: {cmd} [device])",
        )
        add_cmd_help(base_ui.save_commands, "Save conversation (usage: {cmd} <name>)")
        add_cmd_help(base_ui.load_commands, "Load conversation (usage: {cmd} <name>)")
        if base_ui.snapshot_manager is not None:
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
            base_ui.exec_commands, "Execute shell command (usage: {cmd} <command>)"
        )
        add_cmd_help(
            base_ui.btw_commands,
            "Ask a side question without saving to history (usage: {cmd} <question>)",
        )
        add_cmd_help(base_ui.plan_commands, "Toggle PLAN mode (read-only) on/off")
        add_cmd_help(base_ui.voice_commands, "Toggle voice dictation on/off")
        for custom_cmd in base_ui.custom_commands:
            raw_lines.append((custom_cmd.command, custom_cmd.description))

        return raw_lines


_KEYBOARD_SHORTCUTS: list[tuple[str, str]] = [
    ("Ctrl+J", "Insert a newline (multi-line input)"),
    ("Ctrl+V / Alt+V", "Paste text or image from clipboard"),
    ("Shift+Tab", "Cycle mode: normal -> accept-edits -> plan"),
    ("Ctrl+K", "Toggle focus between input and output"),
    ("Esc", "Cancel running task or clear input"),
    ("Ctrl+Y", "Toggle YOLO mode"),
    ("Ctrl+O", "Expand/collapse tool call/thinking at cursor"),
    ("Ctrl+C", "Copy selection, clear input, or exit"),
    ("↑ / ↓", "Navigate input history"),
]


def _get_default_help_width() -> int | None:
    """Terminal width for UIs that print straight to the terminal."""
    try:
        return get_terminal_size().columns
    except Exception:
        return None


def _voice_auto_enabled_by_vosk() -> bool:
    """Voice may run without explicit opt-in when config is untouched and vosk
    is installed.

    Two conditions must hold. First, `LLM_VOICE_ENABLED` must be unset — an
    explicit value always wins: `on` enables voice with any backend, `off`
    disables it even when vosk is installed. Second, the configured backend
    must actually be vosk: auto-enabling a user who set
    `LLM_VOICE_MODE=openai` would announce "(vosk detected)" and then fail on
    a missing API key.
    """
    if CFG.is_env_set("LLM_VOICE_ENABLED"):
        return False
    if CFG.is_env_set("LLM_VOICE_MODE"):
        return False
    # lazy: tests patch zrb.llm.voice.engine.vosk_installed; hoisting would
    # bind the name at this module's load time and bypass the mock.
    from zrb.llm.voice.engine import vosk_installed

    return vosk_installed()


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
