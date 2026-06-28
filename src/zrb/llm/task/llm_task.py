"""`LLMTask` — single-shot task that creates a pydantic-ai agent and runs it.

This module is decomposed into mixins, mirroring `chat/task.py`:

  builder_mixin.py  - post-construction config API (add/append/set), public
                      properties, and agent/prompt assembly (tools, system
                      prompt, model selection)
  history_mixin.py  - conversation/history resolution + error & cancellation
                      recovery

The host class keeps `__init__` plus the execution core — `_exec_action`,
`_exec_action_inner`, `_create_agent`, and `_handle_summarization`. Those own
the `run_agent` / `create_agent` / `summarize_history` call sites, which tests
patch at this module path (`zrb.llm.task.llm_task.*`), so they must stay here.
"""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING, Any, Callable, cast

from zrb.attr.type import BoolAttr, StrAttr, StrListAttr, fstring
from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.context.print_fn import PrintFn
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.llm.agent import AnyToolConfirmation, create_agent, run_agent
from zrb.llm.config.config import LLMConfig
from zrb.llm.config.config import llm_config as default_llm_config
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.config.limiter import llm_limiter as default_llm_limiter
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.manager import hook_manager as default_hook_manager
from zrb.llm.permission import (
    ALLOW,
    ASK,
    DENY,
    Capability,
    PermissionPolicyInput,
    get_effective_policy,
    resolve_policy,
)
from zrb.llm.prompt.manager import PromptManager
from zrb.llm.prompt.tool_guidance import ToolGuidance
from zrb.llm.sandbox import SandboxInput, coerce_sandbox
from zrb.llm.summarizer import (
    summarize_history,
)
from zrb.llm.task.builder_mixin import BuilderMixin
from zrb.llm.task.history_mixin import HistoryMixin
from zrb.llm.util.attachment import get_attachments
from zrb.task.any_task import AnyTask
from zrb.task.base_task import BaseTask
from zrb.util.attr import get_attr, get_bool_attr

if TYPE_CHECKING:
    from pydantic_ai import Tool, UserContent
    from pydantic_ai.capabilities import AbstractCapability
    from pydantic_ai.models import Model
    from pydantic_ai.settings import ModelSettings
    from pydantic_ai.tools import ToolFuncEither
    from pydantic_ai.toolsets import AbstractToolset

    from zrb.llm.agent.common import HistoryProcessor
    from zrb.llm.approval.approval_channel import ApprovalChannel
    from zrb.llm.tool_call.ui_protocol import UIProtocol


