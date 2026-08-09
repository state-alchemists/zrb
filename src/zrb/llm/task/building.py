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
- `_history_processors`, `_tool_confirmation`, `_approval_channel`
- `_history_manager`, `_permissions`, `_sandbox`, `_custom_model_names`
- `_model`, `_render_model`, `_model_settings`
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from zrb.attr.type import BoolAttr
from zrb.llm.factory_resolver import resolve_factory_items
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.manager import hook_manager as default_hook_manager
from zrb.llm.prompt.manager import PromptManager
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


class LLMTaskBuilding:
    """Post-construction configuration + agent/prompt assembly for LLMTask."""

    if TYPE_CHECKING:
        # Attributes supplied by the host class (BaseTask, or set in
        # LLMTask.__init__).
        # `name` is a property on BaseTask; declaring it as a variable here
        # would trip reportIncompatibleVariableOverride on the composed class.
        @property
        def name(self) -> str: ...

        _prompt_manager: PromptManager | None
        _uis: list[UIProtocol]
        _hook_manager: HookManager
        _llm_config: LLMConfig
        _tools: list[Tool | ToolFuncEither]
        _tool_factories: list[Callable[[AnyContext], Tool | ToolFuncEither]]
        _toolsets: list[AbstractToolset[None]]
        _toolset_factories: list[Callable[[AnyContext], AbstractToolset[None]]]
        _history_processors: list[HistoryProcessor]
        _tool_confirmation: AnyToolConfirmation
        _approval_channel: ApprovalChannel | None
        _history_manager: AnyHistoryManager | None
        _permissions: PermissionPolicyInput
        _sandbox: SandboxInput | BoolAttr
        _custom_model_names: StrListAttr | None
        _model: Any
        _render_model: bool
        _model_settings: Any

    @property
    def prompt_manager(self) -> PromptManager:
        """The `PromptManager` composing this task's system prompt.

        Raises:
            ValueError: If the task was built without one.
        """
        if self._prompt_manager is None:
            raise ValueError(f"Task {self.name} doesn't have prompt_manager")
        return self._prompt_manager

    def set_ui(self, ui: UIProtocol | None):
        """Replace every attached UI with `ui`, or detach all when None."""
        self._uis = [] if ui is None else [ui]

    def append_ui(self, ui: UIProtocol) -> None:
        """Attach one more UI, keeping those already attached.

        Every attached UI receives the same stream of events, which is how
        output is mirrored to a terminal and a web client at once.
        """
        self._uis.append(ui)

    @property
    def tool_confirmation(self) -> AnyToolConfirmation:
        """Policy deciding which tool calls need the user to approve them."""
        return self._tool_confirmation

    @tool_confirmation.setter
    def tool_confirmation(self, value: AnyToolConfirmation):
        """Replace the tool-confirmation policy."""
        self._tool_confirmation = value

    @property
    def approval_channel(self) -> ApprovalChannel | None:
        """Channel carrying approval requests to whoever answers them.

        None when the task runs unattended, in which case a tool call needing
        approval is denied rather than blocking.
        """
        return self._approval_channel

    @approval_channel.setter
    def approval_channel(self, value: ApprovalChannel | None):
        """Replace the approval channel."""
        self._approval_channel = value

    @property
    def history_manager(self) -> AnyHistoryManager | None:
        """Store that persists conversation history across runs.

        None keeps the conversation in memory only.
        """
        return self._history_manager

    @history_manager.setter
    def history_manager(self, value: AnyHistoryManager | None):
        """Replace the history manager."""
        self._history_manager = value

    @property
    def permissions(self) -> PermissionPolicyInput:
        """Policy bounding which files and commands the agent's tools may touch."""
        return self._permissions

    @permissions.setter
    def permissions(self, value: PermissionPolicyInput):
        """Replace the permission policy."""
        self._permissions = value

    @property
    def sandbox(self) -> SandboxInput | BoolAttr:
        """Whether, and how, tool calls run inside a sandbox.

        A bool or template toggles the default sandbox; a `SandboxInput`
        configures it.
        """
        return self._sandbox

    @sandbox.setter
    def sandbox(self, value: SandboxInput | BoolAttr):
        """Replace the sandbox configuration."""
        self._sandbox = value

    def append_hook_factory(self, *factory: Callable[[HookManager], None]):
        """Register one or more hook factories on this task's hook manager.

        Each factory is applied immediately, receiving the `HookManager` so it
        can call `manager.register(hook, events=[...])`.

        Isolation by default: a task starts on the shared global hook manager,
        but the first call here swaps in a fresh per-task `HookManager` so these
        hooks do not leak into other tasks. Pass `hook_manager=` at construction
        to opt into a specific one — an explicitly provided manager is never
        replaced.
        """
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
        """Extra model names offered by the model picker, beyond the detected ones."""
        return self._custom_model_names

    @custom_model_names.setter
    def custom_model_names(self, value: StrListAttr | None):
        """Replace the custom model-name list."""
        self._custom_model_names = value

    def append_toolset(self, *toolset: AbstractToolset):
        """Add pydantic-ai toolsets whose tools the agent may call.

        Use a toolset to attach a group of related tools at once, such as an
        MCP server's. For a single function, `append_tool` is simpler.
        """
        self._toolsets += list(toolset)

    def append_toolset_factory(
        self, *factory: Callable[[AnyContext], AbstractToolset[None]]
    ):
        """Add factories building toolsets per run, from the task context.

        Prefer this over `append_toolset` when the toolset depends on inputs or
        env vars: a factory is called at run time, so it sees resolved values.
        """
        self._toolset_factories += list(factory)

    def append_tool(self, *tool: Tool | ToolFuncEither):
        """Add tools the agent may call.

        Accepts a plain function or a pydantic-ai `Tool`. A plain function's
        name, type hints, and docstring become the tool schema the model sees,
        so both are worth writing carefully.
        """
        self._tools += list(tool)

    def append_tool_factory(
        self, *factory: Callable[[AnyContext], Tool | ToolFuncEither]
    ):
        """Add factories building tools per run, from the task context.

        Prefer this over `append_tool` when the tool needs to close over
        resolved inputs or env vars, which exist only once the task runs.
        """
        self._tool_factories += list(factory)

    def append_history_processor(self, *processor: HistoryProcessor):
        """Add processors that rewrite conversation history before each request.

        Processors run in registration order, each receiving the previous one's
        output. This is the seam summarization and trimming use to keep a long
        conversation inside the context window.
        """
        self._history_processors += list(processor)

    def get_all_tools(self, ctx: AnyContext) -> list[Tool | ToolFuncEither]:
        """Get all tools including those resolved from factories."""
        return resolve_factory_items(self._tools, self._tool_factories, ctx)

    def get_all_toolsets(self, ctx: AnyContext) -> list[AbstractToolset[None]]:
        """Get all toolsets including those resolved from factories."""
        return resolve_factory_items(self._toolsets, self._toolset_factories, ctx)

    def get_system_prompt(self, ctx: AnyContext) -> str:
        """Compose the full system prompt for this run.

        Returns the empty string when the task has no prompt manager.
        """
        if self._prompt_manager is None:
            return ""
        compose_prompt = self._prompt_manager.compose_prompt()
        return compose_prompt(ctx)

    def get_live_context(
        self, ctx: AnyContext, inject_journal_index: bool = False
    ) -> str:
        """Render the per-turn ``<live-context>`` block injected into the user
        turn. Empty string when there is no prompt manager (nothing to wire).

        ``inject_journal_index`` appends the journal index snapshot. Callers set
        it only when the index is absent from history, so it is paid once per
        context window and re-seeded after summarization drops it."""
        if self._prompt_manager is None:
            return ""
        return self._prompt_manager.create_live_context(
            ctx, inject_journal_index=inject_journal_index
        )

    async def get_live_context_async(
        self, ctx: AnyContext, inject_journal_index: bool = False
    ) -> str:
        """``get_live_context`` for async callers: git collection runs off-loop
        so the per-turn render cannot freeze the TUI's event loop."""
        if self._prompt_manager is None:
            return ""
        return await self._prompt_manager.create_live_context_async(
            ctx, inject_journal_index=inject_journal_index
        )

    def get_model_settings(self, ctx: AnyContext) -> ModelSettings | None:
        """The task's model settings, falling back to the LLM config's."""
        model_settings = self._model_settings
        rendered_model_settings = get_attr(ctx, model_settings, None)
        if rendered_model_settings is not None:
            return rendered_model_settings
        return self._llm_config.model_settings

    def get_model(self, ctx: AnyContext) -> str | Model:
        """The task's model, rendered against *ctx*, falling back to the config's.

        A blank render counts as unset, so an empty ``--model`` input does not
        shadow the configured model with an empty string.
        """
        model = self._model
        rendered_model = get_attr(ctx, model, None, auto_render=self._render_model)
        if isinstance(rendered_model, str) and rendered_model.strip() == "":
            rendered_model = None
        if rendered_model is not None:
            return rendered_model
        return self._llm_config.model
