"""`LLMChatTask` — the conversational task type that powers `zrb llm chat`.

Wires together: tools/skills/hooks resolution, UI factory selection (default
TUI, std-out, http, multi-UI), approval-channel orchestration, history
manager + snapshot lifecycle, and the inner `LLMTask` execution. Heavy.
Most of the behaviour is decomposed into:

  builder_mixin.py - construct the inner LLMTask (model, tools, prompts)
  runner_mixin.py  - resolve UIs/triggers/custom commands, run the loop

For the public API and authoring patterns, see:
  docs/task-types/llmchat-task.md
For the end-to-end request lifecycle (CLI -> LLMChatTask -> agent run -> UI),
see docs/advanced-topics/llm-chat-lifecycle.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncIterable, Callable, cast

from zrb.attr.type import BoolAttr, StrAttr, StrListAttr, fstring
from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.context.print_fn import PrintFn
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.input.bool_input import BoolInput
from zrb.input.str_input import StrInput
from zrb.llm.agent import AnyToolConfirmation
from zrb.llm.config.config import LLMConfig
from zrb.llm.config.config import llm_config as default_llm_config
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
from zrb.llm.factory_resolver import resolve_factory_items
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
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
from zrb.llm.prompt.manager import PromptManager
from zrb.llm.prompt.tool_guidance import ToolGuidance
from zrb.llm.summarizer import (
    create_summarizer_history_processor,
)
from zrb.llm.task.chat.builder_mixin import BuilderMixin
from zrb.llm.task.chat.runner_mixin import RunnerMixin
from zrb.llm.task.llm_task import LLMTask
from zrb.llm.tool_call import (
    ArgumentFormatter,
    ResponseHandler,
    ToolPolicy,
    replace_in_file_formatter,
    write_file_formatter,
)
from zrb.llm.util.attachment import get_attachments
from zrb.task.any_task import AnyTask
from zrb.task.base_task import BaseTask
from zrb.util.attr import get_attr, get_bool_attr, get_str_attr
from zrb.util.cli.style import stylize_highlight, stylize_muted
from zrb.util.string.name import get_random_name
from zrb.xcom.xcom import Xcom

if TYPE_CHECKING:
    from pydantic_ai import Tool, UserContent
    from pydantic_ai.capabilities import AbstractCapability
    from pydantic_ai.models import Model
    from pydantic_ai.settings import ModelSettings
    from pydantic_ai.tools import ToolFuncEither
    from pydantic_ai.toolsets import AbstractToolset
    from rich.theme import Theme

    from zrb.llm.agent.common import HistoryProcessor
    from zrb.llm.approval.approval_channel import ApprovalChannel
    from zrb.llm.permission import PermissionPolicyInput
    from zrb.llm.sandbox import SandboxInput
    from zrb.llm.tool_call.ui_protocol import UIProtocol


def parse_yolo_value(value: Any) -> "bool | frozenset[str]":
    """Parse a yolo input value into bool or frozenset of tool names.

    - bool True/False → returned as-is
    - "true"/"1"/"yes" → True (full yolo)
    - ""/"false"/"0"/"no" → False (no yolo)
    - "Write,Edit" → frozenset({"Write", "Edit"}) (selective yolo)
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (set, frozenset)):
        return frozenset(value)
    if not value:
        return False
    s = str(value).strip()
    if not s or s.lower() in ("false", "0", "no", "none"):
        return False
    if s.lower() in ("true", "1", "yes"):
        return True
    tools = frozenset(t.strip() for t in s.split(",") if t.strip())
    return tools if tools else False


