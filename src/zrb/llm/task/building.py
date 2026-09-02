"""Builder API for `LLMTask`.

All `set_*`, `add_*`, `append_*` methods that configure the task
post-construction live here, plus the related public properties and the
agent/prompt assembly helpers (resolving tools/toolsets, composing the system
prompt, and selecting the model). This keeps `llm_task.py` focused on the
`__init__` constructor and the execution orchestration (`_exec_action`,
`_exec_action_inner`, `_create_agent`, `_handle_summarization`) — the methods
that own the `run_agent` / `create_agent` / `summarize_history` call sites.

Composed into `LLMTask` as `self._building` rather than inherited: keeps
`LLMTask` in `self._llm_task` and reads/writes its state through that
reference (not a value cached here at construction time), since almost every
attribute here has a public setter (`task.tools = ...`,
`task.history_manager = ...`, ...) that must be visible immediately from
this collaborator and from `LLMTask` itself alike.
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
    from zrb.llm.approval.approval_channel import ApprovalChannel
    from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
    from zrb.llm.permission import PermissionPolicyInput
    from zrb.llm.sandbox import SandboxInput
    from zrb.llm.task.llm_task import LLMTask
    from zrb.llm.tool_call.ui_protocol import UIProtocol


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
        """Replace the `PromptManager` composing this task's system prompt.

        Used to swap a running task's persona wholesale — e.g. the CLI TUI's
        `/load` on a delegated sub-agent session rebuilding a fresh, isolated
        `PromptManager` from that sub-agent's own resolved system prompt
        (Item 4, Phase D), mirroring the fresh `LLMChatTask` the web resume
        path builds via `SubAgentManager.create_llm_chat_task`.
        """
        self._llm_task.prompt_manager_attr = value

    @property
    def tools(self) -> list["Tool | ToolFuncEither"]:
        """Tools this task's agent may call (excluding factory-resolved ones)."""
        return self._llm_task.tools

    @tools.setter
    def tools(self, value: list["Tool | ToolFuncEither"]) -> None:
        """Replace the tool list wholesale.

        `append_tool` only grows the list — this is the reset a persona swap
        needs, so the previous persona's tools don't linger alongside the new
        one's.
        """
        self._llm_task.tools = value

    @property
    def toolsets(self) -> list["AbstractToolset[None]"]:
        """Pydantic-ai toolsets this task's agent may call."""
        return self._llm_task.toolsets

    @toolsets.setter
    def toolsets(self, value: list["AbstractToolset[None]"]) -> None:
        """Replace the toolset list wholesale (see `tools` setter)."""
        self._llm_task.toolsets = value

    def set_ui(self, ui: UIProtocol | None):
        """Replace every attached UI with `ui`, or detach all when None."""
        self._llm_task.uis = [] if ui is None else [ui]

    def append_ui(self, ui: UIProtocol) -> None:
        """Attach one more UI, keeping those already attached.

        Every attached UI receives the same stream of events, which is how
        output is mirrored to a terminal and a web client at once.
        """
        self._llm_task.uis.append(ui)

    def get_uis(self) -> list[UIProtocol]:
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
    def approval_channel(self) -> ApprovalChannel | None:
        """Channel carrying approval requests to whoever answers them.

        None when the task runs unattended, in which case a tool call needing
        approval is denied rather than blocking.
        """
        return self._llm_task.approval_channel

    @approval_channel.setter
    def approval_channel(self, value: ApprovalChannel | None):
        """Replace the approval channel."""
        self._llm_task.approval_channel = value

    @property
    def history_manager(self) -> AnyHistoryManager | None:
        """Store that persists conversation history across runs.

        None falls back to a default file-backed store under LLM_HISTORY_DIR.
        """
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
        """Whether, and how, tool calls run inside a sandbox.

        A bool or template toggles the default sandbox; a `SandboxInput`
        configures it.
        """
        return self._llm_task.sandbox

    @sandbox.setter
    def sandbox(self, value: SandboxInput | BoolAttr):
        """Replace the sandbox configuration."""
        self._llm_task.sandbox = value

    def append_hook_factory(self, *factory: Callable[[HookManager], None]):
        """Register one or more hook factories on this task's hook manager.

        Each factory is applied immediately, receiving the `HookManager` so it
        can call `manager.add_hook(hook, events=[...])`.

        Isolation by default: a task starts on the shared global hook manager,
        but the first call here swaps in a fresh per-task `HookManager` so these
        hooks do not leak into other tasks. Pass `hook_manager=` at construction
        to opt into a specific one — an explicitly provided manager is never
        replaced.
        """
        for f in factory:
            self._ensure_task_local_hook_manager()
            f(self._llm_task.hook_manager)

    def _ensure_task_local_hook_manager(self) -> None:
        # Swap the shared global default for a fresh per-task manager on first
        # registration, so task-level hooks stay isolated. A manager passed
        # explicitly at construction is left untouched.
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
        """Add pydantic-ai toolsets whose tools the agent may call.

        Use a toolset to attach a group of related tools at once, such as an
        MCP server's. For a single function, `append_tool` is simpler.
        """
        self._llm_task.toolsets += list(toolset)

    def append_toolset_factory(
        self, *factory: Callable[[AnyContext], AbstractToolset[None]]
    ):
        """Add factories building toolsets per run, from the task context.

        Prefer this over `append_toolset` when the toolset depends on inputs or
        env vars: a factory is called at run time, so it sees resolved values.
        """
        self._llm_task.toolset_factories += list(factory)

    def append_tool(self, *tool: Tool | ToolFuncEither):
        """Add tools the agent may call.

        Accepts a plain function or a pydantic-ai `Tool`. A plain function's
        name, type hints, and docstring become the tool schema the model sees,
        so both are worth writing carefully.
        """
        self._llm_task.tools += list(tool)

    def append_tool_factory(
        self,
        *factory: "Callable[[AnyContext], Tool | ToolFuncEither | list[Tool | ToolFuncEither]]",
    ):
        """Add factories building tools per run, from the task context.

        Prefer this over `append_tool` when the tool needs to close over
        resolved inputs or env vars, which exist only once the task runs.
        """
        self._llm_task.tool_factories += list(factory)

    def append_history_processor(self, *processor: HistoryProcessor):
        """Add processors that rewrite conversation history before each request.

        Processors run in registration order, each receiving the previous one's
        output. This is the seam summarization and trimming use to keep a long
        conversation inside the context window.
        """
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
        """Render the per-turn ``<live-context>`` block injected into the user
        turn. Empty string when there is no prompt manager (nothing to wire).

        ``inject_journal_index`` appends the journal index snapshot. Callers set
        it only when the index is absent from history, so it is paid once per
        context window and re-seeded after summarization drops it.
        ``first_message`` feeds the journal's first-turn auto-search addendum
        (ignored, harmlessly, on any other turn)."""
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
        """``get_live_context`` for async callers: git collection runs off-loop
        so the per-turn render cannot freeze the TUI's event loop."""
        if self._llm_task.prompt_manager_attr is None:
            return ""
        return await self._llm_task.prompt_manager_attr.create_live_context_async(
            ctx,
            inject_journal_index=inject_journal_index,
            first_message=first_message,
        )

    def get_model_settings(self, ctx: AnyContext) -> ModelSettings | None:
        """The task's model settings, falling back to the LLM config's."""
        model_settings = self._llm_task.model_settings_attr
        rendered_model_settings = get_attr(ctx, model_settings, None)
        if rendered_model_settings is not None:
            return rendered_model_settings
        return self._llm_task.llm_config.model_settings

    def get_model(self, ctx: AnyContext) -> str | Model:
        """The task's model, rendered against *ctx*, falling back to the config's.

        A blank render counts as unset, so an empty ``--model`` input does not
        shadow the configured model with an empty string.
        """
        return resolve_model(
            ctx,
            self._llm_task.model_attr,
            self._llm_task.render_model,
            self._llm_task.llm_config,
        )
