"""`LLMChatTask` session runners: drive a built inner `LLMTask` either as a
one-shot run or through an interactive UI.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from typing import TYPE_CHECKING, Any, cast

from zrb.config.config import CFG
from zrb.context.shared_context import SharedContext
from zrb.llm.custom_command.action_command import ActionCommand
from zrb.llm.custom_command.resolver import (
    get_custom_command_match,
    resolve_custom_commands,
    run_custom_command,
)
from zrb.llm.task.chat.agent_mention import resolve_agent_mention
from zrb.llm.util.feature_config import (
    get_session_ui,
    reset_session_ui,
    set_session_ui,
)
from zrb.session.session import Session
from zrb.util.attr import get_attr
from zrb.util.cli.style import stylize_muted

if TYPE_CHECKING:
    from zrb.context.any_context import AnyContext
    from zrb.llm.agent.types import UserContent
    from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
    from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
    from zrb.llm.task.chat.task import LLMChatTask
    from zrb.llm.task.llm_task import LLMTask
    from zrb.llm.ui.any_ui import AnyUI
    from zrb.llm.ui.base.ui import BaseUI
    from zrb.llm.ui.multi_ui import MultiUI


class ChatRunning:
    """Interactive + non-interactive session orchestration for LLMChatTask."""

    def __init__(self, llm_chat_task: "LLMChatTask") -> None:
        self._llm_chat_task = llm_chat_task

    @property
    def llm_chat_task(self) -> "LLMChatTask":
        """The owning `LLMChatTask` this runner reads state from."""
        return self._llm_chat_task

    async def run_non_interactive_session(
        self,
        ctx: "AnyContext",
        llm_task_core: "LLMTask",
        history_manager: "AnyHistoryManager",
        ui_commands: dict[str, list[str]],
        initial_message: Any,
        initial_conversation_name: str,
        initial_yolo: "bool | frozenset[str]",
        initial_attachments: "list[UserContent]",
    ) -> Any:
        effective_message, reply = _expand_message(
            initial_message, self._resolve_custom_commands()
        )
        if effective_message is None:
            # An action command ran in place of the turn.
            if reply:
                ctx.print(reply, plain=True)
            return reply

        # Factory-produced UIs (e.g. the web/SSE HTTPUI) become output sinks so
        # run_agent streams through them. Programmatic `uis` are already wired
        # in by `_create_llm_task_core`; factories need the core task instance.
        self._attach_ui_factories(
            ctx=ctx,
            llm_task_core=llm_task_core,
            history_manager=history_manager,
            ui_commands=ui_commands,
            initial_message=effective_message,
            initial_conversation_name=initial_conversation_name,
            initial_yolo=initial_yolo,
            initial_attachments=initial_attachments,
        )

        session_input = {
            "message": effective_message,
            "session": initial_conversation_name,
            "yolo": bool(initial_yolo),  # inner task uses dynamic_yolo; just pass bool
            "attachments": initial_attachments,
            "model": self._llm_chat_task.get_model(ctx),
            "interactive": False,
        }
        shared_ctx = SharedContext(
            input=session_input,
            print_fn=ctx.shared_print,
        )
        session = Session(shared_ctx)
        uis = llm_task_core.get_uis()
        # the first sink stands for the session; the web runner
        # attaches one HTTPUI, so there is no second to choose from.
        with _bound_session_ui(uis[0] if uis else None):
            result = await llm_task_core.async_run(session)
        # Unlike stream_ai_response, this path never finalizes with a rendered
        # pass, so do it here for every UI that supports it.
        if isinstance(result, str):
            for ui in llm_task_core.get_uis():
                append_markdown = getattr(ui, "append_markdown", None)
                if callable(append_markdown):
                    append_markdown(result)
        ctx.xcom["__conversation_name__"] = initial_conversation_name
        return result

    def _attach_ui_factories(
        self,
        ctx: "AnyContext",
        llm_task_core: "LLMTask",
        history_manager: "AnyHistoryManager",
        ui_commands: dict[str, list[str]],
        initial_message: Any,
        initial_conversation_name: str,
        initial_yolo: "bool | frozenset[str]",
        initial_attachments: "list[UserContent]",
    ) -> None:
        """Resolve the UI factories and attach the results to the core task."""
        for factory in self._llm_chat_task.ui_factories:
            factory_ui = factory(
                ctx=ctx,
                llm_task=llm_task_core,
                history_manager=history_manager,
                ui_commands=ui_commands,
                initial_message=initial_message,
                initial_conversation_name=initial_conversation_name,
                initial_yolo=initial_yolo,
                initial_attachments=initial_attachments,
            )
            for ui in factory_ui if isinstance(factory_ui, list) else [factory_ui]:
                llm_task_core.append_ui(ui)

    def _resolve_custom_commands(self) -> list["AnyCustomCommand"]:
        """Resolve custom commands, calling any callable factories."""
        return resolve_custom_commands(self._llm_chat_task.custom_commands)

    async def run_interactive_session(
        self,
        ctx: "AnyContext",
        llm_task_core: "LLMTask",
        history_manager: "AnyHistoryManager",
        ui_commands: dict[str, list[str]],
        initial_message: Any,
        initial_conversation_name: str,
        initial_yolo: "bool | frozenset[str]",
        initial_attachments: "list[UserContent]",
        enable_rewind: bool = False,
        snapshot_dir: str = "",
    ) -> Any:
        resolved_custom_commands = self._resolve_custom_commands()
        # An action may need the UI (`/photo` attaches to it), which does not
        # exist yet: run it once the UI does.
        initial_action = ""
        if _is_action_command(initial_message, resolved_custom_commands):
            initial_action, initial_message, reply = initial_message, "", None
        else:
            initial_message, reply = _expand_message(
                initial_message, resolved_custom_commands
            )
        if initial_message is None:
            initial_message = ""

        resolved_uis: list["AnyUI"] = list(self._llm_chat_task.uis)
        for factory in self._llm_chat_task.ui_factories:
            factory_ui = factory(
                ctx=ctx,
                llm_task=llm_task_core,
                history_manager=history_manager,
                ui_commands=ui_commands,
                initial_message=initial_message,
                initial_conversation_name=initial_conversation_name,
                initial_yolo=initial_yolo,
                initial_attachments=initial_attachments,
                custom_commands=resolved_custom_commands,
            )
            if isinstance(factory_ui, list):
                resolved_uis.extend(factory_ui)
            else:
                resolved_uis.append(factory_ui)

        default_ui_kwargs = self._build_default_ui_kwargs(
            ctx=ctx,
            llm_task_core=llm_task_core,
            history_manager=history_manager,
            initial_message=initial_message,
            initial_conversation_name=initial_conversation_name,
            initial_yolo=initial_yolo,
            initial_attachments=initial_attachments,
            enable_rewind=enable_rewind,
            snapshot_dir=snapshot_dir,
            resolved_custom_commands=resolved_custom_commands,
        )

        ui = self._resolve_ui(resolved_uis, default_ui_kwargs)

        if initial_conversation_name:
            self.load_session_history(ui, history_manager, initial_conversation_name)
        if initial_action:
            outcome = run_custom_command(
                initial_action, resolved_custom_commands, _get_action_ui(ui)
            )
            reply = outcome.reply if outcome is not None else None
        if reply:
            ui.append_to_output(stylize_muted(f"\n  {reply}\n"))

        with _bound_session_ui(_get_action_ui(ui)):
            await ui.run_async()
        last_output = getattr(ui, "last_output", "")
        final_conversation_name = self._llm_chat_task.get_ui_conversation_name(
            ui, initial_conversation_name
        )
        ctx.xcom["__conversation_name__"] = final_conversation_name
        return last_output

    def _build_default_ui_kwargs(
        self,
        ctx: "AnyContext",
        llm_task_core: "LLMTask",
        history_manager: "AnyHistoryManager",
        initial_message: Any,
        initial_conversation_name: str,
        initial_yolo: "bool | frozenset[str]",
        initial_attachments: "list[UserContent]",
        enable_rewind: bool = False,
        snapshot_dir: str = "",
        resolved_custom_commands: "list[AnyCustomCommand] | None" = None,
    ) -> dict[str, Any]:
        """Build keyword arguments shared by all default UI constructor calls."""
        resolved_custom_model_names = (
            get_attr(ctx, self._llm_chat_task.custom_model_names, []) or []
        )
        if not isinstance(resolved_custom_model_names, list):
            resolved_custom_model_names = []

        if resolved_custom_commands is None:
            resolved_custom_commands = self._resolve_custom_commands()

        # Layer this run's yolo state and session name over the task's ui_config.
        ui_config = replace(
            self._llm_chat_task.ui_config,
            is_yolo=initial_yolo,
            conversation_session_name=initial_conversation_name,
        )

        return {
            "ctx": ctx,
            "output_lexer": None,  # resolved lazily to avoid early import
            "llm_task": llm_task_core,
            "history_manager": history_manager,
            "initial_message": initial_message,
            "initial_attachments": initial_attachments,
            "ui_config": ui_config,
            "triggers": self._llm_chat_task.triggers,
            "response_handlers": self._llm_chat_task.response_handlers,
            "tool_policies": self._llm_chat_task.tool_policies,
            "argument_formatters": self._llm_chat_task.argument_formatters,
            "markdown_theme": self._llm_chat_task.markdown_theme,
            "custom_commands": resolved_custom_commands,
            "model": self._llm_chat_task.get_model(ctx),
            "custom_model_names": resolved_custom_model_names,
            "enable_rewind": enable_rewind,
            "snapshot_dir": snapshot_dir,
        }

    def _resolve_ui(
        self,
        resolved_uis: "list[AnyUI]",
        default_kwargs: dict[str, Any],
    ) -> "AnyUI":
        """Determine the UI to use: factory-only, combined, or default-only."""
        # lazy: zrb.llm.ui.default.ui transitively loads prompt_toolkit,
        # pydantic_ai, pdfplumber and vosk.
        from zrb.llm.ui.default.ui import UI

        if resolved_uis and not self._llm_chat_task.include_default_ui:
            if len(resolved_uis) == 1:
                return resolved_uis[0]
            return self._create_multi_ui(resolved_uis)

        # lazy: zrb.llm.ui.default.app.lexer transitively loads prompt_toolkit.
        from zrb.llm.ui.default.app.lexer import CLIStyleLexer

        default_kwargs["output_lexer"] = CLIStyleLexer()
        default_ui = UI(**default_kwargs)

        if not resolved_uis:
            return default_ui

        ui = self._create_multi_ui([default_ui] + resolved_uis)
        ui.set_tool_call_handler(default_ui.tool_call_handler)
        return ui

    def _create_multi_ui(self, uis: "list[AnyUI]") -> "MultiUI":
        """Combine `uis` into a `MultiUI` wired to the task's approval channel."""
        # lazy: zrb.llm.ui.multi_ui transitively loads prompt_toolkit and
        # pydantic_ai; zrb.llm.approval transitively loads pydantic_ai.
        from zrb.llm.approval import resolve_approval_channel
        from zrb.llm.ui.multi_ui import MultiUI

        ui = MultiUI(uis)
        approval_channel = resolve_approval_channel(
            self._llm_chat_task.approval_channels
        )
        if approval_channel is not None:
            ui.set_approval_channel(approval_channel)
        return ui

    def load_session_history(
        self,
        ui: "AnyUI",
        history_manager: "AnyHistoryManager",
        conversation_name: str,
    ) -> None:
        """Load and display session history if it exists.

        Uses the UI's `replay_history` when it has one, else a plain text dump.
        """
        if not conversation_name:
            return
        try:
            history = history_manager.load(conversation_name)
            if not history:
                return
            replay = getattr(ui, "replay_history", None)
            if callable(replay):
                replay(history)
            else:
                # lazy: zrb.llm.util.history_formatter transitively loads pydantic_ai.
                from zrb.llm.util.history_formatter import format_history_as_text

                ui.append_to_output(format_history_as_text(history))
        except FileNotFoundError:
            pass
        except Exception as e:
            CFG.LOGGER.warning(
                f"Failed to load history for session {conversation_name}: {e}"
            )


