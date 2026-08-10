"""Builder API for `LLMChatTask`.

All `set_*`, `add_*`, `append_*`, `prepend_*` methods that configure the task
post-construction live here, plus the related public properties for model
hooks. This keeps `llm_chat_task.py` focused on the `__init__` constructor and
the execution orchestration (`_exec_action` and friends).

The `_*` state this mixin mutates is set in `LLMChatTask.__init__` and typed in
`state.py::ChatState`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncIterable, Callable

from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.hook.manager import HookManager
from zrb.llm.prompt.manager import PromptManager
from zrb.llm.task.chat.state import ChatState
from zrb.llm.tool_call import ArgumentFormatter, ResponseHandler, ToolPolicy

if TYPE_CHECKING:
    from pydantic_ai import Tool
    from pydantic_ai.tools import ToolFuncEither
    from pydantic_ai.toolsets import AbstractToolset

    from zrb.attr.type import BoolAttr, StrListAttr
    from zrb.context.any_context import AnyContext
    from zrb.llm.agent.common import HistoryProcessor
    from zrb.llm.approval.approval_channel import ApprovalChannel
    from zrb.llm.config.config import LLMConfig
    from zrb.llm.config.limiter import LLMLimiter
    from zrb.llm.permission import PermissionPolicyInput
    from zrb.llm.sandbox import SandboxInput
    from zrb.llm.tool_call.ui_protocol import UIProtocol


class ChatBuilding(ChatState):
    """Post-construction configuration API for LLMChatTask."""

    @property
    def prompt_manager(self) -> PromptManager:
        """The `PromptManager` composing this task's system prompt.

        Raises:
            ValueError: If the task was built without one.
        """
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
        """Extra model names offered by the `/model` picker, beyond detected ones."""
        return self._custom_model_names

    @custom_model_names.setter
    def custom_model_names(self, value: "StrListAttr | None"):
        """Replace the custom model-name list."""
        self._custom_model_names = value

    def set_approval_channel(self, channel: "ApprovalChannel | None"):
        """Set the approval channel for tool confirmations."""
        self._approval_channels = [] if channel is None else [channel]

    def append_approval_channel(self, channel: "ApprovalChannel") -> None:
        """Append an approval channel to the list."""
        self._approval_channels.append(channel)

    # --- Toolsets ---------------------------------------------------------

    def append_toolset(self, *toolset: "AbstractToolset"):
        """Add pydantic-ai toolsets whose tools the agent may call.

        Use a toolset to attach a group of related tools at once, such as an
        MCP server's. For a single function, `append_tool` is simpler.
        """
        self._toolsets += list(toolset)

    def append_toolset_factory(
        self, *factory: "Callable[[AnyContext], AbstractToolset[None]]"
    ):
        """Add factories building toolsets per run, from the task context.

        Prefer this over `append_toolset` when the toolset depends on inputs or
        env vars: a factory is called at run time, so it sees resolved values.
        """
        self._toolset_factories += list(factory)

    # --- Tools ------------------------------------------------------------

    def append_tool(self, *tool: "Tool | ToolFuncEither"):
        """Add tools the agent may call.

        Accepts a plain function or a pydantic-ai `Tool`. A plain function's
        name, type hints, and docstring become the tool schema the model sees,
        so both are worth writing carefully.
        """
        self._tools += list(tool)

    def append_tool_factory(
        self,
        *factory: "Callable[[AnyContext], Tool | ToolFuncEither | list[Tool | ToolFuncEither]]",
    ):
        """Add factories building tools per run, from the task context.

        Prefer this over `append_tool` when the tool needs to close over
        resolved inputs or env vars, which exist only once the task runs.
        """
        self._tool_factories += list(factory)

    # --- Hook factories ---------------------------------------------------

    def append_hook_factory(self, *factory: Callable[[HookManager], None]):
        """Add factories registering hooks on this task's hook manager.

        Unlike `LLMTaskBuilding.append_hook_factory`, factories are stored and
        applied when the chat task builds its inner `LLMTask`, not immediately.
        """
        self._hook_factories += list(factory)

    # --- History processors ----------------------------------------------

    def append_history_processor(self, *processor: "HistoryProcessor"):
        """Add processors that rewrite conversation history before each request.

        Processors run in registration order, each receiving the previous one's
        output. This is the seam summarization and trimming use to keep a long
        conversation inside the context window.
        """
        self._history_processors += list(processor)

    # --- Response handlers / tool policies / arg formatters --------------

    def prepend_response_handler(self, *handler: ResponseHandler):
        """Add handlers that post-process a tool's result before the model sees it.

        Inserted at the front, so these run before already-registered handlers.
        The chain short-circuits: the first handler returning a non-`None`
        result wins and the rest are skipped.
        """
        self._response_handlers = list(handler) + self._response_handlers

    def prepend_tool_policy(self, *policy: ToolPolicy):
        """Add policies deciding whether a tool call is allowed, denied, or confirmed.

        Inserted at the front, so these run before already-registered policies.
        The chain short-circuits: the first policy returning a verdict decides,
        and the rest are skipped.
        """
        self._tool_policies = list(policy) + self._tool_policies

    def prepend_argument_formatter(self, *formatter: ArgumentFormatter):
        """Add formatters controlling how a tool call's arguments are displayed.

        Inserted at the front of the pipeline. Unlike the policy and handler
        chains, formatters do not short-circuit: every one runs in order and
        each non-`None` result overwrites the previous, so formatters already
        registered still run after this one and may replace its output.
        """
        self._argument_formatters = list(formatter) + self._argument_formatters

    # --- Triggers ---------------------------------------------------------

    def append_trigger(self, *trigger: Callable[[], AsyncIterable[Any]]):
        """Add sources that feed messages into the chat loop unprompted.

        Each trigger is a callable returning an async iterable; every item it
        yields is submitted as a user turn. This is how a scheduled or
        externally-driven message enters an otherwise interactive session.
        """
        self._triggers += trigger

    # --- Custom commands --------------------------------------------------

    def append_custom_command(
        self,
        *custom_command: (
            AnyCustomCommand | Callable[[], AnyCustomCommand | list[AnyCustomCommand]]
        ),
    ):
        """Add slash commands available inside the chat session.

        Accepts an `AnyCustomCommand`, or a callable returning one or a list of
        them. A callable is resolved when the session starts, which lets a
        command set be discovered at run time.
        """
        self._custom_commands += list(custom_command)

    # --- Accessors --------------------------------------------------------

    @property
    def llm_config(self) -> "LLMConfig":
        """Model, credentials, and endpoint settings backing this task."""
        return self._llm_config

    @property
    def llm_limiter(self) -> "LLMLimiter | None":
        """Rate and token limiter throttling requests, or None if unlimited."""
        return self._llm_limiter

    @property
    def permissions(self) -> "PermissionPolicyInput":
        """Policy bounding which files and commands the agent's tools may touch."""
        return self._permissions

    @permissions.setter
    def permissions(self, value: "PermissionPolicyInput"):
        """Replace the permission policy."""
        self._permissions = value

    @property
    def sandbox(self) -> "SandboxInput | BoolAttr":
        """Whether, and how, tool calls run inside a sandbox.

        A bool or template toggles the default sandbox; a `SandboxInput`
        configures it.
        """
        return self._sandbox

    @sandbox.setter
    def sandbox(self, value: "SandboxInput | BoolAttr"):
        self._sandbox = value

    @property
    def history_manager(self) -> "AnyHistoryManager | None":
        """Get the history manager."""
        return self._history_manager

    @history_manager.setter
    def history_manager(self, value: "AnyHistoryManager | None"):
        """Set the history manager."""
        self._history_manager = value

    @property
    def ui_factories(self) -> list[Callable[..., "UIProtocol"]]:
        """Get the UI factories."""
        return self._ui_factories

    @ui_factories.setter
    def ui_factories(self, value: list[Callable[..., "UIProtocol"]]):
        """Set the UI factories."""
        self._ui_factories = value

    @property
    def approval_channels(self) -> list["ApprovalChannel"]:
        """Get the approval channels."""
        return self._approval_channels

    @approval_channels.setter
    def approval_channels(self, value: list["ApprovalChannel"]):
        """Set the approval channels."""
        self._approval_channels = value

    @property
    def include_default_ui(self) -> bool:
        """Check if the default UI should be included."""
        return self._include_default_ui

    @include_default_ui.setter
    def include_default_ui(self, value: bool):
        """Set if the default UI should be included."""
        self._include_default_ui = value
