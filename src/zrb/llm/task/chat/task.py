"""`LLMChatTask` — the conversational task type that powers `zrb llm chat`.

Wires together: tools/skills/hooks resolution, UI factory selection (default
TUI, std-out, http, multi-UI), approval-channel orchestration, history
manager + snapshot lifecycle, and the inner `LLMTask` execution. Heavy.
Most of the behaviour is decomposed into:

  building.py - construct the inner LLMTask (model, tools, prompts)
  running.py  - resolve UIs/triggers/custom commands, run the loop

For the public API and authoring patterns, see:
  docs/task-types/llmchat-task.md
For the end-to-end request lifecycle (CLI -> LLMChatTask -> agent run -> UI),
see docs/advanced-topics/llm-chat-lifecycle.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncIterable, Callable

from zrb.attr.type import BoolAttr, StrAttr, StrListAttr, fstring
from zrb.context.any_context import AnyContext
from zrb.context.print_fn import PrintFn
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.llm.agent import AnyToolConfirmation
from zrb.llm.config.config import LLMConfig
from zrb.llm.config.config import llm_config as default_llm_config
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.hook.manager import HookManager
from zrb.llm.prompt.manager import PromptManager
from zrb.llm.task.chat.building import ChatBuilding
from zrb.llm.task.chat.execution import ChatExecution
from zrb.llm.task.chat.running import ChatRunning
from zrb.llm.task.llm_task import LLMTask
from zrb.llm.tool_call import (
    ArgumentFormatter,
    ResponseHandler,
    ToolPolicy,
    replace_in_file_formatter,
    write_file_formatter,
)
from zrb.task.any_task import AnyTask
from zrb.task.base_task import BaseTask

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


class LLMChatTask(ChatBuilding, ChatRunning, ChatExecution, BaseTask):

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
        sandbox: "SandboxInput | BoolAttr" = None,
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
        ui_voice_commands: list[str] | None = None,
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
        self._tools = tools or []
        self._toolsets = toolsets or []
        # LLMChatTask-specific factories that resolve using parent context
        self._tool_factories = tool_factories or []
        self._toolset_factories = toolset_factories or []
        self._hook_factories: list[Callable[[HookManager], None]] = []
        # Set per execution in _create_llm_task_core; the interactive teardown
        # fires the terminal SESSION_END on it.
        self._active_hook_manager: HookManager | None = None
        self._message = message
        self._render_message = render_message
        self._attachment = attachment
        self._history_processors = history_processors or []
        self._capabilities = capabilities or []
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
        # Slash-command alias overrides, keyed as ChatExecution._get_ui_commands
        # and the UIs consume them. An empty list means "no override" — CFG
        # supplies the default at resolve time, not here, so a later env change
        # still wins.
        self._ui_command_overrides: dict[str, list[str]] = {
            key: value or []
            for key, value in (
                ("summarize", ui_summarize_commands),
                ("attach", ui_attach_commands),
                ("exit", ui_exit_commands),
                ("info", ui_info_commands),
                ("save", ui_save_commands),
                ("load", ui_load_commands),
                ("rewind", ui_rewind_commands),
                ("yolo_toggle", ui_yolo_toggle_commands),
                ("set_model", ui_set_model_commands),
                ("redirect_output", ui_redirect_output_commands),
                ("exec", ui_exec_commands),
                ("btw", ui_btw_commands),
                ("plan", ui_plan_commands),
                ("copy", ui_copy_commands),
                ("voice", ui_voice_commands),
            )
        }
        self._custom_commands = custom_commands or []
        # (value, render) per UI text; ChatRunning renders the block as one.
        self._ui_texts: dict[str, tuple[StrAttr | None, bool]] = {
            "greeting": (ui_greeting, render_ui_greeting),
            "assistant_name": (ui_assistant_name, render_ui_assistant_name),
            "ascii_art": (ui_ascii_art, render_ui_ascii_art_name),
            "jargon": (ui_jargon, render_ui_jargon),
        }
        self._triggers = triggers or []
        self._response_handlers = response_handlers or []
        self._tool_policies = tool_policies or []
        self._argument_formatters = (argument_formatters or []) + [
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