class LLMTask(BuilderMixin, HistoryMixin, BaseTask):  # type: ignore[reportIncompatibleVariableOverride]

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
        hook_manager: HookManager | None = None,
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
        dynamic_yolo: Callable[..., bool] | None = None,
        permissions: PermissionPolicyInput = None,
        sandbox: SandboxInput | BoolAttr = None,
        yolo: BoolAttr = False,
        ui: UIProtocol | None = None,
        approval_channel: ApprovalChannel | None = None,
        summarize_command: list[str] | None = None,
        execute_condition: bool | str | Callable[[AnyContext], bool] = True,
        retries: int = 2,
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
        self._llm_limiter = default_llm_limiter if llm_limiter is None else llm_limiter
        # Auto-convert system_prompt to prompt_manager if provided and prompt_manager not set
        if prompt_manager is None:
            prompt_manager = PromptManager(
                prompts=[system_prompt] if system_prompt else [],
                render=render_system_prompt,
                active_skills=active_skills,
                render_active_skills=render_active_skills,
                include_sections=[],
            )
        self._system_prompt = system_prompt
        self._render_system_prompt = render_system_prompt
        self._prompt_manager = prompt_manager
        self._hook_manager = (
            default_hook_manager if hook_manager is None else hook_manager
        )
        self._active_skills = active_skills
        self._render_active_skills = render_active_skills
        self._tools = tools if tools is not None else []
        self._toolsets = toolsets if toolsets is not None else []
        self._tool_factories = tool_factories if tool_factories is not None else []
        self._toolset_factories = (
            toolset_factories if toolset_factories is not None else []
        )
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
        self._uis: list[UIProtocol] = []
        if ui is not None:
            self._uis.append(ui)
        self._yolo = yolo
        self._ui_factories: list[Callable[..., UIProtocol]] = []
        self._dynamic_yolo = dynamic_yolo
        self._permissions = permissions
        self._sandbox = sandbox
        self._approval_channel = approval_channel
        self._summarize_command = (
            summarize_command if summarize_command is not None else []
        )
        # Guidance factories for dynamically-named tools (e.g., RunZrbTask).
        # Resolved per exec and applied to prompt_manager before composing the
        # system prompt.
        self._tool_guidance_factories: list[Callable[[AnyContext], ToolGuidance]] = []
        # Section factories for model-aware Tool Usage Guide intros (e.g.,
        # parallel-tool-call policy).
        self._tool_guidance_section_factories: list[
            Callable[[AnyContext, Any], "str | None"]
        ] = []

    @property
    def llm_config(self) -> LLMConfig:
        return self._llm_config

    @property
    def llm_limiter(self) -> LLMLimiter:
        return self._llm_limiter

    async def _exec_action(self, ctx: AnyContext) -> Any:
        async with AsyncExitStack() as stack:
            # Enter context for all toolsets that support it
            for toolset in self._get_all_toolsets(ctx):
                if hasattr(toolset, "__aenter__"):
                    await stack.enter_async_context(toolset)

            return await self._exec_action_inner(ctx)

    async def _exec_action_inner(self, ctx: AnyContext) -> Any:
        conversation_name = self._get_conversation_name(ctx)
        history_manager = self._get_history_manager(ctx)
        message_history = history_manager.load(conversation_name)
        user_message = cast(str, get_attr(ctx, self._message, "", self._render_message))
        user_attachments = get_attachments(ctx, self._attachment)

        if await self._handle_summarization(
            ctx, history_manager, conversation_name, user_message, message_history
        ):
            return "Conversation history compressed."

        # Resolve guidance/section factories into the prompt manager so the
        # composed system prompt reflects dynamically-named tools and any
        # model-aware Tool Usage Guide sections.
        self._resolve_tool_guidance_factories(ctx)

        # Compute system prompt once and reuse for both agent creation and run_agent.
        # This avoids rebuilding the prompt (including expensive system_context I/O)
        # a second time inside _create_agent.
        system_prompt = self.get_system_prompt(ctx)
        # Render the volatile per-turn state separately and inject it into the
        # user turn (not the system prompt) so the cacheable prefix stays
        # byte-stable. This call also performs per-turn ambient-state wiring
        # (session/interactive/worktree) — it must run every turn. The journal
        # index snapshot is seeded on the first turn only (empty history); each
        # later summarization re-seeds it at its own site (summarize_history), so
        # the index is always present without living in the cached system prompt.
        live_context = self.get_live_context(
            ctx, inject_journal_index=not message_history
        )
        agent = self._create_agent(ctx, system_prompt=system_prompt)
        effective_message, effective_attachments = self._get_effective_prompt(
            ctx, user_message, user_attachments, message_history
        )

        try:
            # Compute YOLO status for context propagation
            yolo_value = (
                self._dynamic_yolo()
                if callable(self._dynamic_yolo)
                else get_bool_attr(ctx, self._yolo, False)
            )
            # Resolve the permission policy from the explicit task param, else
            # global config. None → run_agent keeps legacy/inherited behavior.
            permission_policy = resolve_policy(
                self._permissions
                if self._permissions is not None
                else CFG.LLM_PERMISSIONS
            )
            # Resolve the sandbox policy from the explicit task param. None →
            # run_agent keeps inherited/ambient behavior (CFG fallback at the
            # enforcement sites — disabled unless the deployment opted in).
            sandbox_policy = coerce_sandbox(ctx, self._sandbox)
            CFG.LOGGER.debug("llm_task Calling run_agent with:")
            CFG.LOGGER.debug(f"  tool_confirmation: {self._tool_confirmation}")
            CFG.LOGGER.debug(f"  approval_channel: {self._approval_channel}")
            output, new_history = await run_agent(
                agent=agent,
                message=effective_message,
                message_history=message_history,
                limiter=self._llm_limiter,
                attachments=effective_attachments,
                print_fn=lambda *args, **kwargs: ctx.print(*args, **kwargs, plain=True),
                event_handler=None,  # Let run_agent create the event handler with proper status_fn
                tool_confirmation=self._tool_confirmation,
                hook_manager=self._hook_manager,
                ui=self._uis,
                yolo=yolo_value,
                approval_channel=self._approval_channel,
                system_prompt=system_prompt,
                live_context=live_context,
                permission_policy=permission_policy,
                sandbox_policy=sandbox_policy,
            )
        except asyncio.CancelledError as ce:
            partial_run = getattr(ce, "zrb_partial_run", None)
            self._save_cancelled_history(
                history_manager,
                conversation_name,
                message_history,
                user_message,
                partial_run=partial_run,
            )
            raise
        except Exception as e:
            partial_run = getattr(e, "zrb_partial_run", None)
            self._handle_run_error(
                ctx, history_manager, conversation_name, e, partial_run=partial_run
            )
            raise e

        history_manager.update(conversation_name, new_history)
        history_manager.save(conversation_name)
        ctx.log_debug(f"All messages: {new_history}")

        return self._post_process_output(output)

    async def _handle_summarization(
        self,
        ctx: AnyContext,
        history_manager: AnyHistoryManager,
        conversation_name: str,
        user_message: Any,
        message_history: list[Any],
    ) -> bool:
        if (
            isinstance(user_message, str)
            and user_message.strip() in self._summarize_command
        ):
            ctx.print("Compressing conversation history...", plain=True)
            new_history = await summarize_history(
                message_history,
                force=True,
                inject_journal_index=(
                    self._prompt_manager is not None
                    and "journal_mandate" in self._prompt_manager.active_sections
                ),
            )
            history_manager.update(conversation_name, new_history)
            history_manager.save(conversation_name)
            return True
        return False

    def _create_agent(self, ctx: AnyContext, system_prompt: str | None = None) -> Any:
        if self._dynamic_yolo is not None:
            should_skip_approval = self._dynamic_yolo
        else:
            # Default policy-aware callable (bare LLMTask without dynamic_yolo).
            # Follows the same precedence chain as chat/task.py check_yolo.
            # Caching the yolo value at closure-creation time is fine — bare
            # LLMTask yolo is a BoolAttr, not a live xcom like LLMChatTask.
            should_skip_approval_bool = get_bool_attr(ctx, self._yolo, False)

            def _should_skip_approval(tool_def=None):
                policy = get_effective_policy()
                if policy is not None:
                    tool_name = (
                        getattr(tool_def, "name", str(tool_def))
                        if tool_def is not None
                        else ""
                    )
                    result = policy.decide(tool_name, Capability.UNKNOWN, {})
                    if result == ALLOW:
                        return True
                    if result == DENY:
                        return True  # auto-approved (gate blocks at execution)
                    if result == ASK:
                        return False  # explicit policy ASK is a 'hard ask'
                return should_skip_approval_bool

            should_skip_approval = _should_skip_approval
        if system_prompt is None:
            system_prompt = self.get_system_prompt(ctx)
        ctx.log_debug(f"SYSTEM PROMPT: {system_prompt}")
        # Get all tools and toolsets including those from factories
        resolved_tools = self._get_all_tools(ctx)
        resolved_toolsets = self._get_all_toolsets(ctx)

        # Resolve model using llm_config
        base_model = self._get_model(ctx)
        final_model = self._llm_config.resolve_model(base_model)

        for ui in self._uis:
            if hasattr(ui, "model"):
                setattr(ui, "model", final_model)

        # Pass resolve_model=False: we already ran model_getter/model_renderer
        # above. Letting create_agent resolve again would double-fire those
        # callbacks on the already-resolved model.
        return create_agent(
            model=final_model,
            system_prompt=system_prompt,
            tools=resolved_tools,
            toolsets=resolved_toolsets,
            model_settings=self._get_model_settings(ctx),
            history_processors=self._history_processors,
            capabilities=self._capabilities,
            yolo=should_skip_approval,
            resolve_model=False,
        )
