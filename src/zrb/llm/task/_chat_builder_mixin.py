"""Builder API for `LLMChatTask`.

All `set_*`, `add_*`, `append_*`, `prepend_*` methods that configure the task
post-construction live here, plus the related public properties for model
hooks. This keeps `llm_chat_task.py` focused on the `__init__` constructor and
the execution orchestration (`_exec_action` and friends).

State assumed to exist on the host class (set in `LLMChatTask.__init__`):
- `_prompt_manager`, `_uis`, `_ui_factories`, `_history_manager`
- `_custom_model_names`, `_model_getter`, `_model_renderer`
- `_approval_channels`
- `_tools`, `_tool_factories`, `_toolsets`, `_toolset_factories`
- `_tool_guidance_factories`, `_pending_tool_guidance`
- `_hook_factories`, `_history_processors`
- `_response_handlers`, `_tool_policies`, `_argument_formatters`
- `_triggers`, `_custom_commands`
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncIterable, Callable

from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.hook.manager import HookManager
from zrb.llm.prompt.manager import PromptManager
from zrb.llm.prompt.tool_guidance import ToolGuidance
from zrb.llm.tool_call import ArgumentFormatter, ResponseHandler, ToolPolicy

if TYPE_CHECKING:
    from pydantic_ai import Tool
    from pydantic_ai._agent_graph import HistoryProcessor
    from pydantic_ai.models import Model
    from pydantic_ai.tools import ToolFuncEither
    from pydantic_ai.toolsets import AbstractToolset

    from zrb.attr.type import StrListAttr
    from zrb.context.any_context import AnyContext
    from zrb.llm.approval.approval_channel import ApprovalChannel
    from zrb.llm.tool_call.ui_protocol import UIProtocol


class LLMChatBuilderMixin:
    """Post-construction configuration API for LLMChatTask."""

    @property
    def prompt_manager(self) -> PromptManager:
        if self._prompt_manager is None:
            raise ValueError(f"Task {self.name} doesn't have prompt_manager")
        return self._prompt_manager

    # --- UI ---------------------------------------------------------------

    def set_ui(self, ui: "UIProtocol | list[UIProtocol] | None"):
        """Set the UI protocol(s) for this task."""
        self._uis = [] if ui is None else (ui if isinstance(ui, list) else [ui])

    def append_ui(self, ui: "UIProtocol") -> None:
        """Append a UI to the list of UIs."""
        self._uis.append(ui)

    def set_ui_factory(self, ui_factory: Callable[..., "UIProtocol"] | None):
        """Set a factory function to instantiate the UI dynamically during execution."""
        self._ui_factories = [] if ui_factory is None else [ui_factory]

    def append_ui_factory(self, factory: Callable[..., "UIProtocol"]) -> None:
        """Append a UI factory to the list of factories."""
        self._ui_factories.append(factory)

    # --- History manager --------------------------------------------------

    def set_history_manager(self, history_manager: "AnyHistoryManager") -> None:
        """Set the history manager for this task."""
        self._history_manager = history_manager

    # --- Model hooks ------------------------------------------------------

    @property
    def custom_model_names(self) -> "StrListAttr | None":
        return self._custom_model_names

    @custom_model_names.setter
    def custom_model_names(self, value: "StrListAttr | None"):
        self._custom_model_names = value

    @property
    def model_getter(
        self,
    ) -> "Callable[[Model | str | None], Model | str | None] | None":
        return self._model_getter

    @model_getter.setter
    def model_getter(
        self, value: "Callable[[Model | str | None], Model | str | None] | None"
    ):
        self._model_getter = value

    @property
    def model_renderer(
        self,
    ) -> "Callable[[Model | str | None], Model | str | None] | None":
        return self._model_renderer

    @model_renderer.setter
    def model_renderer(
        self, value: "Callable[[Model | str | None], Model | str | None] | None"
    ):
        self._model_renderer = value

    # --- Approval channels ------------------------------------------------

    def set_approval_channel(self, channel: "ApprovalChannel | None"):
        """Set the approval channel for tool confirmations."""
        self._approval_channels = [] if channel is None else [channel]

    def append_approval_channel(self, channel: "ApprovalChannel") -> None:
        """Append an approval channel to the list."""
        self._approval_channels.append(channel)

    # --- Toolsets ---------------------------------------------------------

    def add_toolset(self, *toolset: "AbstractToolset"):
        self.append_toolset(*toolset)

    def append_toolset(self, *toolset: "AbstractToolset"):
        self._toolsets += list(toolset)

    def add_toolset_factory(
        self, *factory: "Callable[[AnyContext], AbstractToolset[None]]"
    ):
        self.append_toolset_factory(*factory)

    def append_toolset_factory(
        self, *factory: "Callable[[AnyContext], AbstractToolset[None]]"
    ):
        self._toolset_factories += list(factory)

    # --- Tools ------------------------------------------------------------

    def add_tool(self, *tool: "Tool | ToolFuncEither"):
        self.append_tool(*tool)

    def append_tool(self, *tool: "Tool | ToolFuncEither"):
        self._tools += list(tool)

    def add_tool_factory(
        self, *factory: "Callable[[AnyContext], Tool | ToolFuncEither]"
    ):
        self.append_tool_factory(*factory)

    def append_tool_factory(
        self, *factory: "Callable[[AnyContext], Tool | ToolFuncEither]"
    ):
        self._tool_factories += list(factory)

    # --- Tool guidance ----------------------------------------------------

    def add_tool_guidance_factory(
        self,
        *guidance_factory: "Callable[[AnyContext], ToolGuidance]",
    ):
        self.append_tool_guidance_factory(*guidance_factory)

    def append_tool_guidance_factory(
        self,
        *guidance_factory: "Callable[[AnyContext], ToolGuidance]",
    ):
        """Register guidance for dynamically-named factory tools.

        The factory is called when tools are resolved from factories. It should
        return a single ToolGuidance object.
        """
        self._tool_guidance_factories += list(guidance_factory)

    def add_tool_guidance(self, *guidance: ToolGuidance):
        self.append_tool_guidance(*guidance)

    def append_tool_guidance(self, *guidance: ToolGuidance):
        """Add tool guidance entries to be applied when prompt_manager is available."""
        self._pending_tool_guidance.extend(guidance)

    def _apply_tool_guidance(self):
        """Apply all pending tool guidance to the prompt manager."""
        if self._prompt_manager is None:
            return
        for g in self._pending_tool_guidance:
            self._prompt_manager.add_tool_guidance(
                group=g.group_name,
                name=g.tool_name,
                use_when=g.when_to_use,
                key_rule=g.key_rule,
            )
        self._pending_tool_guidance.clear()

    # --- Hook factories ---------------------------------------------------

    def add_hook_factory(self, *factory: Callable[[HookManager], None]):
        self.append_hook_factory(*factory)

    def append_hook_factory(self, *factory: Callable[[HookManager], None]):
        self._hook_factories += list(factory)

    # --- History processors ----------------------------------------------

    def add_history_processor(self, *processor: "HistoryProcessor"):
        self.append_history_processor(*processor)

    def append_history_processor(self, *processor: "HistoryProcessor"):
        self._history_processors += list(processor)

    # --- Response handlers / tool policies / arg formatters --------------

    def add_response_handler(self, *handler: ResponseHandler):
        self.prepend_response_handler(*handler)

    def prepend_response_handler(self, *handler: ResponseHandler):
        self._response_handlers = list(handler) + self._response_handlers

    def add_tool_policy(self, *policy: ToolPolicy):
        self.prepend_tool_policy(*policy)

    def prepend_tool_policy(self, *policy: ToolPolicy):
        self._tool_policies = list(policy) + self._tool_policies

    def add_argument_formatter(self, *formatter: ArgumentFormatter):
        self.prepend_argument_formatter(*formatter)

    def prepend_argument_formatter(self, *formatter: ArgumentFormatter):
        self._argument_formatters = list(formatter) + self._argument_formatters

    # --- Triggers ---------------------------------------------------------

    def add_trigger(self, *trigger: Callable[[], AsyncIterable[Any]]):
        self.append_trigger(*trigger)

    def append_trigger(self, *trigger: Callable[[], AsyncIterable[Any]]):
        self._triggers += trigger

    # --- Custom commands --------------------------------------------------

    def add_custom_command(
        self,
        *custom_command: (
            AnyCustomCommand | Callable[[], AnyCustomCommand | list[AnyCustomCommand]]
        ),
    ):
        self.append_custom_command(*custom_command)

    def append_custom_command(
        self,
        *custom_command: (
            AnyCustomCommand | Callable[[], AnyCustomCommand | list[AnyCustomCommand]]
        ),
    ):
        self._custom_commands += list(custom_command)
