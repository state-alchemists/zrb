"""Shared attribute declarations for the `LLMChatTask` mixins.

Every `_`-prefixed name below is assigned in `LLMChatTask.__init__`. Declaring
the types here once lets `ChatBuilding`, `ChatRunning`, and `ChatExecution` be
type-checked in isolation without each re-declaring the same list — the three
copies used to drift, and one of them carried a "keep the two in sync" comment
that only a human could honour.

Annotation-only on purpose: a bare annotation creates no class attribute, so
putting `ChatState` in the MRO ahead of `BaseTask` shadows nothing at runtime.
Sibling-*method* contracts stay in the mixin that calls them — this class owns
state, not behaviour.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncIterable, Callable

if TYPE_CHECKING:
    from pydantic_ai import Tool, UserContent
    from pydantic_ai.capabilities import AbstractCapability
    from pydantic_ai.models import Model
    from pydantic_ai.settings import ModelSettings
    from pydantic_ai.tools import ToolFuncEither
    from pydantic_ai.toolsets import AbstractToolset
    from rich.theme import Theme

    from zrb.attr.type import BoolAttr, StrAttr, StrListAttr, fstring
    from zrb.context.any_context import AnyContext
    from zrb.env.any_env import AnyEnv
    from zrb.llm.agent import AnyToolConfirmation
    from zrb.llm.agent.common import HistoryProcessor
    from zrb.llm.approval.approval_channel import ApprovalChannel
    from zrb.llm.config.config import LLMConfig
    from zrb.llm.config.limiter import LLMLimiter
    from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
    from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
    from zrb.llm.hook.manager import HookManager
    from zrb.llm.permission import PermissionPolicyInput
    from zrb.llm.prompt.manager import PromptManager
    from zrb.llm.sandbox import SandboxInput
    from zrb.llm.tool_call import ArgumentFormatter, ResponseHandler, ToolPolicy
    from zrb.llm.tool_call.ui_protocol import UIProtocol


class ChatState:
    """State set by `LLMChatTask.__init__`, declared once for the mixins."""

    # --- Prompt -----------------------------------------------------------
    _prompt_manager: PromptManager | None
    _system_prompt: Callable[[AnyContext], str | fstring | None] | str | None
    _render_system_prompt: bool
    _active_skills: StrListAttr | None
    _render_active_skills: bool

    # --- Tools / toolsets --------------------------------------------------
    _tools: list[Tool | ToolFuncEither]
    _tool_factories: list[Callable[[AnyContext], Tool | ToolFuncEither]]
    _toolsets: list[AbstractToolset[None]]
    _toolset_factories: list[Callable[[AnyContext], AbstractToolset[None]]]
    _tool_confirmation: AnyToolConfirmation
    _tool_policies: list[ToolPolicy]
    _argument_formatters: list[ArgumentFormatter]
    _response_handlers: list[ResponseHandler]

    # --- Hooks -------------------------------------------------------------
    _hook_factories: list[Callable[[HookManager], None]]
    #: Explicit manager from the constructor; None means "build a fresh one per
    #: run", which is the default and keeps one chat session's hooks out of the
    #: next.
    _hook_manager: HookManager | None
    _active_hook_manager: HookManager | None

    # --- Message / model ---------------------------------------------------
    _message: StrAttr | None
    _render_message: bool
    _attachment: (
        UserContent
        | list[UserContent]
        | Callable[[AnyContext], UserContent | list[UserContent]]
        | None
    )
    _capabilities: list[AbstractCapability[Any]]
    _model: Callable[[AnyContext], Model | str | fstring | None] | Model | None
    _render_model: bool
    _model_settings: ModelSettings | Callable[[AnyContext], ModelSettings] | None
    _custom_model_names: StrListAttr | None
    _show_ollama_models: bool | None
    _show_pydantic_ai_models: bool | None

    # --- Config ------------------------------------------------------------
    _llm_config: LLMConfig
    _llm_limiter: LLMLimiter | None
    _permissions: PermissionPolicyInput
    _sandbox: SandboxInput | BoolAttr
    _yolo: BoolAttr
    _yolo_xcom_key: str
    _interactive: BoolAttr

    # --- History -----------------------------------------------------------
    _conversation_name: StrAttr | None
    _render_conversation_name: bool
    _history_manager: AnyHistoryManager | None
    _history_processors: list[HistoryProcessor]
    _enable_rewind: bool | None
    _snapshot_dir: StrAttr | None

    # --- UI ----------------------------------------------------------------
    _uis: list[UIProtocol]
    _ui_factories: list[Callable[..., UIProtocol]]
    _include_default_ui: bool
    _approval_channels: list[ApprovalChannel]
    _markdown_theme: Theme | None
    _triggers: list[Callable[[], AsyncIterable[Any]]]
    _custom_commands: list[
        AnyCustomCommand | Callable[[], AnyCustomCommand | list[AnyCustomCommand]]
    ]
    # greeting / assistant_name / ascii_art / jargon -> (value, render)
    _ui_texts: dict[str, tuple[StrAttr | None, bool]]

    # --- UI command aliases ------------------------------------------------
    # Per-command overrides; an empty list defers to the CFG default.
    _ui_command_overrides: dict[str, list[str]]

    if TYPE_CHECKING:
        # From BaseTask, which LLMChatTask also extends. Declared as
        # properties, not variables, to match BaseTask — a variable here would
        # trip reportIncompatibleVariableOverride on the composed class.
        @property
        def name(self) -> str: ...

        @property
        def envs(self) -> list[AnyEnv]: ...