class LLMChatTask(BuilderMixin, RunnerMixin, BaseTask):  # type: ignore[reportIncompatibleVariableOverride]

    def __init__(
        self,
        name: str,
        color: int | None = None,
        icon: str | None = None,
        description: str | None = None,
        cli_only: bool = False,
        input: list[AnyInput | None] | AnyInput | None = None,
        env: list[AnyEnv | None] | AnyEnv | None = None,
        system_prompt: Callable[[AnyContext], str | fstring | None] | str | None = None,
        render_system_prompt: bool = False,
        prompt_manager: PromptManager | None = None,
        active_skills: StrListAttr | None = None,
        render_active_skills: bool = True,
        tools: list[Tool | ToolFuncEither] | None = None,
        toolsets: list[AbstractToolset[None]] | None = None,
        tool_factories: (
            list[Callable[[AnyContext], Tool | ToolFuncEither]] | None
        ) = None,
        toolset_factories: (
            list[Callable[[AnyContext], AbstractToolset[None]]] | None
        ) = None,
        message: StrAttr | None = None,
        render_message: bool = True,
        attachment: (
            UserContent
            | list[UserContent]
            | Callable[[AnyContext], UserContent | list[UserContent]]
            | None
        ) = None,  # noqa
        history_processors: list[HistoryProcessor] | None = None,
        capabilities: "list[AbstractCapability[Any]] | None" = None,
        llm_config: LLMConfig | None = None,
        llm_limiter: LLMLimiter | None = None,
        model: (
            Callable[[AnyContext], Model | str | fstring | None] | Model | None
        ) = None,
        render_model: bool = True,
        model_settings: (
            ModelSettings | Callable[[AnyContext], ModelSettings] | None
        ) = None,
        custom_model_names: StrListAttr | None = None,
        conversation_name: StrAttr | None = None,
        render_conversation_name: bool = True,
        history_manager: AnyHistoryManager | None = None,
        tool_confirmation: AnyToolConfirmation = None,
        ui: UIProtocol | None = None,
        ui_factory: (
            Callable[
                [
                    AnyContext,
                    LLMTask,
                    AnyHistoryManager,
                    dict[str, list[str]],
                    Any,
                    str,
                    bool,
                    list[UserContent],
                ],
                UIProtocol,
            ]
            | None
        ) = None,
        approval_channel: ApprovalChannel | None = None,
        permissions: "PermissionPolicyInput" = None,
        sandbox: "SandboxInput" = None,
        yolo: BoolAttr = False,
        yolo_xcom_key: str = "yolo",
        ui_summarize_commands: list[str] | None = None,
        ui_attach_commands: list[str] | None = None,
        ui_exit_commands: list[str] | None = None,
        ui_info_commands: list[str] | None = None,
        ui_save_commands: list[str] | None = None,
        ui_load_commands: list[str] | None = None,
        ui_rewind_commands: list[str] | None = None,
        ui_redirect_output_commands: list[str] | None = None,
        ui_yolo_toggle_commands: list[str] | None = None,
        ui_set_model_commands: list[str] | None = None,
        ui_exec_commands: list[str] | None = None,
        ui_btw_commands: list[str] | None = None,
        ui_plan_commands: list[str] | None = None,
        ui_copy_commands: list[str] | None = None,
        custom_commands: (
            list[
                AnyCustomCommand
                | Callable[[], AnyCustomCommand | list[AnyCustomCommand]]
            ]
            | None
        ) = None,
        ui_greeting: StrAttr | None = None,
        render_ui_greeting: bool = True,
        ui_assistant_name: StrAttr | None = None,
        render_ui_assistant_name: bool = True,
        ui_jargon: StrAttr | None = None,
        render_ui_jargon: bool = True,
        ui_ascii_art: StrAttr | None = None,
        render_ui_ascii_art_name: bool = True,
        triggers: list[Callable[[], AsyncIterable[Any]]] | None = None,
        response_handlers: list[ResponseHandler] | None = None,
        tool_policies: list[ToolPolicy] | None = None,
        argument_formatters: list[ArgumentFormatter] | None = None,
        markdown_theme: "Theme | None" = None,
        enable_rewind: bool | None = None,
        snapshot_dir: StrAttr | None = None,
        include_default_ui: bool = True,
        interactive: BoolAttr = True,
        show_ollama_models: bool | None = None,
        show_pydantic_ai_models: bool | None = None,
        execute_condition: bool | str | Callable[[AnyContext], bool] = True,
        retries: int = 0,
        retry_period: float = 0,
        readiness_check: list[AnyTask] | AnyTask | None = None,
        readiness_check_delay: float = 0.5,
        readiness_check_period: float = 5,
        readiness_failure_threshold: int = 1,
        readiness_timeout: int = 60,
        monitor_readiness: bool = False,
        upstream: list[AnyTask] | AnyTask | None = None,
        fallback: list[AnyTask] | AnyTask | None = None,
        successor: list[AnyTask] | AnyTask | None = None,
        print_fn: PrintFn | None = None,
    ):
        super().__init__(
            name=name,
            color=color,
            icon=icon,
            description=description,
            cli_only=cli_only,
            input=input,
            env=env,
            execute_condition=execute_condition,
            retries=retries,
            retry_period=retry_period,
            readiness_check=readiness_check,
            readiness_check_delay=readiness_check_delay,
            readiness_check_period=readiness_check_period,
            readiness_failure_threshold=readiness_failure_threshold,
            readiness_timeout=readiness_timeout,
            monitor_readiness=monitor_readiness,
            upstream=upstream,
            fallback=fallback,
            successor=successor,
            print_fn=print_fn,
        )
        self._llm_config = default_llm_config if llm_config is None else llm_config
        self._llm_limiter = llm_limiter
        # Auto-convert system_prompt to prompt_manager if provided and prompt_manager not set
        if prompt_manager is None:
            prompt_manager = PromptManager(
                prompts=[system_prompt] if system_prompt else [],
                render=render_system_prompt,
                active_skills=active_skills,
                render_active_skills=render_active_skills,
                include_sections=[],
            )
        self._prompt_manager = prompt_manager
        self._system_prompt = system_prompt
        self._render_system_prompt = render_system_prompt
        self._active_skills = active_skills
        self._render_active_skills = render_active_skills
        self._tools = tools if tools is not None else []
        self._toolsets = toolsets if toolsets is not None else []
        # LLMChatTask-specific factories that resolve using parent context
        self._tool_factories = tool_factories if tool_factories is not None else []
        # Guidance factories are called when tools are resolved, to register
        # guidance for dynamically-named factory tools (e.g., RunZrbTask).
        self._tool_guidance_factories: list[Callable[[AnyContext], ToolGuidance]] = []
        # Tool-guidance section factories — produce model-aware Markdown
        # blocks inserted above the per-tool catalogue at compose time.
        self._tool_guidance_section_factories: list[
            Callable[[AnyContext, Any], str | None]
        ] = []
        # Store tool guidance until prompt_manager is available
        self._pending_tool_guidance: list[ToolGuidance] = []
        self._toolset_factories = (
            toolset_factories if toolset_factories is not None else []
        )
        self._hook_factories: list[Callable[[HookManager], None]] = []
        # Set per execution in _create_llm_task_core; the interactive teardown
        # fires the terminal SESSION_END on it.
        self._active_hook_manager: HookManager | None = None
        self._message = message
        self._render_message = render_message
        self._attachment = attachment
        self._history_processors = (
            history_processors if history_processors is not None else []
        )
        self._capabilities = capabilities if capabilities is not None else []
        self._model = model
        self._render_model = render_model
        self._model_settings = model_settings
        self._custom_model_names = custom_model_names
        self._conversation_name = conversation_name
        self._render_conversation_name = render_conversation_name
        self._history_manager = history_manager
        self._tool_confirmation = tool_confirmation
        self._uis: list["UIProtocol"] = []
        if ui is not None:
            self._uis.append(ui)
        self._ui_factories: list[Callable[..., "UIProtocol"]] = []
        if ui_factory is not None:
            self._ui_factories.append(ui_factory)
        self._approval_channels: list["ApprovalChannel"] = []
        if approval_channel is not None:
            self._approval_channels.append(approval_channel)
        self._permissions = permissions
        self._sandbox = sandbox
        self._yolo = yolo
        self._yolo_xcom_key = yolo_xcom_key
        self._ui_summarize_commands = (
            ui_summarize_commands if ui_summarize_commands is not None else []
        )
        self._ui_attach_commands = (
            ui_attach_commands if ui_attach_commands is not None else []
        )
        self._ui_exit_commands = (
            ui_exit_commands if ui_exit_commands is not None else []
        )
        self._ui_info_commands = (
            ui_info_commands if ui_info_commands is not None else []
        )
        self._ui_save_commands = (
            ui_save_commands if ui_save_commands is not None else []
        )
        self._ui_load_commands = (
            ui_load_commands if ui_load_commands is not None else []
        )
        self._ui_rewind_commands = (
            ui_rewind_commands if ui_rewind_commands is not None else []
        )
        self._ui_redirect_output_commands = (
            ui_redirect_output_commands
            if ui_redirect_output_commands is not None
            else []
        )
        self._ui_yolo_toggle_commands = (
            ui_yolo_toggle_commands if ui_yolo_toggle_commands is not None else []
        )
        self._ui_set_model_commands = (
            ui_set_model_commands if ui_set_model_commands is not None else []
        )
        self._ui_exec_commands = (
            ui_exec_commands if ui_exec_commands is not None else []
        )
        self._ui_btw_commands = ui_btw_commands if ui_btw_commands is not None else []
        self._ui_plan_commands = (
            ui_plan_commands if ui_plan_commands is not None else []
        )
        self._ui_copy_commands = (
            ui_copy_commands if ui_copy_commands is not None else []
        )
        self._custom_commands = custom_commands if custom_commands is not None else []
        self._ui_greeting = ui_greeting
        self._render_ui_greeting = render_ui_greeting
        self._ui_assistant_name = ui_assistant_name
        self._render_ui_assistant_name = render_ui_assistant_name
        self._ui_jargon = ui_jargon
        self._render_ui_jargon = render_ui_jargon
        self._ui_ascii_art_name = ui_ascii_art
        self._render_ui_ascii_art_name = render_ui_ascii_art_name
        self._triggers = triggers if triggers is not None else []
        self._response_handlers = (
            response_handlers if response_handlers is not None else []
        )
        self._tool_policies = tool_policies if tool_policies is not None else []
        self._argument_formatters = (
            argument_formatters if argument_formatters is not None else []
        ) + [
            replace_in_file_formatter,
            write_file_formatter,
        ]
        self._markdown_theme = markdown_theme
        self._enable_rewind = enable_rewind
        self._snapshot_dir = snapshot_dir
        self._include_default_ui = include_default_ui
        self._interactive = interactive
        self._show_ollama_models = show_ollama_models
        self._show_pydantic_ai_models = show_pydantic_ai_models

    def get_system_prompt(self, ctx: AnyContext) -> str:
        if self._prompt_manager is None:
            return ""
        compose_prompt = self._prompt_manager.compose_prompt()
        return compose_prompt(ctx)

    async def _exec_action(self, ctx: AnyContext) -> Any:
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
            + [create_summarizer_history_processor()],
            capabilities=capabilities,
            llm_config=self._llm_config,
            llm_limiter=self._llm_limiter,
            history_manager=history_manager,
            hook_manager=hook_manager,
            tool_confirmation=tool_confirmation,
            ui=cast("UIProtocol | None", ui),
            approval_channel=effective_approval_channel,
            permissions=self._permissions,
            sandbox=self._sandbox,
            message="{ctx.input.message}",
            conversation_name="{ctx.input.session}",
            yolo="{ctx.input.yolo}",
            dynamic_yolo=_should_skip_approval,
            attachment=lambda ctx: ctx.input.attachments,
            model=lambda ctx: ctx.input.get("model"),
            render_model=False,
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
