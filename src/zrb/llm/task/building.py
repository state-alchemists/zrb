"""Builder API and agent/prompt assembly for `LLMTask`.

State is read through the owner on every access, never cached, because most
of it has a public setter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.manager import hook_manager as default_hook_manager
from zrb.llm.prompt.manager import PromptManager
from zrb.llm.task.shared_getters import (
    resolve_all_tools,
    resolve_all_toolsets,
    resolve_model,
    resolve_system_prompt,
)
from zrb.util.attr import get_attr

if TYPE_CHECKING:
    from zrb.attr.type import BoolAttr, StrListAttr
    from zrb.context.any_context import AnyContext
    from zrb.llm.agent import AnyToolConfirmation
    from zrb.llm.agent.common import HistoryProcessor
    from zrb.llm.agent.types import (
        AbstractToolset,
        Model,
        ModelSettings,
        Tool,
        ToolFuncEither,
    )
    from zrb.llm.approval.any_approval_channel import AnyApprovalChannel
    from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
    from zrb.llm.permission import PermissionPolicyInput
    from zrb.llm.sandbox import SandboxInput
    from zrb.llm.task.llm_task import LLMTask
    from zrb.llm.ui.any_ui import AnyUI


class LLMTaskBuilding:
    """Post-construction configuration + agent/prompt assembly for LLMTask."""

    def __init__(self, llm_task: "LLMTask") -> None:
        self._llm_task = llm_task

    @property
    def prompt_manager(self) -> PromptManager:
        """The `PromptManager` composing this task's system prompt.

        Raises:
            ValueError: If the task was built without one.
        """
        if self._llm_task.prompt_manager_attr is None:
            raise ValueError(f"Task {self._llm_task.name} doesn't have prompt_manager")
        return self._llm_task.prompt_manager_attr

    @prompt_manager.setter
    def prompt_manager(self, value: PromptManager) -> None:
        """Replace the `PromptManager`, e.g. on the TUI's `/load` persona swap."""
        self._llm_task.prompt_manager_attr = value

    @property
    def tools(self) -> list["Tool | ToolFuncEither"]:
        """Tools this task's agent may call (excluding factory-resolved ones)."""
        return self._llm_task.tools

    @tools.setter
    def tools(self, value: list["Tool | ToolFuncEither"]) -> None:
        """Replace the tool list wholesale, e.g. on a persona swap."""
        self._llm_task.tools = value

    @property
    def toolsets(self) -> list["AbstractToolset[None]"]:
        """Pydantic-ai toolsets this task's agent may call."""
        return self._llm_task.toolsets

    @toolsets.setter
    def toolsets(self, value: list["AbstractToolset[None]"]) -> None:
        """Replace the toolset list wholesale (see `tools` setter)."""
        self._llm_task.toolsets = value

    def set_ui(self, ui: AnyUI | None):
        """Replace every attached UI with `ui`, or detach all when None."""
        self._llm_task.uis = [] if ui is None else [ui]

    def append_ui(self, ui: AnyUI) -> None:
        """Attach one more UI; every attached UI receives the same event stream."""
        self._llm_task.uis.append(ui)

    def get_uis(self) -> list[AnyUI]:
        """Return a copy of every currently attached UI."""
        return list(self._llm_task.uis)

    @property
    def tool_confirmation(self) -> AnyToolConfirmation:
        """Policy deciding which tool calls need the user to approve them."""
        return self._llm_task.tool_confirmation

    @tool_confirmation.setter
    def tool_confirmation(self, value: AnyToolConfirmation):
        """Replace the tool-confirmation policy."""
        self._llm_task.tool_confirmation = value

    @property
    def approval_channel(self) -> AnyApprovalChannel | None:
        """Channel carrying approval requests; None denies calls needing approval."""
        return self._llm_task.approval_channel

    @approval_channel.setter
    def approval_channel(self, value: AnyApprovalChannel | None):
        """Replace the approval channel."""
        self._llm_task.approval_channel = value

    @property
    def history_manager(self) -> AnyHistoryManager | None:
        """History store; None falls back to a file-backed one under LLM_HISTORY_DIR."""
        return self._llm_task.history_manager

    @history_manager.setter
    def history_manager(self, value: AnyHistoryManager | None):
        """Replace the history manager."""
        self._llm_task.history_manager = value

    @property
    def permissions(self) -> PermissionPolicyInput:
        """Policy bounding which files and commands the agent's tools may touch."""
        return self._llm_task.permissions

    @permissions.setter
    def permissions(self, value: PermissionPolicyInput):
        """Replace the permission policy."""
        self._llm_task.permissions = value

    @property
    def sandbox(self) -> SandboxInput | BoolAttr:
        """Whether, and how, tool calls run inside a sandbox."""
        return self._llm_task.sandbox

    @sandbox.setter
    def sandbox(self, value: SandboxInput | BoolAttr):
        """Replace the sandbox configuration."""
        self._llm_task.sandbox = value

    def append_hook_factory(self, *factory: Callable[[HookManager], None]):
        """Apply hook factories to this task's hook manager immediately.

        If the task is still on the global manager, a fresh per-task one is
        swapped in first so these hooks do not leak into other tasks. An
        explicitly provided `hook_manager=` is never replaced.
        """
        for f in factory:
            self._ensure_task_local_hook_manager()
            f(self._llm_task.hook_manager)

    def _ensure_task_local_hook_manager(self) -> None:
        if self._llm_task.hook_manager is default_hook_manager:
            self._llm_task.hook_manager = HookManager()

    @property
    def custom_model_names(self) -> StrListAttr | None:
        """Extra model names offered by the model picker, beyond the detected ones."""
        return self._llm_task.custom_model_names

    @custom_model_names.setter
    def custom_model_names(self, value: StrListAttr | None):
        """Replace the custom model-name list."""
        self._llm_task.custom_model_names = value

    def append_toolset(self, *toolset: AbstractToolset):
        """Add pydantic-ai toolsets (e.g. an MCP server's) whose tools the agent may call."""
        self._llm_task.toolsets += list(toolset)

    def append_toolset_factory(
        self, *factory: Callable[[AnyContext], AbstractToolset[None]]
    ):
        """Add factories building toolsets per run, from the resolved task context."""
        self._llm_task.toolset_factories += list(factory)

    def append_tool(self, *tool: Tool | ToolFuncEither):
        """Add tools the agent may call: plain functions or pydantic-ai `Tool`s.

        A function's name, type hints and docstring become the tool schema.
        """
        self._llm_task.tools += list(tool)

    def append_tool_factory(
        self,
        *factory: "Callable[[AnyContext], Tool | ToolFuncEither | list[Tool | ToolFuncEither]]",
    ):
        """Add factories building tools per run, from the resolved task context."""
        self._llm_task.tool_factories += list(factory)

    def append_history_processor(self, *processor: HistoryProcessor):
        """Add processors that rewrite history before each request, run in order."""
        self._llm_task.history_processors += list(processor)

    def get_all_tools(self, ctx: AnyContext) -> list[Tool | ToolFuncEither]:
        """Get all tools including those resolved from factories."""
        return resolve_all_tools(
            ctx, self._llm_task.tools, self._llm_task.tool_factories
        )

    def get_all_toolsets(self, ctx: AnyContext) -> list[AbstractToolset[None]]:
        """Get all toolsets including those resolved from factories."""
        return resolve_all_toolsets(
            ctx, self._llm_task.toolsets, self._llm_task.toolset_factories
        )

    def get_system_prompt(self, ctx: AnyContext) -> str:
        """Compose the full system prompt for this run.

        Returns the empty string when the task has no prompt manager.
        """
        return resolve_system_prompt(ctx, self._llm_task.prompt_manager_attr)

    def get_live_context(
        self,
        ctx: AnyContext,
        inject_journal_index: bool = False,
        first_message: str | None = None,
    ) -> str:
        """Render the per-turn ``<live-context>`` block, or "" without a prompt manager.

        ``inject_journal_index`` appends the journal index snapshot; callers set
        it only when the index is absent from history. ``first_message`` feeds
        the journal's first-turn auto-search.
        """
        if self._llm_task.prompt_manager_attr is None:
            return ""
        return self._llm_task.prompt_manager_attr.create_live_context(
            ctx,
            inject_journal_index=inject_journal_index,
            first_message=first_message,
        )

    async def get_live_context_async(
        self,
        ctx: AnyContext,
        inject_journal_index: bool = False,
        first_message: str | None = None,
    ) -> str:
        """``get_live_context`` with git collection off-loop, for async callers."""
        if self._llm_task.prompt_manager_attr is None:
            return ""
        return await self._llm_task.prompt_manager_attr.create_live_context_async(
            ctx,
            inject_journal_index=inject_journal_index,
            first_message=first_message,
        )

    def get_model_settings(self, ctx: AnyContext) -> ModelSettings | None:
        """The task's model settings, or None (pydantic-ai's own defaults apply)."""
        return get_attr(ctx, self._llm_task.model_settings_attr, None)

    def get_model(self, ctx: AnyContext) -> str | Model:
        """The task's model, rendered against *ctx*, falling back to `CFG.LLM_MODEL`."""
        return resolve_model(ctx, self._llm_task.model_attr)
