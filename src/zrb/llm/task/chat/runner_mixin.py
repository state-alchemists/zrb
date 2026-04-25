"""Session runners for `LLMChatTask`.

Holds `_run_non_interactive_session` and `_run_interactive_session`, the two
big orchestration methods that take a built `llm_task_core` plus all resolved
inputs and either return a one-shot result or hand off to an interactive UI.

Kept separate from `_chat_builder_mixin.py` because:
- builder is config-time API (mutators);
- runner is execution-time orchestration (drives the inner LLMTask + UI loop).

Assumes the host class provides:
- `_uis`, `_ui_factories`, `_include_default_ui`, `_approval_channels`
- `_yolo_xcom_key`, `_triggers`, `_response_handlers`, `_tool_policies`,
  `_argument_formatters`, `_markdown_theme`, `_custom_commands`
- `_custom_model_names`, `_ui_greeting`/`_render_ui_greeting`, `_ui_assistant_name`,
  `_render_ui_assistant_name`, `_ui_jargon`, `_render_ui_jargon`,
  `_ui_ascii_art_name`, `_render_ui_ascii_art_name`
- `_show_ollama_models`, `_show_pydantic_ai_models`
- `_get_model(ctx)`, `_get_ui_conversation_name(ui, name)`
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.context.shared_context import SharedContext
from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
from zrb.session.session import Session
from zrb.util.attr import get_attr, get_str_attr

if TYPE_CHECKING:
    from pydantic_ai import UserContent

    from zrb.context.any_context import AnyContext
    from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
    from zrb.llm.task.llm_task import LLMTask
    from zrb.llm.tool_call.ui_protocol import UIProtocol


class RunnerMixin:
    """Interactive + non-interactive session orchestration for LLMChatTask."""

    async def _run_non_interactive_session(
        self,
        ctx: "AnyContext",
        llm_task_core: "LLMTask",
        initial_message: Any,
        initial_conversation_name: str,
        initial_yolo: "bool | frozenset[str]",
        initial_attachments: "list[UserContent]",
    ) -> Any:
        # AsyncExitStack is handled by LLMTask._exec_action
        session_input = {
            "message": initial_message,
            "session": initial_conversation_name,
            "yolo": bool(initial_yolo),  # inner task uses dynamic_yolo; just pass bool
            "attachments": initial_attachments,
            "model": self._get_model(ctx),
        }
        shared_ctx = SharedContext(
            input=session_input,
            print_fn=ctx.shared_print,  # Use current task's print function
        )
        session = Session(shared_ctx)
        result = await llm_task_core.async_run(session)
        # Store conversation name in xcom for CLI to print at the end
        ctx.xcom["__conversation_name__"] = initial_conversation_name
        return result

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
        from zrb.llm.ui.base.ui import BaseUI

        # Note: AsyncExitStack is handled by LLMTask._exec_action
        # 1. Resolve UIs from factories
        resolved_uis: list["UIProtocol"] = list(self._uis)
        for factory in self._ui_factories:
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
            if isinstance(factory_ui, list):
                resolved_uis.extend(factory_ui)
            else:
                resolved_uis.append(factory_ui)

        # 2. Resolve UI attributes for default UI
        resolved_custom_model_names = get_attr(ctx, self._custom_model_names, []) or []
        if not isinstance(resolved_custom_model_names, list):
            resolved_custom_model_names = []
        ui_greeting = get_str_attr(ctx, self._ui_greeting, "", self._render_ui_greeting)
        ui_assistant_name = get_str_attr(
            ctx, self._ui_assistant_name, "", self._render_ui_assistant_name
        )
        ui_jargon = get_str_attr(ctx, self._ui_jargon, "", self._render_ui_jargon)
        ascii_art = get_str_attr(
            ctx, self._ui_ascii_art_name, "", self._render_ui_ascii_art_name
        )
        # Resolve show_ollama_models and show_pydantic_ai_models with CFG fallback
        effective_show_ollama_models = (
            CFG.LLM_SHOW_OLLAMA_MODELS
            if self._show_ollama_models is None
            else self._show_ollama_models
        )
        effective_show_pydantic_ai_models = (
            CFG.LLM_SHOW_PYDANTIC_AI_MODELS
            if self._show_pydantic_ai_models is None
            else self._show_pydantic_ai_models
        )

        # Resolve custom commands
        resolved_custom_commands: list[AnyCustomCommand] = []
        for cmd in self._custom_commands:
            if callable(cmd):
                res = cmd()
                if isinstance(res, list):
                    resolved_custom_commands.extend(res)
                else:
                    resolved_custom_commands.append(res)
            else:
                resolved_custom_commands.append(cmd)

        # 3. Determine the UI to use
        from zrb.llm.app.lexer import CLIStyleLexer
        from zrb.llm.ui.default.ui import UI
        from zrb.llm.ui.multi_ui import MultiUI

        ui: "UIProtocol | None" = None

        if resolved_uis and not self._include_default_ui:
            # Factory UIs only — skip the default CLI UI entirely
            if len(resolved_uis) == 1:
                ui = resolved_uis[0]
            else:
                ui = MultiUI(resolved_uis)
                if len(self._approval_channels) == 1:
                    ui.set_approval_channel(self._approval_channels[0])
                elif len(self._approval_channels) > 1:
                    from zrb.llm.approval import MultiplexApprovalChannel

                    ui.set_approval_channel(
                        MultiplexApprovalChannel(self._approval_channels)
                    )
        elif resolved_uis:
            # We have factory UIs - create default UI and combine them
            default_ui = UI(
                ctx=ctx,
                yolo_xcom_key=self._yolo_xcom_key,
                greeting=ui_greeting,
                assistant_name=ui_assistant_name,
                ascii_art=ascii_art,
                jargon=ui_jargon,
                output_lexer=CLIStyleLexer(),
                llm_task=llm_task_core,
                history_manager=history_manager,
                initial_message=initial_message,
                initial_attachments=initial_attachments,
                conversation_session_name=initial_conversation_name,
                is_yolo=initial_yolo,
                triggers=self._triggers,
                response_handlers=self._response_handlers,
                tool_policies=self._tool_policies,
                argument_formatters=self._argument_formatters,
                markdown_theme=self._markdown_theme,
                summarize_commands=ui_commands["summarize"],
                attach_commands=ui_commands["attach"],
                exit_commands=ui_commands["exit"],
                info_commands=ui_commands["info"],
                save_commands=ui_commands["save"],
                load_commands=ui_commands["load"],
                rewind_commands=ui_commands["rewind"],
                yolo_toggle_commands=ui_commands["yolo_toggle"],
                set_model_commands=ui_commands["set_model"],
                redirect_output_commands=ui_commands["redirect_output"],
                exec_commands=ui_commands["exec"],
                btw_commands=ui_commands["btw"],
                custom_commands=resolved_custom_commands,
                model=self._get_model(ctx),
                custom_model_names=resolved_custom_model_names,
                show_ollama_models=effective_show_ollama_models,
                show_pydantic_ai_models=effective_show_pydantic_ai_models,
                enable_rewind=enable_rewind,
                snapshot_dir=snapshot_dir,
            )
            # Add default UI first, then factory UIs
            all_uis = [default_ui] + resolved_uis
            if len(all_uis) == 1:
                ui = default_ui
            else:
                ui = MultiUI(all_uis)
                # Set up approval channel for MultiUI
                if len(self._approval_channels) == 1:
                    ui.set_approval_channel(self._approval_channels[0])
                elif len(self._approval_channels) > 1:
                    from zrb.llm.approval import MultiplexApprovalChannel

                    ui.set_approval_channel(
                        MultiplexApprovalChannel(self._approval_channels)
                    )
                # Set tool call handler so CLI mode has same formatters as standalone CLI
                ui.set_tool_call_handler(default_ui.tool_call_handler)
        else:
            # No factory UIs, use default UI
            ui = UI(
                ctx=ctx,
                yolo_xcom_key=self._yolo_xcom_key,
                greeting=ui_greeting,
                assistant_name=ui_assistant_name,
                ascii_art=ascii_art,
                jargon=ui_jargon,
                output_lexer=CLIStyleLexer(),
                llm_task=llm_task_core,
                history_manager=history_manager,
                initial_message=initial_message,
                initial_attachments=initial_attachments,
                conversation_session_name=initial_conversation_name,
                is_yolo=initial_yolo,
                triggers=self._triggers,
                response_handlers=self._response_handlers,
                tool_policies=self._tool_policies,
                argument_formatters=self._argument_formatters,
                markdown_theme=self._markdown_theme,
                summarize_commands=ui_commands["summarize"],
                attach_commands=ui_commands["attach"],
                exit_commands=ui_commands["exit"],
                info_commands=ui_commands["info"],
                save_commands=ui_commands["save"],
                load_commands=ui_commands["load"],
                rewind_commands=ui_commands["rewind"],
                yolo_toggle_commands=ui_commands["yolo_toggle"],
                set_model_commands=ui_commands["set_model"],
                redirect_output_commands=ui_commands["redirect_output"],
                exec_commands=ui_commands["exec"],
                btw_commands=ui_commands["btw"],
                custom_commands=resolved_custom_commands,
                model=self._get_model(ctx),
                custom_model_names=resolved_custom_model_names,
                show_ollama_models=effective_show_ollama_models,
                show_pydantic_ai_models=effective_show_pydantic_ai_models,
                enable_rewind=enable_rewind,
                snapshot_dir=snapshot_dir,
            )

        # 4. Load and display session history if session name is provided
        if initial_conversation_name:
            try:
                from zrb.llm.util.history_formatter import format_history_as_text

                history = history_manager.load(initial_conversation_name)
                if history:
                    history_text = format_history_as_text(history)
                    ui.append_to_output(history_text)
            except FileNotFoundError:
                # New session - no history file exists yet
                pass
            except Exception as e:
                CFG.LOGGER.warning(
                    f"Failed to load history for session {initial_conversation_name}: {e}"
                )

        # 5. Run the UI
        if ui is None:
            raise ValueError("No UI available")
        if isinstance(ui, BaseUI) or hasattr(ui, "run_async"):
            await ui.run_async()
        else:
            raise ValueError(f"UI {type(ui)} does not implement run_async")
        last_output = getattr(ui, "last_output", "")
        final_conversation_name = self._get_ui_conversation_name(
            ui, initial_conversation_name
        )
        # Print session name at the very end (after result is returned to caller)
        # Store it to be printed by the finally block in cli.py
        ctx.xcom["__conversation_name__"] = final_conversation_name
        return last_output
