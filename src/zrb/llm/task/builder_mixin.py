"""Builder API for `LLMTask`.

All `set_*`, `add_*`, `append_*` methods that configure the task
post-construction live here, plus the related public properties and the
agent/prompt assembly helpers (resolving tools/toolsets, composing the system
prompt, and selecting the model). This keeps `llm_task.py` focused on the
`__init__` constructor and the execution orchestration (`_exec_action`,
`_exec_action_inner`, `_create_agent`, `_handle_summarization`) — the methods
that own the `run_agent` / `create_agent` / `summarize_history` call sites.

State assumed to exist on the host class (set in `LLMTask.__init__`):
- `_prompt_manager`, `_uis`, `_hook_manager`, `_llm_config`
- `_tools`, `_tool_factories`, `_toolsets`, `_toolset_factories`
- `_tool_guidance_factories`, `_tool_guidance_section_factories`
- `_history_processors`, `_tool_confirmation`, `_approval_channel`
- `_history_manager`, `_permissions`, `_sandbox`, `_custom_model_names`
- `_model`, `_render_model`, `_model_settings`
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from zrb.llm.factory_resolver import resolve_factory_items
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.manager import hook_manager as default_hook_manager
from zrb.llm.prompt.manager import PromptManager
from zrb.llm.prompt.tool_guidance import ToolGuidance
from zrb.util.attr import get_attr

if TYPE_CHECKING:
    from pydantic_ai import Tool
    from pydantic_ai.models import Model
    from pydantic_ai.settings import ModelSettings
    from pydantic_ai.tools import ToolFuncEither
    from pydantic_ai.toolsets import AbstractToolset

    from zrb.attr.type import StrListAttr
    from zrb.context.any_context import AnyContext
    from zrb.llm.agent import AnyToolConfirmation
    from zrb.llm.agent.common import HistoryProcessor
    from zrb.llm.approval.approval_channel import ApprovalChannel
    from zrb.llm.config.config import LLMConfig
    from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
    from zrb.llm.permission import PermissionPolicyInput
    from zrb.llm.sandbox import SandboxInput
    from zrb.llm.tool_call.ui_protocol import UIProtocol


class BuilderMixin:
    """Post-construction configuration + agent/prompt assembly for LLMTask."""

    if TYPE_CHECKING:
        # Attributes supplied by the host class (BaseTask, or set in
        # LLMTask.__init__).
        name: str  # BaseTask
        _prompt_manager: PromptManager | None
        _uis: list[UIProtocol]
        _hook_manager: HookManager
        _llm_config: LLMConfig
        _tools: list[Tool | ToolFuncEither]
        _tool_factories: list[Callable[[AnyContext], Tool | ToolFuncEither]]
        _toolsets: list[AbstractToolset[None]]
        _toolset_factories: list[Callable[[AnyContext], AbstractToolset[None]]]
        _tool_guidance_factories: list[Callable[[AnyContext], ToolGuidance]]
        _tool_guidance_section_factories: list[Callable[[AnyContext, Any], str | None]]
        _history_processors: list[HistoryProcessor]
        _tool_confirmation: AnyToolConfirmation
        _approval_channel: ApprovalChannel | None
        _history_manager: AnyHistoryManager | None
        _permissions: PermissionPolicyInput
        _sandbox: SandboxInput
        _custom_model_names: StrListAttr | None
        _model: Any
        _render_model: bool
        _model_settings: Any

    @property
    def prompt_manager(self) -> PromptManager:
        if self._prompt_manager is None:
            raise ValueError(f"Task {self.name} doesn't have prompt_manager")
        return self._prompt_manager

    def set_ui(self, ui: UIProtocol | None):
        self._uis = [] if ui is None else [ui]

    def append_ui(self, ui: UIProtocol) -> None:
        self._uis.append(ui)

    @property
    def tool_confirmation(self) -> AnyToolConfirmation:
        return self._tool_confirmation

    @tool_confirmation.setter
    def tool_confirmation(self, value: AnyToolConfirmation):
        self._tool_confirmation = value

    @property
    def approval_channel(self) -> ApprovalChannel | None:
        return self._approval_channel

    @approval_channel.setter
    def approval_channel(self, value: ApprovalChannel | None):
        self._approval_channel = value

    @property
    def history_manager(self) -> AnyHistoryManager | None:
        return self._history_manager

    @history_manager.setter
    def history_manager(self, value: AnyHistoryManager | None):
        self._history_manager = value

    @property
    def permissions(self) -> PermissionPolicyInput:
        return self._permissions

    @permissions.setter
    def permissions(self, value: PermissionPolicyInput):
        self._permissions = value

    @property
    def sandbox(self) -> SandboxInput:
        return self._sandbox

    @sandbox.setter
    def sandbox(self, value: SandboxInput):
        self._sandbox = value

    def add_hook_factory(self, *factory: Callable[[HookManager], None]):
        """Register one or more hook factories on this task's hook manager.

        Each factory receives the ``HookManager`` and registers hooks on it (it
        is applied immediately — the factory typically calls
        ``manager.register(hook, events=[...])``). Mirrors
        ``LLMChatTask.add_hook_factory``.

        Isolation by default: a task starts on the shared global hook manager,
        but the first ``add_hook_factory`` call swaps in a fresh per-task
        ``HookManager`` so these hooks do not leak into other tasks. To opt into
        the global manager (or any specific one) instead, pass ``hook_manager=``
        at construction — an explicitly provided manager is never replaced.
        """
        self.append_hook_factory(*factory)

    def append_hook_factory(self, *factory: Callable[[HookManager], None]):
        for f in factory:
            self._ensure_task_local_hook_manager()
            f(self._hook_manager)

    def _ensure_task_local_hook_manager(self) -> None:
        # Swap the shared global default for a fresh per-task manager on first
        # registration, so task-level hooks stay isolated. A manager passed
        # explicitly at construction is left untouched.
        if self._hook_manager is default_hook_manager:
            self._hook_manager = HookManager()

    @property
    def custom_model_names(self) -> StrListAttr | None:
        return self._custom_model_names

    @custom_model_names.setter
    def custom_model_names(self, value: StrListAttr | None):
        self._custom_model_names = value

    def add_toolset(self, *toolset: AbstractToolset):
        self.append_toolset(*toolset)

    def append_toolset(self, *toolset: AbstractToolset):
        self._toolsets += list(toolset)

    def add_toolset_factory(
        self, *factory: Callable[[AnyContext], AbstractToolset[None]]
    ):
        self.append_toolset_factory(*factory)

    def append_toolset_factory(
        self, *factory: Callable[[AnyContext], AbstractToolset[None]]
    ):
        self._toolset_factories += list(factory)

    def add_tool(self, *tool: Tool | ToolFuncEither):
        self.append_tool(*tool)

    def append_tool(self, *tool: Tool | ToolFuncEither):
        self._tools += list(tool)

    def add_tool_factory(self, *factory: Callable[[AnyContext], Tool | ToolFuncEither]):
        self.append_tool_factory(*factory)

    def append_tool_factory(
        self, *factory: Callable[[AnyContext], Tool | ToolFuncEither]
    ):
        self._tool_factories += list(factory)

    def add_tool_guidance(self, *guidance: ToolGuidance):
        self.append_tool_guidance(*guidance)

    def append_tool_guidance(self, *guidance: ToolGuidance):
        """Add tool guidance entries directly to the prompt manager."""
        if self._prompt_manager is None:
            return
        for g in guidance:
            self._prompt_manager.add_tool_guidance(
                group=g.group_name,
                name=g.tool_name,
                use_when=g.when_to_use,
                key_rule=g.key_rule,
            )

    def add_tool_guidance_factory(self, *factory: Callable[[AnyContext], ToolGuidance]):
        self.append_tool_guidance_factory(*factory)

    def append_tool_guidance_factory(
        self, *factory: Callable[[AnyContext], ToolGuidance]
    ):
        """Register guidance for dynamically-named factory tools.

        Each factory is called per exec and returns a single ``ToolGuidance``
        that gets added to ``prompt_manager`` before the system prompt is
        composed.
        """
        self._tool_guidance_factories += list(factory)

    def add_tool_guidance_section_factory(
        self, *factory: Callable[[AnyContext, Any], "str | None"]
    ):
        self.append_tool_guidance_section_factory(*factory)

    def append_tool_guidance_section_factory(
        self, *factory: Callable[[AnyContext, Any], "str | None"]
    ):
        """Register a factory that renders a model-aware Tool Usage Guide section.

        Each factory is called per exec with ``(ctx, resolved_model)`` and
        returns a Markdown block (typically starting with ``## Heading``) or
        ``None``/empty string to skip injection.
        """
        self._tool_guidance_section_factories += list(factory)

    def _resolve_tool_guidance_factories(self, ctx: AnyContext) -> None:
        """Resolve guidance + section factories into ``_prompt_manager``.

        Called once per exec before ``get_system_prompt``.
        """
        if self._prompt_manager is None:
            return
        for guidance_factory in self._tool_guidance_factories:
            guidance = guidance_factory(ctx)
            self._prompt_manager.add_tool_guidance(
                group=guidance.group_name,
                name=guidance.tool_name,
                use_when=guidance.when_to_use,
                key_rule=guidance.key_rule,
            )
        resolved_model = self._get_model(ctx)
        sections: list[str] = []
        for section_factory in self._tool_guidance_section_factories:
            rendered = section_factory(ctx, resolved_model)
            if rendered:
                sections.append(rendered)
        self._prompt_manager.tool_guidance_sections = sections

    def add_history_processor(self, *processor: HistoryProcessor):
        self.append_history_processor(*processor)

    def append_history_processor(self, *processor: HistoryProcessor):
        self._history_processors += list(processor)

    def _get_all_tools(self, ctx: AnyContext) -> list[Tool | ToolFuncEither]:
        """Get all tools including those resolved from factories."""
        return resolve_factory_items(self._tools, self._tool_factories, ctx)

    def _get_all_toolsets(self, ctx: AnyContext) -> list[AbstractToolset[None]]:
        """Get all toolsets including those resolved from factories."""
        return resolve_factory_items(self._toolsets, self._toolset_factories, ctx)

    def get_system_prompt(self, ctx: AnyContext) -> str:
        if self._prompt_manager is None:
            return ""
        compose_prompt = self._prompt_manager.compose_prompt()
        return compose_prompt(ctx)

    def get_live_context(self, ctx: AnyContext) -> str:
        """Render the per-turn ``<live-context>`` block injected into the user
        turn. Empty string when there is no prompt manager (nothing to wire)."""
        if self._prompt_manager is None:
            return ""
        return self._prompt_manager.create_live_context(ctx)

    def _get_model_settings(self, ctx: AnyContext) -> ModelSettings | None:
        model_settings = self._model_settings
        rendered_model_settings = get_attr(ctx, model_settings, None)
        if rendered_model_settings is not None:
            return rendered_model_settings
        return self._llm_config.model_settings

    def _get_model(self, ctx: AnyContext) -> str | Model:
        model = self._model
        rendered_model = get_attr(ctx, model, None, auto_render=self._render_model)
        if isinstance(rendered_model, str) and rendered_model.strip() == "":
            rendered_model = None
        if rendered_model is not None:
            return rendered_model
        return self._llm_config.model