@contextmanager
def _bound_session_ui(ui: "AnyUI | None") -> Iterator[None]:
    """Make *ui* the session's UI for the block, ``None`` meaning none, then
    put back the one bound before it, if any."""
    previous = get_session_ui()
    if ui is None:
        reset_session_ui()
    else:
        set_session_ui(ui)
    try:
        yield
    finally:
        if previous is None:
            reset_session_ui()
        else:
            set_session_ui(previous)


def _get_action_ui(ui: "AnyUI") -> "BaseUI":
    """The UI an action command acts on: a `MultiUI`'s main UI, else *ui*."""
    return cast("BaseUI", getattr(ui, "main_ui", None) or ui)


def _is_action_command(message: Any, custom_commands: "list[AnyCustomCommand]") -> bool:
    if not isinstance(message, str):
        return False
    match = get_custom_command_match(message, custom_commands)
    return match is not None and isinstance(match[0], ActionCommand)


def _expand_message(
    message: Any, custom_commands: "list[AnyCustomCommand]"
) -> tuple[Any, str | None]:
    """Expand a slash command, else an @agent mention, in a string message.

    Returns ``(message, reply)``; an `ActionCommand` handled in-process
    returns ``(None, reply)`` since there is no turn to run.
    """
    if not isinstance(message, str):
        return message, None
    outcome = run_custom_command(message, custom_commands, None)
    if outcome is not None:
        return outcome.prompt, outcome.reply
    mentioned = resolve_agent_mention(message)
    return (message if mentioned is None else mentioned), None
