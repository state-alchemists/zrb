"""Session runners for `LLMChatTask`.

Holds `_run_non_interactive_session` and `_run_interactive_session`, the two
big orchestration methods that take a built `llm_task_core` plus all resolved
inputs and either return a one-shot result or hand off to an interactive UI.

Kept separate from `building.py` because:
- builder is config-time API (mutators);
- runner is execution-time orchestration (drives the inner LLMTask + UI loop).

Composed into `LLMChatTask` as `self._running`: takes the owning
`LLMChatTask` and reads its state through that reference. Two calls
(`get_model`, `_get_ui_conversation_name`) reach methods implemented by the
sibling `ChatExecution` collaborator — routed through the owner, which
delegates to both collaborators uniformly.
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
    from pydantic_ai import UserContent

    from zrb.context.any_context import AnyContext
    from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
    from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
    from zrb.llm.task.chat.task import LLMChatTask
    from zrb.llm.task.llm_task import LLMTask
    from zrb.llm.tool_call.ui_protocol import UIProtocol


class ChatRunning:
    """Interactive + non-interactive session orchestration for LLMChatTask."""

    def __init__(self, owner: "LLMChatTask") -> None:
        self._owner = owner

    async def _run_non_interactive_session(
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
        # LSP/SESSION_END teardown. Programmatic self._owner._uis are already
        # wired into the core task by _create_llm_task_core; only factories
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
            "model": self._owner.get_model(ctx),
            "interactive": False,
        }
        shared_ctx = SharedContext(
            input=session_input,
            print_fn=ctx.shared_print,  # Use current task's print function
        )
        session = Session(shared_ctx)
        result = await llm_task_core.async_run(session)
        # Unlike _stream_ai_response, this loop never finalizes with a
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
        for factory in self._owner._ui_factories:
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
        return resolve_custom_commands(self._owner._custom_commands)

    async def _run_interactive_session(
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
        # lazy: zrb.llm.ui.base.ui transitively loads pydantic_ai,
        # prompt_toolkit, pdfplumber and playwright.
        from zrb.llm.ui.base.ui import BaseUI

        # Mirror _run_non_interactive_session's slash-command resolution.
        # Resolved once here and reused by _build_default_ui_kwargs below,
        # instead of re-resolving self._owner._custom_commands a second time.
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
        # 1. Resolve UIs from factories
        resolved_uis: list["UIProtocol"] = list(self._owner._uis)
        for factory in self._owner._ui_factories:
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

        # 2. Resolve shared UI attributes
        default_ui_kwargs = self._build_default_ui_kwargs(
            ctx=ctx,
            llm_task_core=llm_task_core,
            history_manager=history_manager,
            ui_commands=ui_commands,
            initial_message=initial_message,
            initial_conversation_name=initial_conversation_name,
            initial_yolo=initial_yolo,
            initial_attachments=initial_attachments,
            enable_rewind=enable_rewind,
            snapshot_dir=snapshot_dir,
            resolved_custom_commands=resolved_custom_commands,
        )

        # 3. Determine the UI to use
        ui = self._resolve_ui(resolved_uis, default_ui_kwargs)

        # 4. Load and display session history
        if initial_conversation_name:
            self._load_session_history(ui, history_manager, initial_conversation_name)

        # 5. Run the UI
        if ui is None:
            raise ValueError("No UI available")
        if isinstance(ui, BaseUI) or hasattr(ui, "run_async"):
            await ui.run_async()
        else:
            raise ValueError(f"UI {type(ui)} does not implement run_async")
        last_output = getattr(ui, "last_output", "")
        final_conversation_name = self._owner._get_ui_conversation_name(
            ui, initial_conversation_name
        )
        ctx.xcom["__conversation_name__"] = final_conversation_name
        return last_output

    def _build_default_ui_kwargs(
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
        resolved_custom_commands: "list[AnyCustomCommand] | None" = None,
    ) -> dict[str, Any]:
        """Build keyword arguments shared by all default UI constructor calls."""
        resolved_custom_model_names = (
            get_attr(ctx, self._owner._custom_model_names, []) or []
        )
        if not isinstance(resolved_custom_model_names, list):
            resolved_custom_model_names = []

        if resolved_custom_commands is None:
            resolved_custom_commands = self._resolve_custom_commands()

        effective_show_ollama_models = (
            CFG.LLM_SHOW_OLLAMA_MODELS
            if self._owner._show_ollama_models is None
            else self._owner._show_ollama_models
        )
        effective_show_pydantic_ai_models = (
            CFG.LLM_SHOW_PYDANTIC_AI_MODELS
            if self._owner._show_pydantic_ai_models is None
            else self._owner._show_pydantic_ai_models
        )

        return {
            "ctx": ctx,
            "yolo_xcom_key": self._owner._yolo_xcom_key,
            **{
                key: get_str_attr(ctx, value, "", render)
                for key, (value, render) in self._owner._ui_texts.items()
            },
            "output_lexer": None,  # resolved lazily to avoid early import
            "llm_task": llm_task_core,
            "history_manager": history_manager,
            "initial_message": initial_message,
            "initial_attachments": initial_attachments,
            "conversation_session_name": initial_conversation_name,
            "is_yolo": initial_yolo,
            "triggers": self._owner._triggers,
            "response_handlers": self._owner._response_handlers,
            "tool_policies": self._owner._tool_policies,
            "argument_formatters": self._owner._argument_formatters,
            "markdown_theme": self._owner._markdown_theme,
            "summarize_commands": ui_commands["summarize"],
            "attach_commands": ui_commands["attach"],
            "exit_commands": ui_commands["exit"],
            "info_commands": ui_commands["info"],
            "save_commands": ui_commands["save"],
            "load_commands": ui_commands["load"],
            "rewind_commands": ui_commands["rewind"],
            "yolo_toggle_commands": ui_commands["yolo_toggle"],
            "set_model_commands": ui_commands["set_model"],
            "redirect_output_commands": ui_commands["redirect_output"],
            "exec_commands": ui_commands["exec"],
            "btw_commands": ui_commands["btw"],
            "plan_commands": ui_commands["plan"],
            "copy_commands": ui_commands["copy"],
            "voice_commands": ui_commands["voice"],
            "photo_commands": ui_commands["photo"],
            "custom_commands": resolved_custom_commands,
            "model": self._owner.get_model(ctx),
            "custom_model_names": resolved_custom_model_names,
            "show_ollama_models": effective_show_ollama_models,
            "show_pydantic_ai_models": effective_show_pydantic_ai_models,
            "enable_rewind": enable_rewind,
            "snapshot_dir": snapshot_dir,
        }

    def _resolve_ui(
        self,
        resolved_uis: "list[UIProtocol]",
        default_kwargs: dict[str, Any],
    ) -> "UIProtocol":
        """Determine the UI to use: factory-only, combined, or default-only."""
        # lazy: zrb.llm.ui.default.ui and zrb.llm.ui.multi_ui transitively
        # load prompt_toolkit, pydantic_ai, pdfplumber and vosk.
        from zrb.llm.ui.default.ui import UI
        from zrb.llm.ui.multi_ui import MultiUI

        if resolved_uis and not self._owner._include_default_ui:
            if len(resolved_uis) == 1:
                return resolved_uis[0]
            ui = MultiUI(resolved_uis)
            if len(self._owner._approval_channels) == 1:
                ui.set_approval_channel(self._owner._approval_channels[0])
            elif len(self._owner._approval_channels) > 1:
                # lazy: zrb.llm.approval transitively loads pydantic_ai.
                from zrb.llm.approval import MultiplexApprovalChannel

                ui.set_approval_channel(
                    MultiplexApprovalChannel(self._owner._approval_channels)
                )
            return ui

        # Create default UI with lazy import of output_lexer
        # lazy: zrb.llm.app.lexer transitively loads prompt_toolkit.
        from zrb.llm.app.lexer import CLIStyleLexer

        default_kwargs["output_lexer"] = CLIStyleLexer()
        default_ui = UI(**default_kwargs)

        if not resolved_uis:
            return default_ui

        all_uis = [default_ui] + resolved_uis
        ui = MultiUI(all_uis)
        if len(self._owner._approval_channels) == 1:
            ui.set_approval_channel(self._owner._approval_channels[0])
        elif len(self._owner._approval_channels) > 1:
            # lazy: zrb.llm.approval transitively loads pydantic_ai.
            from zrb.llm.approval import MultiplexApprovalChannel

            ui.set_approval_channel(
                MultiplexApprovalChannel(self._owner._approval_channels)
            )
        ui.set_tool_call_handler(default_ui.tool_call_handler)
        return ui

    def _load_session_history(
        self,
        ui: "UIProtocol",
        history_manager: "AnyHistoryManager",
        conversation_name: str,
    ) -> None:
        """Load and display session history if it exists.

        Replays the loaded messages through the UI's live-message rendering
        paths (markdown for assistant text, faint for tool calls, etc.) so
        resuming a session feels like continuing the conversation. Falls back
        to a plain text dump for UIs that don't implement `_replay_history`.
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
