"""`LLMTask` — single-shot task that creates a pydantic-ai agent and runs it.

This module is decomposed into parts, mirroring `chat/task.py`:

  building.py  - post-construction config API (add/append/set), public
                      properties, and agent/prompt assembly (tools, system
                      prompt, model selection)
  history.py  - conversation/history resolution + error & cancellation
                      recovery

The host class keeps `__init__` plus the execution core — `_exec_action`,
`_exec_action_inner`, `_create_agent`, and `_handle_summarization`. Those own
the `run_agent` / `create_agent` / `summarize_history` call sites, which tests
patch at this module path (`zrb.llm.task.llm_task.*`), so they must stay here.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING, Any, Callable, cast

from zrb.attr.type import BoolAttr, StrAttr, StrListAttr, fstring
from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.context.print_fn import PrintFn
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.llm.agent import AnyToolConfirmation, create_agent, run_agent
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
from zrb.llm.sandbox import SandboxInput, coerce_sandbox
from zrb.llm.summarizer import summarize_history
from zrb.llm.task.building import LLMTaskBuilding
from zrb.llm.task.history import LLMTaskHistory
from zrb.llm.task.history_config import HistoryConfig
from zrb.llm.task.shared_getters import apply_model_hooks
from zrb.llm.util.attachment import get_attachments
from zrb.task.any_task import AnyTask
from zrb.task.base.base_task import BaseTask
from zrb.util.attr import get_attr, get_bool_attr

if TYPE_CHECKING:
    from zrb.llm.agent.common import HistoryProcessor
    from zrb.llm.agent.types import (
        AbstractCapability,
        AbstractToolset,
        Model,
        ModelSettings,
        Tool,
        ToolFuncEither,
        UserContent,
    )
    from zrb.llm.approval.any_approval_channel import AnyApprovalChannel
    from zrb.llm.ui.any_ui import AnyUI


class LLMTask(BaseTask):

    def __init__(
        self,
        name: str,
        *,
        color: int | None = None,
        icon: str | None = None,
        description: str | None = None,
        cli_only: bool = False,
        input: Sequence[AnyInput | None] | AnyInput | None = None,
        env: Sequence[AnyEnv | None] | AnyEnv | None = None,
        system_prompt: Callable[[AnyContext], str | fstring | None] | str | None = None,
        render_system_prompt: bool = False,
        prompt_manager: PromptManager | None = None,
        hook_manager: HookManager | None = None,
        active_skills: StrListAttr | None = None,
        render_active_skills: bool = True,
        tools: list[Tool | ToolFuncEither] | None = None,
        toolsets: list[AbstractToolset[None]] | None = None,
        tool_factories: (
            list[
                Callable[
                    [AnyContext],
                    Tool | ToolFuncEither | list[Tool | ToolFuncEither],
                ]
            ]
            | None
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
        llm_limiter: LLMLimiter | None = None,
        model: (
            Callable[[AnyContext], Model | str | fstring | None] | Model | None
        ) = None,
        render_model: bool = True,
        model_settings: (
            ModelSettings | Callable[[AnyContext], ModelSettings] | None
        ) = None,
        model_getter: (
            "Callable[[str | Model | None], str | Model | None] | None"
        ) = None,
        model_renderer: (
            "Callable[[str | Model | None], str | Model | None] | None"
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
        ui: AnyUI | None = None,
        approval_channel: AnyApprovalChannel | None = None,
        summarize_commands: list[str] | None = None,
        execute_condition: bool | str | Callable[[AnyContext], bool] = True,
        retries: int = 2,
        retry_period: float = 0,
        readiness_check: Sequence[AnyTask] | AnyTask | None = None,
        readiness_check_delay: float = 0.5,
        readiness_check_period: float = 5,
        readiness_failure_threshold: int = 1,
        readiness_timeout: int = 60,
        monitor_readiness: bool = False,
        upstream: Sequence[AnyTask] | AnyTask | None = None,
        fallback: Sequence[AnyTask] | AnyTask | None = None,
        successor: Sequence[AnyTask] | AnyTask | None = None,
        print_fn: PrintFn | None = None,
    ):
        """Define a single-turn LLM task: one prompt in, one response out.

        Use `LLMChatTask` instead when you want an interactive conversation.

        A `render_x` flag controls whether `x` is treated as an f-string template
        rendered against the task context. Set it False to pass a literal value
        containing braces.

        Args:
            message: The user message to send. Usually a template referencing an
                input, such as `"{ctx.input.question}"`.
            render_message: Whether to render `message` as a template.
            attachment: Images or files to send alongside the message. A single
                item, a list, or a callable taking the context.
            system_prompt: System prompt text, or a callable taking the context.
                Overrides whatever `prompt_manager` would compose.
            render_system_prompt: Whether to render `system_prompt` as a template.
                Off by default, since prompts commonly contain braces.
            prompt_manager: `PromptManager` composing the system prompt from
                sections. Defaults to the shared one.
            active_skills: Names of skills to pre-activate for this task.
            render_active_skills: Whether to render `active_skills` as templates.
            model: The model to use, as a name or a pydantic-ai `Model`. Defaults
                to `CFG.LLM_MODEL`.
            render_model: Whether to render `model` as a template.
            model_settings: Provider settings such as temperature, or a callable
                taking the context.
            model_getter: Callable transforming the resolved base model into the
                active model (e.g. tier switching, A/B testing) — applied before
                `model_renderer`.
            model_renderer: Callable transforming the active model into the
                final pydantic-ai model (e.g. wrapping a tier name into a real
                model string).
            custom_model_names: Extra model names to offer beyond the detected
                ones.
            llm_limiter: Rate and token limiter. Defaults to the shared
                `llm_limiter`.
            capabilities: pydantic-ai capabilities to enable for the run.
            tools: Functions or `Tool`s the model may call.
            toolsets: Toolsets whose tools the model may call.
            tool_factories: Callables building tools per run from the context. Use
                these when a tool must close over resolved inputs.
            toolset_factories: Callables building toolsets per run from the
                context.
            tool_confirmation: Policy deciding which tool calls need approval.
            approval_channel: Channel carrying approval requests to whoever answers
                them. Without one, a call needing approval is denied rather than
                blocking.
            permissions: Policy bounding which files and commands tools may touch.
            sandbox: Whether, and how, tool calls run sandboxed.
            yolo: Skip tool confirmation. True for all tools, or a comma-separated
                string or set naming the tools to auto-approve.
            dynamic_yolo: Callable re-evaluating `yolo` per tool call, for a
                decision that depends on run-time state.
            conversation_name: Name the conversation is stored under.
            render_conversation_name: Whether to render `conversation_name` as a
                template.
            history_manager: Store persisting conversation history across runs.
                Without one, a default file-backed store under LLM_HISTORY_DIR
                is used.
            history_processors: Callables rewriting history before each request,
                run in order. This is the seam summarization uses.
            summarize_commands: Aliases for the summarize command exposed to any
                attached UI.
            hook_manager: `HookManager` supplying lifecycle hooks. Defaults to a
                task-local manager.
            ui: UI receiving streamed output and prompts.

        Every parameter `BaseTask` accepts is also accepted here and behaves
        identically; see `BaseTask` for those.
        """
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
        self._llm_limiter = default_llm_limiter if llm_limiter is None else llm_limiter
        if prompt_manager is None:
            prompt_manager = PromptManager(
                prompts=[system_prompt] if system_prompt else None,
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
        self._tools = tools or []
        self._toolsets = toolsets or []
        self._tool_factories = tool_factories or []
        self._toolset_factories = toolset_factories or []
        self._message = message
        self._render_message = render_message
        self._attachment = attachment
        self._history_processors = history_processors or []
        self._capabilities = capabilities or []
        self._model = model
        self._render_model = render_model
        self._model_settings = model_settings
        self._model_getter = model_getter
        self._model_renderer = model_renderer
        self._custom_model_names = custom_model_names
        self._conversation_name = conversation_name
        self._render_conversation_name = render_conversation_name
        self._history_manager = history_manager
        self._tool_confirmation = tool_confirmation
        self._uis: list[AnyUI] = []
        if ui is not None:
            self._uis.append(ui)
        self._yolo = yolo
        self._ui_factories: list[Callable[..., AnyUI]] = []
        self._dynamic_yolo = dynamic_yolo
        self._permissions = permissions
        self._sandbox = sandbox
        self._approval_channel = approval_channel
        self._summarize_commands = summarize_commands or []
        self._building = LLMTaskBuilding(self)
        self._history = LLMTaskHistory(self)

    # --- LLMTaskBuilding delegators ------------------------------------------

    @property
    def prompt_manager(self) -> PromptManager:
        """The `PromptManager` composing this task's system prompt.

        Raises:
            ValueError: If the task was built without one.
        """
        if self._prompt_manager is None:
            raise ValueError(f"Task {self.name} doesn't have prompt_manager")
        return self._prompt_manager

    @prompt_manager.setter
    def prompt_manager(self, value: PromptManager) -> None:
        """Replace the `PromptManager` composing this task's system prompt."""
        self._prompt_manager = value

    @property
    def tools(self) -> "list[Tool | ToolFuncEither]":
        """Tools this task's agent may call (excluding factory-resolved ones)."""
        return self._tools

    @tools.setter
    def tools(self, value: "list[Tool | ToolFuncEither]") -> None:
        """Replace the tool list wholesale."""
        self._tools = value

    @property
    def toolsets(self) -> "list[AbstractToolset[None]]":
        """Pydantic-ai toolsets this task's agent may call."""
        return self._toolsets

    @toolsets.setter
    def toolsets(self, value: "list[AbstractToolset[None]]") -> None:
        """Replace the toolset list wholesale (see `tools` setter)."""
        self._toolsets = value

    def set_ui(self, ui: "AnyUI | None") -> None:
        """Replace every attached UI with `ui`, or detach all when None."""
        self._building.set_ui(ui)

    def append_ui(self, ui: "AnyUI") -> None:
        """Attach one more UI, keeping those already attached."""
        self._building.append_ui(ui)

    def get_uis(self) -> "list[AnyUI]":
        """Return a copy of every currently attached UI."""
        return self._building.get_uis()

    @property
    def tool_confirmation(self) -> AnyToolConfirmation:
        """Policy deciding which tool calls need the user to approve them."""
        return self._tool_confirmation

    @tool_confirmation.setter
    def tool_confirmation(self, value: AnyToolConfirmation) -> None:
        """Replace the tool-confirmation policy."""
        self._tool_confirmation = value

    @property
    def approval_channel(self) -> "AnyApprovalChannel | None":
        """Channel carrying approval requests to whoever answers them."""
        return self._approval_channel

    @approval_channel.setter
    def approval_channel(self, value: "AnyApprovalChannel | None") -> None:
        """Replace the approval channel."""
        self._approval_channel = value

    @property
    def history_manager(self) -> AnyHistoryManager | None:
        """Store that persists conversation history across runs."""
        return self._history_manager

    @history_manager.setter
    def history_manager(self, value: AnyHistoryManager | None) -> None:
        """Replace the history manager."""
        self._history_manager = value

    @property
    def permissions(self) -> PermissionPolicyInput:
        """Policy bounding which files and commands the agent's tools may touch."""
        return self._permissions

    @permissions.setter
    def permissions(self, value: PermissionPolicyInput) -> None:
        """Replace the permission policy."""
        self._permissions = value

    @property
    def sandbox(self) -> "SandboxInput | BoolAttr":
        """Whether, and how, tool calls run inside a sandbox."""
        return self._sandbox

    @sandbox.setter
    def sandbox(self, value: "SandboxInput | BoolAttr") -> None:
        """Replace the sandbox configuration."""
        self._sandbox = value

    def append_hook_factory(self, *factory: Callable[[HookManager], None]) -> None:
        """Register one or more hook factories on this task's hook manager."""
        self._building.append_hook_factory(*factory)

    @property
    def custom_model_names(self) -> "StrListAttr | None":
        """Extra model names offered by the model picker, beyond the detected ones."""
        return self._custom_model_names

    @custom_model_names.setter
    def custom_model_names(self, value: "StrListAttr | None") -> None:
        """Replace the custom model-name list."""
        self._custom_model_names = value

    def append_toolset(self, *toolset: "AbstractToolset") -> None:
        """Add pydantic-ai toolsets whose tools the agent may call."""
        self._building.append_toolset(*toolset)

    def append_toolset_factory(
        self, *factory: "Callable[[AnyContext], AbstractToolset[None]]"
    ) -> None:
        """Add factories building toolsets per run, from the task context."""
        self._building.append_toolset_factory(*factory)

    def append_tool(self, *tool: "Tool | ToolFuncEither") -> None:
        """Add tools the agent may call."""
        self._building.append_tool(*tool)

    def append_tool_factory(
        self,
        *factory: "Callable[[AnyContext], Tool | ToolFuncEither | list[Tool | ToolFuncEither]]",
    ) -> None:
        """Add factories building tools per run, from the task context."""
        self._building.append_tool_factory(*factory)

    def append_history_processor(self, *processor: "HistoryProcessor") -> None:
        """Add processors that rewrite conversation history before each request."""
        self._building.append_history_processor(*processor)

    @property
    def hook_manager(self) -> HookManager:
        """The hook manager this task's lifecycle hooks run through."""
        return self._hook_manager

    @hook_manager.setter
    def hook_manager(self, value: HookManager) -> None:
        """Replace the hook manager."""
        self._hook_manager = value

    @property
    def uis(self) -> "list[AnyUI]":
        """Every currently attached UI (mutable in place, e.g. `append_ui`)."""
        return self._uis

    @uis.setter
    def uis(self, value: "list[AnyUI]") -> None:
        """Replace every attached UI."""
        self._uis = value

    @property
    def prompt_manager_attr(self) -> "PromptManager | None":
        """The raw prompt manager, or None when the task has none."""
        return self._prompt_manager

    @prompt_manager_attr.setter
    def prompt_manager_attr(self, value: "PromptManager | None") -> None:
        """Replace the raw prompt manager."""
        self._prompt_manager = value

    @property
    def tool_factories(self) -> "list[Callable[[AnyContext], Any]]":
        """Factories building tools per run, from the task context."""
        return self._tool_factories

    @tool_factories.setter
    def tool_factories(self, value: "list[Callable[[AnyContext], Any]]") -> None:
        """Replace the tool factories."""
        self._tool_factories = value

    @property
    def toolset_factories(
        self,
    ) -> "list[Callable[[AnyContext], AbstractToolset[None]]]":
        """Factories building toolsets per run, from the task context."""
        return self._toolset_factories

    @toolset_factories.setter
    def toolset_factories(
        self, value: "list[Callable[[AnyContext], AbstractToolset[None]]]"
    ) -> None:
        """Replace the toolset factories."""
        self._toolset_factories = value

    @property
    def history_processors(self) -> "list[HistoryProcessor]":
        """Processors rewriting conversation history before each request."""
        return self._history_processors

    @history_processors.setter
    def history_processors(self, value: "list[HistoryProcessor]") -> None:
        """Replace the history processors."""
        self._history_processors = value

    @property
    def model_attr(self) -> Any:
        """The raw model attribute, unrendered."""
        return self._model

    @property
    def render_model(self) -> bool:
        """Whether `model` is rendered as a template."""
        return self._render_model

    @property
    def model_settings_attr(self) -> "ModelSettings | None | Any":
        """The raw model-settings attribute, unrendered."""
        return self._model_settings

    def get_all_tools(self, ctx: AnyContext) -> "list[Tool | ToolFuncEither]":
        """Get all tools including those resolved from factories."""
        return self._building.get_all_tools(ctx)

    def get_all_toolsets(self, ctx: AnyContext) -> "list[AbstractToolset[None]]":
        """Get all toolsets including those resolved from factories."""
        return self._building.get_all_toolsets(ctx)

    def get_system_prompt(self, ctx: AnyContext) -> str:
        """Compose the full system prompt for this run."""
        return self._building.get_system_prompt(ctx)

    def get_live_context(
        self,
        ctx: AnyContext,
        inject_journal_index: bool = False,
        first_message: str | None = None,
    ) -> str:
        """Render the per-turn ``<live-context>`` block injected into the user turn."""
        return self._building.get_live_context(ctx, inject_journal_index, first_message)

    async def get_live_context_async(
        self,
        ctx: AnyContext,
        inject_journal_index: bool = False,
        first_message: str | None = None,
    ) -> str:
        """``get_live_context`` for async callers."""
        return await self._building.get_live_context_async(
            ctx, inject_journal_index, first_message
        )

    def get_model_settings(self, ctx: AnyContext) -> "ModelSettings | None":
        """The task's model settings, falling back to the LLM config's."""
        return self._building.get_model_settings(ctx)

    def get_model(self, ctx: AnyContext) -> "str | Model":
        """The task's model, rendered against *ctx*, falling back to the config's."""
        return self._building.get_model(ctx)

    # --- LLMTaskHistory delegators --------------------------------------------

    @property
    def conversation_name_attr(self) -> "StrAttr | None":
        """The raw conversation-name attribute, unrendered."""
        return self._conversation_name

    @property
    def render_conversation_name(self) -> bool:
        """Whether `conversation_name` is rendered as a template."""
        return self._render_conversation_name

    @property
    def history_config(self) -> HistoryConfig:
        """The history-manager/conversation-name knobs as one group — see
        `HistoryConfig`. Recomputed on each read (not cached at construction)
        so `history_manager`'s public setter stays immediately visible here,
        matching that property's own contract."""
        return HistoryConfig(
            history_manager=self._history_manager,
            conversation_name=self._conversation_name,
            render_conversation_name=self._render_conversation_name,
        )

    def get_history_manager(self, ctx: AnyContext) -> AnyHistoryManager:
        """The configured history manager, or a default file-backed one."""
        return self._history.get_history_manager(ctx)

    def get_conversation_name(self, ctx: AnyContext) -> str:
        """The configured conversation name, or a fresh random one when blank."""
        return self._history.get_conversation_name(ctx)

    def get_effective_prompt(
        self,
        ctx: AnyContext,
        user_message: str,
        user_attachments: "list[Any] | None",
        message_history: "list[Any]",
    ) -> "tuple[str, list[Any] | None]":
        """The message to send this attempt, plus the attachments to send with it."""
        return self._history.get_effective_prompt(
            ctx, user_message, user_attachments, message_history
        )

    def is_context_length_error(self, error: Exception) -> bool:
        """Return True when the error is a model context-length / prompt-too-long rejection."""
        return self._history.is_context_length_error(error)

    def handle_run_error(
        self,
        ctx: AnyContext,
        history_manager: AnyHistoryManager,
        conversation_name: str,
        error: Exception,
        partial_run: Any = None,
    ) -> None:
        """Persist what a failed run leaves behind, so the next retry sees it."""
        self._history.handle_run_error(
            ctx, history_manager, conversation_name, error, partial_run
        )

    def save_cancelled_history(
        self,
        history_manager: AnyHistoryManager,
        conversation_name: str,
        message_history: "list[Any]",
        user_message: Any,
        partial_run: Any = None,
    ) -> None:
        """Save partial history when a run is cancelled by the user (e.g. Escape)."""
        self._history.save_cancelled_history(
            history_manager,
            conversation_name,
            message_history,
            user_message,
            partial_run,
        )

    def post_process_output(self, output: Any) -> Any:
        """Strip terminal styling from a string result; pass anything else through."""
        return self._history.post_process_output(output)

    @property
    def model_getter(
        self,
    ) -> "Callable[[str | Model | None], str | Model | None] | None":
        """Callable transforming the resolved base model into the active
        model (e.g. tier switching, A/B testing) — applied before
        `model_renderer`."""
        return self._model_getter

    @model_getter.setter
    def model_getter(
        self, value: "Callable[[str | Model | None], str | Model | None] | None"
    ) -> None:
        """Replace the model-getter hook, or None to remove it."""
        if value is not None and not callable(value):
            raise TypeError(
                f"{self.name}.model_getter must be a callable or None, "
                f"got {type(value).__name__}."
            )
        self._model_getter = value

    @property
    def model_renderer(
        self,
    ) -> "Callable[[str | Model | None], str | Model | None] | None":
        """Callable transforming the active model into the final
        pydantic-ai model — applied after `model_getter`."""
        return self._model_renderer

    @model_renderer.setter
    def model_renderer(
        self, value: "Callable[[str | Model | None], str | Model | None] | None"
    ) -> None:
        """Replace the model-renderer hook, or None to remove it."""
        if value is not None and not callable(value):
            raise TypeError(
                f"{self.name}.model_renderer must be a callable or None, "
                f"got {type(value).__name__}."
            )
        self._model_renderer = value

    @property
    def llm_limiter(self) -> LLMLimiter:
        """Rate and token limiter throttling this task's requests."""
        return self._llm_limiter

    async def _exec_action(self, ctx: AnyContext) -> Any:
        # Resolve toolset factories exactly once. Resolving again inside
        # _create_agent would produce DIFFERENT instances: the batch entered on
        # this stack would never be used, the batch given to the agent would
        # never be entered, and factory side effects (e.g. MCP server spawn)
        # would run twice per turn.
        toolsets = self.get_all_toolsets(ctx)
        async with AsyncExitStack() as stack:
            for toolset in toolsets:
                if hasattr(toolset, "__aenter__"):
                    await stack.enter_async_context(toolset)

            return await self._exec_action_inner(ctx, toolsets=toolsets)

    async def _exec_action_inner(
        self, ctx: AnyContext, toolsets: "list[AbstractToolset[None]] | None" = None
    ) -> Any:
        conversation_name = self.get_conversation_name(ctx)
        history_manager = self.get_history_manager(ctx)
        # Offload: load deserializes + re-validates the whole conversation —
        # O(history) blocking work that would stall the TUI's event loop.
        message_history = await asyncio.to_thread(
            history_manager.load, conversation_name
        )
        user_message = cast(str, get_attr(ctx, self._message, "", self._render_message))
        user_attachments = get_attachments(ctx, self._attachment)

        if await self._handle_summarization(
            ctx, history_manager, conversation_name, user_message, message_history
        ):
            return "Conversation history compressed."

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
        live_context = await self.get_live_context_async(
            ctx, inject_journal_index=not message_history, first_message=user_message
        )
        agent = self._create_agent(ctx, system_prompt=system_prompt, toolsets=toolsets)
        effective_message, effective_attachments = self.get_effective_prompt(
            ctx, user_message, user_attachments, message_history
        )

        async def _checkpoint(snapshot: list[Any]) -> None:
            """Persist mid-turn progress so a crash/cancel can resume from it.

            Fired in the background at every safe tool-call-round-trip
            boundary (see `_build_event_stream_handler`) — never awaited by
            the run loop itself. `write_backup=False`: a full timestamped
            backup on every tool call would spam the history dir for no
            benefit; the end-of-turn save below still writes one.
            """
            history_manager.update(conversation_name, snapshot)
            await asyncio.to_thread(
                history_manager.save, conversation_name, write_backup=False
            )

        try:
            yolo_value = (
                self._dynamic_yolo()
                if callable(self._dynamic_yolo)
                else get_bool_attr(ctx, self._yolo, False)
            )
            # Resolve the permission policy from the explicit task param, else
            # global config. None → run_agent keeps the inherited policy.
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
                # A falsy task-level yolo must keep inheriting the ambient
                # context (run_agent treats None as inherit); an explicit
                # opt-out is available on run_agent/delegate directly.
                yolo=yolo_value or None,
                approval_channel=self._approval_channel,
                system_prompt=system_prompt,
                live_context=live_context,
                permission_policy=permission_policy,
                sandbox_policy=sandbox_policy,
                checkpoint_fn=_checkpoint,
                # Stable across this conversation's turns (same identity used
                # for history persistence above), so file_observation.py's
                # read-before-overwrite tracking survives from one turn to
                # the next rather than resetting every message.
                run_scope=conversation_name,
            )
        except asyncio.CancelledError as ce:
            partial_run = getattr(ce, "zrb_partial_run", None)
            self.save_cancelled_history(
                history_manager,
                conversation_name,
                message_history,
                user_message,
                partial_run=partial_run,
            )
            raise
        except Exception as e:
            partial_run = getattr(e, "zrb_partial_run", None)
            self.handle_run_error(
                ctx, history_manager, conversation_name, e, partial_run=partial_run
            )
            raise e

        history_manager.update(conversation_name, new_history)
        # Offload: save serializes, re-validates, and writes the whole
        # conversation (twice, with the backup) — it lands at the exact moment
        # the user expects the prompt back, so it must not block the loop.
        await asyncio.to_thread(history_manager.save, conversation_name)
        ctx.log_debug(f"All messages: {new_history}")

        return self.post_process_output(output)

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
            and user_message.strip() in self._summarize_commands
        ):
            ctx.print("Compressing conversation history...", plain=True)
            new_history = await summarize_history(message_history, force=True)
            history_manager.update(conversation_name, new_history)
            # Offloaded for the same reason as the main path: save serializes,
            # re-validates, and writes the whole conversation twice (with the
            # backup), and must not block the loop.
            await asyncio.to_thread(history_manager.save, conversation_name)
            return True
        return False

    def _create_agent(
        self,
        ctx: AnyContext,
        system_prompt: str | None = None,
        toolsets: "list[AbstractToolset[None]] | None" = None,
    ) -> Any:
        if self._dynamic_yolo is not None:
            should_skip_approval = self._dynamic_yolo
        else:
            # Default policy-aware callable (bare LLMTask without dynamic_yolo).
            # Follows the same precedence chain as chat/task.py's
            # _should_skip_approval.
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
        # Get all tools and toolsets including those from factories. Toolsets
        # may be pre-resolved by _exec_action (which entered their contexts) —
        # re-resolving here would hand the agent different, never-entered
        # instances.
        resolved_tools = self.get_all_tools(ctx)
        resolved_toolsets = (
            toolsets if toolsets is not None else self.get_all_toolsets(ctx)
        )

        base_model = self.get_model(ctx)
        final_model = apply_model_hooks(
            base_model, self._model_getter, self._model_renderer
        )

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
            model_settings=self.get_model_settings(ctx),
            history_processors=self._history_processors,
            capabilities=self._capabilities,
            yolo=should_skip_approval,
            resolve_model=False,
        )
