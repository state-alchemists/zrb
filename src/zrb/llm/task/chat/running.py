"""Session runners for `LLMChatTask`.

Holds `run_non_interactive_session` and `run_interactive_session`, the two
big orchestration methods that take a built `llm_task_core` plus all resolved
inputs and either return a one-shot result or hand off to an interactive UI.

Kept separate from `building.py` because:
- builder is config-time API (mutators);
- runner is execution-time orchestration (drives the inner LLMTask + UI loop).

Composed into `LLMChatTask` as `self._running`: keeps `LLMChatTask` in
`self._llm_chat_task` and reads its state through that reference. Two calls
(`get_model`, `get_ui_conversation_name`) reach methods implemented by the
sibling `ChatExecution` collaborator through `self._llm_chat_task`'s public
facade, which delegates to both collaborators uniformly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.context.shared_context import SharedContext
from zrb.llm.custom_command.resolver import (
    resolve_custom_command,
    resolve_custom_commands,
)
from zrb.llm.task.chat.agent_mention import resolve_agent_mention
from zrb.session.session import Session
from zrb.util.attr import get_attr, get_str_attr

if TYPE_CHECKING:
    from zrb.context.any_context import AnyContext
    from zrb.llm.agent.types import UserContent
    from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
    from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
    from zrb.llm.task.chat.task import LLMChatTask
    from zrb.llm.task.llm_task import LLMTask
    from zrb.llm.ui.any_ui import AnyUI


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
        # Resolve custom commands and intercept if the message is a slash command
        resolved_custom_commands = self._resolve_custom_commands()
        effective_message = initial_message
        if isinstance(initial_message, str):
            resolved = resolve_custom_command(initial_message, resolved_custom_commands)
            if resolved is not None:
                effective_message = resolved
            else:
                # Only nudge on @mention when the message wasn't already a
                # slash command — the two are mutually exclusive syntaxes.
                mentioned = resolve_agent_mention(initial_message)
                if mentioned is not None:
                    effective_message = mentioned

        # Attach factory-produced UIs (e.g. the web/SSE HTTPUI) as output sinks
        # so run_agent streams through them. This is what makes browser chat
        # work without the interactive session's per-turn history replay and
        # LSP/SESSION_END teardown. Programmatic self._llm_chat_task.uis are
        # already wired into the core task by _create_llm_task_core; only factories
        # need resolving here, now that the core task instance exists.
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

        # AsyncExitStack is handled by LLMTask._exec_action
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
            print_fn=ctx.shared_print,  # Use current task's print function
        )
        session = Session(shared_ctx)
        result = await llm_task_core.async_run(session)
        # Unlike stream_ai_response, this loop never finalizes with a
        # rendered pass -- do it here for every UI that supports it.
        if isinstance(result, str):
            for ui in llm_task_core.get_uis():
                append_markdown = getattr(ui, "append_markdown", None)
                if callable(append_markdown):
                    append_markdown(result)
        # Store conversation name in xcom for CLI to print at the end
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
        """Resolve `_ui_factories` and attach the results to the core task."""
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
        # Mirror run_non_interactive_session's slash-command resolution.
        # Resolved once here and reused by _build_default_ui_kwargs below,
        # instead of re-resolving self._llm_chat_task.custom_commands a second
        # time.
        resolved_custom_commands = self._resolve_custom_commands()
        if isinstance(initial_message, str):
            resolved = resolve_custom_command(initial_message, resolved_custom_commands)
            if resolved is not None:
                initial_message = resolved
            else:
                mentioned = resolve_agent_mention(initial_message)
                if mentioned is not None:
                    initial_message = mentioned

        # Note: AsyncExitStack is handled by LLMTask._exec_action
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
        # lazy: zrb.llm.ui.ui_config transitively loads pydantic_ai,
        # prompt_toolkit, pdfplumber and playwright, via its package __init__.
        from dataclasses import replace

        resolved_custom_model_names = (
            get_attr(ctx, self._llm_chat_task.custom_model_names, []) or []
        )
        if not isinstance(resolved_custom_model_names, list):
            resolved_custom_model_names = []

        if resolved_custom_commands is None:
            resolved_custom_commands = self._resolve_custom_commands()

        ui_texts = {
            key: get_str_attr(ctx, value, "", render)
            for key, (value, render) in self._llm_chat_task.ui_texts.items()
        }

        # Layer this run's resolved values (yolo state, session name, and — if
        # set — a per-task-instance assistant name) over the task's own
        # ui_config, which already carries the command lists / yolo_xcom_key /
        # show_*_models resolved at construction (task override, else CFG).
        ui_config_overrides: dict[str, Any] = {
            "is_yolo": initial_yolo,
            "conversation_session_name": initial_conversation_name,
        }
        if ui_texts["assistant_name"]:
            ui_config_overrides["assistant_name"] = ui_texts["assistant_name"]
        ui_config = replace(self._llm_chat_task.ui_config, **ui_config_overrides)

        return {
            "ctx": ctx,
            "greeting": ui_texts["greeting"],
            "ascii_art": ui_texts["ascii_art"],
            "jargon": ui_texts["jargon"],
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
        # lazy: zrb.llm.ui.default.ui and zrb.llm.ui.multi_ui transitively
        # load prompt_toolkit, pydantic_ai, pdfplumber and vosk.
        from zrb.llm.ui.default.ui import UI
        from zrb.llm.ui.multi_ui import MultiUI

        if resolved_uis and not self._llm_chat_task.include_default_ui:
            if len(resolved_uis) == 1:
                return resolved_uis[0]
            ui = MultiUI(resolved_uis)
            # lazy: zrb.llm.approval transitively loads pydantic_ai.
            from zrb.llm.approval import resolve_approval_channel

            approval_channel = resolve_approval_channel(
                self._llm_chat_task.approval_channels
            )
            if approval_channel is not None:
                ui.set_approval_channel(approval_channel)
            return ui

        # Create default UI with lazy import of output_lexer
        # lazy: zrb.llm.ui.default.app.lexer transitively loads prompt_toolkit.
        from zrb.llm.ui.default.app.lexer import CLIStyleLexer

        default_kwargs["output_lexer"] = CLIStyleLexer()
        default_ui = UI(**default_kwargs)

        if not resolved_uis:
            return default_ui

        all_uis = [default_ui] + resolved_uis
        ui = MultiUI(all_uis)
        # lazy: zrb.llm.approval transitively loads pydantic_ai.
        from zrb.llm.approval import resolve_approval_channel

        approval_channel = resolve_approval_channel(
            self._llm_chat_task.approval_channels
        )
        if approval_channel is not None:
            ui.set_approval_channel(approval_channel)
        ui.set_tool_call_handler(default_ui.tool_call_handler)
        return ui

    def load_session_history(
        self,
        ui: "AnyUI",
        history_manager: "AnyHistoryManager",
        conversation_name: str,
    ) -> None:
        """Load and display session history if it exists.

        Replays the loaded messages through the UI's live-message rendering
        paths (markdown for assistant text, faint for tool calls, etc.) so
        resuming a session feels like continuing the conversation. Falls back
        to a plain text dump for UIs that don't implement `replay_history`.
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
