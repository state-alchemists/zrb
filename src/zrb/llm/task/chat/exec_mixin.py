"""Execution + resource methods for `LLMChatTask`.

Holds the runtime entrypoint (`_exec_action`), system-prompt composition, the
inner `LLMTask` construction (`_create_llm_task_core`), tool/toolset/UI-command
resolution, conversation-name helpers, model resolution, and the interactive
teardown that releases process-global resources at session end.

Kept separate from `task.py` (config-time `__init__`) and from
`builder_mixin.py` / `runner_mixin.py` because this mixin owns the
execution-time machinery that `BaseTask` invokes on the composed task.

Assumes the host class provides the `_*` attributes set in
`LLMChatTask.__init__`, plus `_apply_tool_guidance` (BuilderMixin) and the
session runners (RunnerMixin).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.env.any_env import AnyEnv
from zrb.input.bool_input import BoolInput
from zrb.input.str_input import StrInput
from zrb.llm.factory_resolver import resolve_factory_items
from zrb.llm.history_manager.file_history_manager import FileHistoryManager
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent
from zrb.llm.permission import (
    ALLOW,
    ASK,
    DENY,
    Capability,
    get_effective_policy,
    tool_capability,
)
from zrb.llm.sandbox import coerce_sandbox
from zrb.llm.summarizer import (
    create_summarizer_history_processor,
)
from zrb.llm.task.llm_task import LLMTask
from zrb.llm.util.attachment import get_attachments
from zrb.util.attr import get_attr, get_bool_attr, get_str_attr
from zrb.util.cli.style import stylize_highlight, stylize_muted
from zrb.util.string.name import get_random_name
from zrb.xcom.xcom import Xcom

if TYPE_CHECKING:
    from pydantic_ai import Tool
    from pydantic_ai.capabilities import AbstractCapability
    from pydantic_ai.models import Model
    from pydantic_ai.tools import ToolFuncEither
    from pydantic_ai.toolsets import AbstractToolset

    from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
    from zrb.llm.tool_call.ui_protocol import UIProtocol


class ExecMixin:
    """Execution + resource lifecycle for LLMChatTask."""

    if TYPE_CHECKING:
        # Attributes/methods provided by the composed LLMChatTask and its
        # sibling mixins. Declared here so pyright can resolve them when
        # ExecMixin is type-checked in isolation (same pattern as the UI
        # mixins, e.g. keybindings_mixin.py). Complex unions/callables are
        # annotated `Any` deliberately; the concrete types live on LLMChatTask.
        _ui_summarize_commands: list[str]
        _ui_attach_commands: list[str]
        _ui_exit_commands: list[str]
        _ui_info_commands: list[str]
        _ui_save_commands: list[str]
        _ui_load_commands: list[str]
        _ui_rewind_commands: list[str]
        _ui_redirect_output_commands: list[str]
        _ui_yolo_toggle_commands: list[str]
        _ui_set_model_commands: list[str]
        _ui_exec_commands: list[str]
        _ui_btw_commands: list[str]
        _ui_plan_commands: list[str]
        _ui_copy_commands: list[str]
        _ui_voice_commands: list[str]
        _render_system_prompt: bool
        _render_active_skills: bool
        _render_message: bool
        _render_model: bool
        _render_conversation_name: bool
        _yolo_xcom_key: str
        _active_skills: Any
        _approval_channels: Any
        _argument_formatters: Any
        _attachment: Any
        _capabilities: Any
        _conversation_name: Any
        _enable_rewind: Any
        _history_manager: Any
        _history_processors: Any
        _hook_factories: Any
        _interactive: Any
        _llm_config: Any
        _llm_limiter: Any
        _message: Any
        _model: Any
        _model_settings: Any
        _permissions: Any
        _prompt_manager: Any
        _response_handlers: Any
        _sandbox: Any
        _snapshot_dir: Any
        _system_prompt: Any
        _tool_confirmation: Any
        _tool_factories: Any
        _tool_guidance_factories: Any
        _tool_guidance_section_factories: Any
        _tool_policies: Any
        _tools: Any
        _toolset_factories: Any
        _toolsets: Any
        _uis: Any
        _yolo: Any
        _apply_tool_guidance: Any
        _run_interactive_session: Any
        _run_non_interactive_session: Any
        # From BaseTask (the concrete base LLMChatTask extends).
        name: str
        envs: Any

    def get_system_prompt(self, ctx: AnyContext) -> str:
        if self._prompt_manager is None:
            return ""
        compose_prompt = self._prompt_manager.compose_prompt()
        return compose_prompt(ctx)

    async def _exec_action(self, ctx: AnyContext) -> Any:
        # lazy: circular — task → exec_mixin (this file) → task.parse_yolo_value.
        from zrb.llm.task.chat.task import parse_yolo_value

        # 1. Resolve inputs/attributes
        initial_conversation_name = self._get_initial_conversation_name(ctx)
        raw_yolo = get_attr(ctx, self._yolo, "", True)
        initial_yolo = parse_yolo_value(raw_yolo)
        if self._yolo_xcom_key not in ctx.xcom:
            ctx.xcom[self._yolo_xcom_key] = Xcom()
        ctx.xcom[self._yolo_xcom_key].set(initial_yolo)

        initial_message = get_attr(ctx, self._message, "", self._render_message)
        initial_attachments = get_attachments(ctx, self._attachment)
        interactive = get_bool_attr(ctx, self._interactive, True)
        history_manager = (
            FileHistoryManager(history_dir=CFG.LLM_HISTORY_DIR)
            if self._history_manager is None
            else self._history_manager
        )

        # 2. Resolve rewind settings
        effective_enable_rewind = (
            CFG.LLM_ENABLE_REWIND
            if self._enable_rewind is None
            else self._enable_rewind
        )
        effective_snapshot_dir = get_str_attr(
            ctx, self._snapshot_dir, CFG.LLM_SNAPSHOT_DIR, True
        )

        # 3. Resolve UI Commands
        ui_commands = self._get_ui_commands()

        # 4. Resolve tools/toolsets from factories using parent context
        # LLMChatTask factories use the parent (LLMChatTask) context
        resolved_tools = self._get_all_tools(ctx)
        resolved_toolsets = self._get_all_toolsets(ctx)

        # 4a. Auto-wire resolved tool names to the prompt manager so that
        # tool guidance is filtered to only the tools actually registered.
        # Also wire the resolved model so the system_context section can
        # surface model-specific capability notes (e.g. lack of parallel
        # tool-call support). Re-set on every exec — `/model` switches
        # update ctx.input.model, which flows through _get_model(ctx).
        if self._prompt_manager is not None:
            tool_names: set[str] = set()
            for t in resolved_tools:
                name = getattr(t, "name", None) or getattr(t, "__name__", None)
                if name:
                    tool_names.add(name)
            self._prompt_manager.tool_names = tool_names or None
            self._prompt_manager.model = self._get_model(ctx)

        # 4b. Apply pending tool guidance added via add_tool_guidance()
        self._apply_tool_guidance()

        # 4c. Register guidance for dynamically-named factory tools.
        if self._prompt_manager is not None:
            for guidance_factory in self._tool_guidance_factories:
                guidance = guidance_factory(ctx)
                self._prompt_manager.add_tool_guidance(
                    group=guidance.group_name,
                    name=guidance.tool_name,
                    use_when=guidance.when_to_use,
                    key_rule=guidance.key_rule,
                )

        # 4d. Resolve model-aware Tool Usage Guide intro sections.
        if self._prompt_manager is not None:
            resolved_model = self._get_model(ctx)
            sections: list[str] = []
            for section_factory in self._tool_guidance_section_factories:
                rendered = section_factory(ctx, resolved_model)
                if rendered:
                    sections.append(rendered)
            self._prompt_manager.tool_guidance_sections = sections

        # 5. Create core LLM task
        llm_task_core = self._create_llm_task_core(
            ctx,
            ui_commands["summarize"],
            history_manager,
            interactive,
            resolved_tools,
            resolved_toolsets,
            self._capabilities,
        )

        # 6. Run Interactive or Non-Interactive
        # Note: AsyncExitStack for toolsets is handled by LLMTask._exec_action
        if not interactive:
            return await self._run_non_interactive_session(
                ctx=ctx,
                llm_task_core=llm_task_core,
                initial_message=initial_message,
                initial_conversation_name=initial_conversation_name,
                initial_yolo=initial_yolo,
                initial_attachments=initial_attachments,
            )

        try:
            return await self._run_interactive_session(
                ctx=ctx,
                llm_task_core=llm_task_core,
                history_manager=history_manager,
                ui_commands=ui_commands,
                initial_message=initial_message,
                initial_conversation_name=initial_conversation_name,
                initial_yolo=initial_yolo,
                initial_attachments=initial_attachments,
                enable_rewind=effective_enable_rewind,
                snapshot_dir=effective_snapshot_dir,
            )
        finally:
            await self._teardown_interactive_resources()

    async def _teardown_interactive_resources(self) -> None:
        """Release process-global resources when an interactive chat ends.

        Runs on normal exit, ``/exit``, EOF, or Ctrl+C (the ``finally`` fires on
        ``KeyboardInterrupt``). Stops LSP language-server subprocesses gracefully
        while the event loop is still alive — the ``atexit`` backstops only run
        once the loop is gone, when graceful async shutdown is no longer possible.

        Gated to the interactive session on purpose: the non-interactive path is
        reused per-message by the web/SSE runner, where tearing servers down
        would restart them on every message. Each step is guarded so teardown
        never raises; a second ``KeyboardInterrupt`` still propagates.
        """
        # Terminal SESSION_END: the interactive chat session is ending (normal
        # exit, /exit, EOF, or Ctrl+C). Claude Code fires SessionEnd once per
        # session, not per turn — run_agent fires only STOP per turn. Guarded so
        # a misbehaving hook never blocks resource teardown.
        #
        # `source` is the Claude-compatible matcher field for SessionEnd. This
        # single teardown point cannot distinguish the exit cause (normal /
        # /exit / EOF / Ctrl+C all funnel through the same `finally`) without
        # threading the reason through the chat loop, so we report the Claude
        # catch-all "other"; finer values (logout / prompt_input_exit) are a
        # follow-up. `reason` stays in event_data for the CLAUDE_* env vars.
        if self._active_hook_manager is not None:
            try:
                await self._active_hook_manager.execute_hooks(
                    HookEvent.SESSION_END,
                    {"reason": "exit"},
                    source="other",
                )
            except Exception:
                CFG.LOGGER.debug("SESSION_END hook raised at teardown", exc_info=True)

        # lazy: circular — chat task → lsp manager → server → (back to llm); and
        # avoids paying the import on the non-interactive/web path.
        try:
            from zrb.llm.lsp.manager.manager import lsp_manager

            await lsp_manager.shutdown_all()
        except Exception:
            pass
        # lazy: only needed at session end; keeps the hook import off hot paths.
        try:
            from zrb.llm.hook.executor import shutdown_hook_executor

            shutdown_hook_executor(wait=False)
        except Exception:
            pass

    def _get_all_tools(self, ctx: AnyContext) -> list[Tool | ToolFuncEither]:
        """Get all tools including those resolved from factories using parent context."""
        return resolve_factory_items(self._tools, self._tool_factories, ctx)

    def _get_all_toolsets(self, ctx: AnyContext) -> list[AbstractToolset[None]]:
        """Get all toolsets including those resolved from factories using parent context."""
        return resolve_factory_items(self._toolsets, self._toolset_factories, ctx)

    def _get_ui_commands(self) -> dict[str, list[str]]:
        """Resolve all UI commands from attributes or CFG defaults."""
        return {
            "summarize": (
                self._ui_summarize_commands
                if self._ui_summarize_commands
                else CFG.LLM_UI_COMMAND_SUMMARIZE
            ),
            "attach": (
                self._ui_attach_commands
                if self._ui_attach_commands
                else CFG.LLM_UI_COMMAND_ATTACH
            ),
            "exit": (
                self._ui_exit_commands
                if self._ui_exit_commands
                else CFG.LLM_UI_COMMAND_EXIT
            ),
            "info": (
                self._ui_info_commands
                if self._ui_info_commands
                else CFG.LLM_UI_COMMAND_INFO
            ),
            "save": (
                self._ui_save_commands
                if self._ui_save_commands
                else CFG.LLM_UI_COMMAND_SAVE
            ),
            "load": (
                self._ui_load_commands
                if self._ui_load_commands
                else CFG.LLM_UI_COMMAND_LOAD
            ),
            "rewind": (
                self._ui_rewind_commands
                if self._ui_rewind_commands
                else CFG.LLM_UI_COMMAND_REWIND
            ),
            "yolo_toggle": (
                self._ui_yolo_toggle_commands
                if self._ui_yolo_toggle_commands
                else CFG.LLM_UI_COMMAND_YOLO_TOGGLE
            ),
            "set_model": (
                self._ui_set_model_commands
                if self._ui_set_model_commands
                else CFG.LLM_UI_COMMAND_SET_MODEL
            ),
            "redirect_output": (
                self._ui_redirect_output_commands
                if self._ui_redirect_output_commands
                else CFG.LLM_UI_COMMAND_REDIRECT_OUTPUT
            ),
            "exec": (
                self._ui_exec_commands
                if self._ui_exec_commands
                else CFG.LLM_UI_COMMAND_EXEC
            ),
            "btw": (
                self._ui_btw_commands
                if self._ui_btw_commands
                else CFG.LLM_UI_COMMAND_BTW
            ),
            "plan": (
                self._ui_plan_commands
                if self._ui_plan_commands
                else CFG.LLM_UI_COMMAND_PLAN_TOGGLE
            ),
            "copy": (
                self._ui_copy_commands
                if self._ui_copy_commands
                else CFG.LLM_UI_COMMAND_COPY
            ),
            "voice": (
                self._ui_voice_commands
                if self._ui_voice_commands
                else CFG.LLM_UI_COMMAND_VOICE
            ),
        }

    def _create_llm_task_core(
        self,
        ctx: AnyContext,
        summarize_commands: list[str],
        history_manager: AnyHistoryManager,
        interactive: bool,
        resolved_tools: list[Tool | ToolFuncEither],
        resolved_toolsets: list[AbstractToolset[None]],
        capabilities: "list[AbstractCapability[Any]]",
    ) -> LLMTask:
        """Create the inner LLMTask that handles the actual processing."""
        # lazy: zrb.llm.ui.* and zrb.llm.tool_call.handler sit downstream of
        # llm_task; hoisting these to module-top creates a circular import.
        from zrb.llm.tool_call.handler import ToolCallHandler

        # lazy: zrb internal (heavy via transitive / circular)
        from zrb.llm.ui.std_ui import StdUI

        # Determine the tool confirmation and ui to use
        tool_confirmation = self._tool_confirmation
        ui = (
            self._uis if self._uis else None
        )  # Use programmatically set UIs if provided

        if interactive:
            # Interactive mode: Let the UI handle everything
            tool_confirmation = None
            ui = None  # Interactive mode uses its own UI system
        elif (
            self._tool_policies or self._response_handlers or self._argument_formatters
        ):
            # Non-interactive with policies/handlers/formatters: Use ToolCallHandler
            if not ui:
                ui = StdUI()
            tool_confirmation = ToolCallHandler(
                tool_policies=self._tool_policies,
                argument_formatters=self._argument_formatters,
                response_handlers=self._response_handlers,
            )
        else:
            # Non-interactive without policies: Use UI for approval
            if not ui:
                ui = StdUI()
            # tool_confirmation = None (let UI handle it via approval_channel)

        # Capability lookup for the resolved tool surface, used only when a
        # permission policy is in force (keyed by the LLM-visible tool name).
        cap_by_name = {
            (getattr(t, "name", None) or getattr(t, "__name__", "")): tool_capability(t)
            for t in resolved_tools
        }

        def _should_skip_approval(tool_def=None):
            # Approval precedence chain:
            #   perm_policy: allow→auto-approve, deny→auto-approve (gate blocks),
            #                ask→defer to tool_policy cascade
            #   tool_policy: handled in _resolve_approval (deferred_calls.py)
            #   yolo:        handled in _resolve_approval (deferred_calls.py)
            policy = get_effective_policy()
            if policy is not None:
                tool_name = (
                    getattr(tool_def, "name", str(tool_def))
                    if tool_def is not None
                    else ""
                )
                cap = cap_by_name.get(tool_name, Capability.UNKNOWN)
                result = policy.decide(tool_name, cap, {})
                if result is not None:
                    if result == ALLOW:
                        return True  # unconditional auto-approve
                    if result == DENY:
                        return True  # auto-approved (gate blocks at execution)
                    if result == ASK:
                        return False  # explicit policy ASK is a 'hard ask'
                # fallback to YOLO only if policy has no matching rule
            if self._yolo_xcom_key not in ctx.xcom:
                return False
            yolo_value = ctx.xcom[self._yolo_xcom_key].get(False)
            if isinstance(yolo_value, bool):
                return yolo_value
            if isinstance(yolo_value, frozenset):
                if tool_def is None:
                    return False
                tool_name = getattr(tool_def, "name", str(tool_def))
                return tool_name in yolo_value
            return False

        # Create MultiplexApprovalChannel if multiple channels
        effective_approval_channel = None
        if len(self._approval_channels) == 1:
            effective_approval_channel = self._approval_channels[0]
        elif len(self._approval_channels) > 1:
            # lazy: same circular reason as the imports earlier in this class.
            from zrb.llm.approval import MultiplexApprovalChannel

            effective_approval_channel = MultiplexApprovalChannel(
                self._approval_channels
            )

        CFG.LOGGER.debug("llm_chat_task _create_llm_task_core:")
        CFG.LOGGER.debug(f"  tool_confirmation: {tool_confirmation}")
        CFG.LOGGER.debug(f"  effective_approval_channel: {effective_approval_channel}")
        CFG.LOGGER.debug(f"  _approval_channels: {self._approval_channels}")

        # Create a fresh HookManager for this task execution
        hook_manager = HookManager()
        # Apply all hook factories
        for factory in self._hook_factories:
            factory(hook_manager)
        # Hold a reference so the interactive teardown can fire the terminal
        # SESSION_END on this exact manager (run_agent fires per-turn STOP, not
        # SESSION_END — SESSION_END is once-per-session, like Claude Code).
        self._active_hook_manager = hook_manager

        # Resolve sandbox against the outer (LLMChatTask) context before passing
        # to the inner LLMTask, whose own context does not carry a "sandbox" input
        # (see _run_non_interactive_session / _run_interactive_session).
        resolved_sandbox = coerce_sandbox(ctx, self._sandbox)

        # Pass resolved tools/toolsets to LLMTask (no factories needed since already resolved)
        return LLMTask(
            name=f"{self.name}-process",
            input=[
                StrInput("message", "Message"),
                StrInput("session", "Conversation Session"),
                BoolInput("yolo", "YOLO Mode"),
                StrInput("attachments", "Attachments"),
                StrInput("model", "Model"),
            ],
            env=cast(list[AnyEnv | None], self.envs),
            system_prompt=self._system_prompt,
            render_system_prompt=self._render_system_prompt,
            prompt_manager=self._prompt_manager,
            active_skills=self._active_skills,
            render_active_skills=self._render_active_skills,
            tools=resolved_tools,
            toolsets=resolved_toolsets,
            # No factories passed - tools/toolsets already resolved with parent context
            history_processors=self._history_processors
            + [
                create_summarizer_history_processor(
                    inject_journal_index=(
                        self._prompt_manager is not None
                        and "journal_mandate" in self._prompt_manager.active_sections
                    )
                )
            ],
            capabilities=capabilities,
            llm_config=self._llm_config,
            llm_limiter=self._llm_limiter,
            history_manager=history_manager,
            hook_manager=hook_manager,
            tool_confirmation=tool_confirmation,
            ui=cast("UIProtocol | None", ui),
            approval_channel=effective_approval_channel,
            permissions=self._permissions,
            sandbox=resolved_sandbox,
            message="{ctx.input.message}",
            conversation_name="{ctx.input.session}",
            yolo="{ctx.input.yolo}",
            dynamic_yolo=_should_skip_approval,
            attachment=lambda ctx: ctx.input.attachments,
            model=lambda ctx: ctx.input.get("model"),
            render_model=False,
            # Without this, LLMChatTask(model_settings=...) is accepted but
            # silently ignored: the inner task falls back to llm_config's.
            model_settings=self._model_settings,
            summarize_command=summarize_commands,
        )

    def _print_conversation_name(self, ctx: AnyContext, conversation_name: str):
        stylized_label = stylize_muted("Session")
        stylized_conversation_name = stylize_highlight(conversation_name)
        ctx.print(
            stylize_muted(f"{stylized_label}: {stylized_conversation_name}"), plain=True
        )

    def _get_initial_conversation_name(self, ctx: AnyContext) -> str:
        conversation_name = str(
            get_attr(ctx, self._conversation_name, "", self._render_conversation_name)
        )
        if conversation_name.strip() == "":
            conversation_name = get_random_name()
        return conversation_name

    def _get_ui_conversation_name(
        self, ui: "UIProtocol", initial_conversation_name: str
    ) -> str:
        """Get the current conversation name from UI or fallback to initial name."""
        # lazy: circular — see imports at top of class.
        from zrb.llm.ui.base.ui import BaseUI

        if isinstance(ui, BaseUI):
            return ui.conversation_session_name
        return getattr(ui, "conversation_session_name", initial_conversation_name)

    def _get_model(self, ctx: AnyContext) -> str | Model:
        model = self._model
        rendered_model = get_attr(ctx, model, None, auto_render=self._render_model)
        if isinstance(rendered_model, str) and rendered_model.strip() == "":
            rendered_model = None
        if rendered_model is not None:
            return rendered_model
        return self._llm_config.model
