from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncIterable, Callable

from zrb.attr.type import BoolAttr, StrAttr, StrListAttr, fstring
from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.context.print_fn import PrintFn
from zrb.context.shared_context import SharedContext
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.input.bool_input import BoolInput
from zrb.input.str_input import StrInput
from zrb.llm.agent import AnyToolConfirmation
from zrb.llm.config.config import LLMConfig
from zrb.llm.config.config import llm_config as default_llm_config
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.history_manager.file_history_manager import FileHistoryManager
from zrb.llm.prompt.manager import PromptManager
from zrb.llm.summarizer import (
    create_summarizer_history_processor,
)
from zrb.llm.task.llm_task import LLMTask
from zrb.llm.tool_call import (
    ArgumentFormatter,
    ResponseHandler,
    ToolPolicy,
    replace_in_file_formatter,
    write_file_formatter,
    write_files_formatter,
)
from zrb.llm.util.attachment import get_attachments
from zrb.session.session import Session
from zrb.task.any_task import AnyTask
from zrb.task.base_task import BaseTask
from zrb.util.attr import get_attr, get_bool_attr, get_str_attr
from zrb.util.cli.style import stylize_bold_yellow, stylize_faint
from zrb.util.string.name import get_random_name
from zrb.xcom.xcom import Xcom

if TYPE_CHECKING:
    from pydantic_ai import Tool, UserContent
    from pydantic_ai._agent_graph import HistoryProcessor
    from pydantic_ai.models import Model
    from pydantic_ai.settings import ModelSettings
    from pydantic_ai.tools import ToolFuncEither
    from pydantic_ai.toolsets import AbstractToolset
    from rich.theme import Theme

    from zrb.llm.approval.approval_channel import ApprovalChannel
    from zrb.llm.tool_call.ui_protocol import UIProtocol


class LLMChatTask(BaseTask):

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
        llm_config: LLMConfig | None = None,
        llm_limitter: LLMLimiter | None = None,
        model: (
            Callable[[AnyContext], Model | str | fstring | None] | Model | None
        ) = None,
        render_model: bool = True,
        model_settings: (
            ModelSettings | Callable[[AnyContext], ModelSettings] | None
        ) = None,
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
        yolo: BoolAttr = False,
        yolo_xcom_key: str = "yolo",
        ui_summarize_commands: list[str] | None = None,
        ui_attach_commands: list[str] | None = None,
        ui_exit_commands: list[str] | None = None,
        ui_info_commands: list[str] | None = None,
        ui_save_commands: list[str] | None = None,
        ui_load_commands: list[str] | None = None,
        ui_redirect_output_commands: list[str] | None = None,
        ui_yolo_toggle_commands: list[str] | None = None,
        ui_set_model_commands: list[str] | None = None,
        ui_exec_commands: list[str] | None = None,
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
        interactive: BoolAttr = True,
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
        self._llm_limitter = llm_limitter
        # Auto-convert system_prompt to prompt_manager if provided and prompt_manager not set
        if prompt_manager is None:
            prompt_manager = PromptManager(
                prompts=[system_prompt] if system_prompt else [],
                render=render_system_prompt,
                active_skills=active_skills,
                render_active_skills=render_active_skills,
                include_persona=False,
                include_mandate=False,
                include_system_context=False,
                include_journal=False,
                include_claude_skills=False,
                include_cli_skills=False,
                include_project_context=False,
            )
        self._prompt_manager = prompt_manager
        self._system_prompt = system_prompt
        self._render_system_prompt = render_system_prompt
        self._active_skills = active_skills
        self._render_active_skills = render_active_skills
        self._tools = tools if tools is not None else []
        self._toolsets = toolsets if toolsets is not None else []
        # LLMChatTask-specific factories that resolve using parent context
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
        self._model = model
        self._render_model = render_model
        self._model_settings = model_settings
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
        self._yolo = yolo
        self._yolo_xcom_key = yolo_xcom_key
        self._ui_summarize_commands = (
            ui_summarize_commands if ui_summarize_commands is not None else []
        )
        self._ui_attach_commands = (
            ui_attach_commands if ui_attach_commands is not None else []
        )
        self._ui_exit_commands = (
            ui_exit_commands if ui_exit_commands is not None else []
        )
        self._ui_info_commands = (
            ui_info_commands if ui_info_commands is not None else []
        )
        self._ui_save_commands = (
            ui_save_commands if ui_save_commands is not None else []
        )
        self._ui_load_commands = (
            ui_load_commands if ui_load_commands is not None else []
        )
        self._ui_redirect_output_commands = (
            ui_redirect_output_commands
            if ui_redirect_output_commands is not None
            else []
        )
        self._ui_yolo_toggle_commands = (
            ui_yolo_toggle_commands if ui_yolo_toggle_commands is not None else []
        )
        self._ui_set_model_commands = (
            ui_set_model_commands if ui_set_model_commands is not None else []
        )
        self._ui_exec_commands = (
            ui_exec_commands if ui_exec_commands is not None else []
        )
        self._custom_commands = custom_commands if custom_commands is not None else []
        self._ui_greeting = ui_greeting
        self._render_ui_greeting = render_ui_greeting
        self._ui_assistant_name = ui_assistant_name
        self._render_ui_assistant_name = render_ui_assistant_name
        self._ui_jargon = ui_jargon
        self._render_ui_jargon = render_ui_jargon
        self._ui_ascii_art_name = ui_ascii_art
        self._render_ui_ascii_art_name = render_ui_ascii_art_name
        self._triggers = triggers if triggers is not None else []
        self._response_handlers = (
            response_handlers if response_handlers is not None else []
        )
        self._tool_policies = tool_policies if tool_policies is not None else []
        self._argument_formatters = (
            argument_formatters if argument_formatters is not None else []
        ) + [
            replace_in_file_formatter,
            write_file_formatter,
            write_files_formatter,
        ]
        self._markdown_theme = markdown_theme
        self._interactive = interactive

    @property
    def prompt_manager(self) -> PromptManager:
        if self._prompt_manager is None:
            raise ValueError(f"Task {self.name} doesn't have prompt_manager")
        return self._prompt_manager

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

    def set_history_manager(self, history_manager: "AnyHistoryManager") -> None:
        """Set the history manager for this task."""
        self._history_manager = history_manager

    def set_approval_channel(self, channel: "ApprovalChannel | None"):
        """Set the approval channel for tool confirmations."""
        self._approval_channels = [] if channel is None else [channel]

    def append_approval_channel(self, channel: "ApprovalChannel") -> None:
        """Append an approval channel to the list."""
        self._approval_channels.append(channel)

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

    def add_history_processor(self, *processor: HistoryProcessor):
        self.append_history_processor(*processor)

    def append_history_processor(self, *processor: HistoryProcessor):
        self._history_processors += list(processor)

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

    def add_trigger(self, *trigger: Callable[[], AsyncIterable[Any]]):
        self.append_trigger(*trigger)

    def append_trigger(self, *trigger: Callable[[], AsyncIterable[Any]]):
        self._triggers += trigger

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

    async def _exec_action(self, ctx: AnyContext) -> Any:
        # 1. Resolve inputs/attributes
        initial_conversation_name = self._get_initial_conversation_name(ctx)
        initial_yolo = get_bool_attr(ctx, self._yolo, False)
        if self._yolo_xcom_key not in ctx.xcom:
            ctx.xcom[self._yolo_xcom_key] = Xcom()
        ctx.xcom[self._yolo_xcom_key].set(initial_yolo)

        initial_message = get_attr(ctx, self._message, "", self._render_message)
        initial_attachments = get_attachments(ctx, self._attachment)
        interactive = get_bool_attr(ctx, self._interactive, True)
        history_manager = (
            FileHistoryManager(history_dir=CFG.LLM_HISTORY_DIR)
            if self._history_manager is None
            else self._history_manager
        )

        # 2. Resolve UI Commands
        ui_commands = self._get_ui_commands()

        # 3. Resolve tools/toolsets from factories using parent context
        # LLMChatTask factories use the parent (LLMChatTask) context
        resolved_tools = self._get_all_tools(ctx)
        resolved_toolsets = self._get_all_toolsets(ctx)

        # 4. Create core LLM task
        llm_task_core = self._create_llm_task_core(
            ctx,
            ui_commands["summarize"],
            history_manager,
            interactive,
            resolved_tools,
            resolved_toolsets,
        )

        # 5. Run Interactive or Non-Interactive
        # Note: AsyncExitStack for toolsets is handled by LLMTask._exec_action
        if not interactive:
            return await self._run_non_interactive_session(
                ctx=ctx,
                llm_task_core=llm_task_core,
                initial_message=initial_message,
                initial_conversation_name=initial_conversation_name,
                initial_yolo=initial_yolo,
                initial_attachments=initial_attachments,
            )

        return await self._run_interactive_session(
            ctx=ctx,
            llm_task_core=llm_task_core,
            history_manager=history_manager,
            ui_commands=ui_commands,
            initial_message=initial_message,
            initial_conversation_name=initial_conversation_name,
            initial_yolo=initial_yolo,
            initial_attachments=initial_attachments,
        )

    def _get_all_tools(self, ctx: AnyContext) -> list[Tool | ToolFuncEither]:
        """Get all tools including those resolved from factories using parent context."""
        all_tools = list(self._tools)
        for factory in self._tool_factories:
            tool = factory(ctx)
            if isinstance(tool, list):
                all_tools.extend(tool)
            else:
                all_tools.append(tool)
        return all_tools

    def _get_all_toolsets(self, ctx: AnyContext) -> list[AbstractToolset[None]]:
        """Get all toolsets including those resolved from factories using parent context."""
        all_toolsets = list(self._toolsets)
        for factory in self._toolset_factories:
            toolset = factory(ctx)
            if isinstance(toolset, list):
                all_toolsets.extend(toolset)
            else:
                all_toolsets.append(toolset)
        return all_toolsets

    def _get_ui_commands(self) -> dict[str, list[str]]:
        """Resolve all UI commands from attributes or CFG defaults."""
        return {
            "summarize": (
                self._ui_summarize_commands
                if self._ui_summarize_commands
                else CFG.LLM_UI_COMMAND_SUMMARIZE
            ),
            "attach": (
                self._ui_attach_commands
                if self._ui_attach_commands
                else CFG.LLM_UI_COMMAND_ATTACH
            ),
            "exit": (
                self._ui_exit_commands
                if self._ui_exit_commands
                else CFG.LLM_UI_COMMAND_EXIT
            ),
            "info": (
                self._ui_info_commands
                if self._ui_info_commands
                else CFG.LLM_UI_COMMAND_INFO
            ),
            "save": (
                self._ui_save_commands
                if self._ui_save_commands
                else CFG.LLM_UI_COMMAND_SAVE
            ),
            "load": (
                self._ui_load_commands
                if self._ui_load_commands
                else CFG.LLM_UI_COMMAND_LOAD
            ),
            "yolo_toggle": (
                self._ui_yolo_toggle_commands
                if self._ui_yolo_toggle_commands
                else CFG.LLM_UI_COMMAND_YOLO_TOGGLE
            ),
            "set_model": (
                self._ui_set_model_commands
                if self._ui_set_model_commands
                else CFG.LLM_UI_COMMAND_SET_MODEL
            ),
            "redirect_output": (
                self._ui_redirect_output_commands
                if self._ui_redirect_output_commands
                else CFG.LLM_UI_COMMAND_REDIRECT_OUTPUT
            ),
            "exec": (
                self._ui_exec_commands
                if self._ui_exec_commands
                else CFG.LLM_UI_COMMAND_EXEC
            ),
        }

    def _create_llm_task_core(
        self,
        ctx: AnyContext,
        summarize_commands: list[str],
        history_manager: AnyHistoryManager,
        interactive: bool,
        resolved_tools: list[Tool | ToolFuncEither],
        resolved_toolsets: list[AbstractToolset[None]],
    ) -> LLMTask:
        """Create the inner LLMTask that handles the actual processing."""
        from zrb.llm.tool_call.handler import ToolCallHandler
        from zrb.llm.ui.std_ui import StdUI

        # Determine the tool confirmation and ui to use
        tool_confirmation = self._tool_confirmation
        ui = (
            self._uis if self._uis else None
        )  # Use programmatically set UIs if provided

        if interactive:
            # Interactive mode: Let the UI handle everything
            tool_confirmation = None
            ui = None  # Interactive mode uses its own UI system
        elif (
            self._tool_policies or self._response_handlers or self._argument_formatters
        ):
            # Non-interactive with policies/handlers/formatters: Use ToolCallHandler
            if not ui:
                ui = StdUI()
            tool_confirmation = ToolCallHandler(
                tool_policies=self._tool_policies,
                argument_formatters=self._argument_formatters,
                response_handlers=self._response_handlers,
            )
        else:
            # Non-interactive without policies: Use UI for approval
            if not ui:
                ui = StdUI()
            # tool_confirmation = None (let UI handle it via approval_channel)

        def check_yolo(*args, **kwargs):
            if self._yolo_xcom_key not in ctx.xcom:
                return False
            return ctx.xcom[self._yolo_xcom_key].get(False)

        # Create MultiplexApprovalChannel if multiple channels
        effective_approval_channel = None
        if len(self._approval_channels) == 1:
            effective_approval_channel = self._approval_channels[0]
        elif len(self._approval_channels) > 1:
            from zrb.llm.approval import MultiplexApprovalChannel

            effective_approval_channel = MultiplexApprovalChannel(
                self._approval_channels
            )

        CFG.LOGGER.debug("llm_chat_task _create_llm_task_core:")
        CFG.LOGGER.debug(f"  tool_confirmation: {tool_confirmation}")
        CFG.LOGGER.debug(f"  effective_approval_channel: {effective_approval_channel}")
        CFG.LOGGER.debug(f"  _approval_channels: {self._approval_channels}")

        # Pass resolved tools/toolsets to LLMTask (no factories needed since already resolved)
        return LLMTask(
            name=f"{self.name}-process",
            input=[
                StrInput("message", "Message"),
                StrInput("session", "Conversation Session"),
                BoolInput("yolo", "YOLO Mode"),
                StrInput("attachments", "Attachments"),
                StrInput("model", "Model"),
            ],
            env=self.envs,
            system_prompt=self._system_prompt,
            render_system_prompt=self._render_system_prompt,
            prompt_manager=self._prompt_manager,
            active_skills=self._active_skills,
            render_active_skills=self._render_active_skills,
            tools=resolved_tools,
            toolsets=resolved_toolsets,
            # No factories passed - tools/toolsets already resolved with parent context
            history_processors=self._history_processors
            + [create_summarizer_history_processor()],
            llm_config=self._llm_config,
            llm_limitter=self._llm_limitter,
            history_manager=history_manager,
            tool_confirmation=tool_confirmation,
            ui=ui,
            approval_channel=effective_approval_channel,
            message="{ctx.input.message}",
            conversation_name="{ctx.input.session}",
            yolo="{ctx.input.yolo}",
            dynamic_yolo=check_yolo,
            attachment=lambda ctx: ctx.input.attachments,
            model=lambda ctx: ctx.input.get("model"),
            render_model=False,
            summarize_command=summarize_commands,
        )

    async def _run_non_interactive_session(
        self,
        ctx: AnyContext,
        llm_task_core: LLMTask,
        initial_message: Any,
        initial_conversation_name: str,
        initial_yolo: bool,
        initial_attachments: list[UserContent],
    ) -> Any:
        # AsyncExitStack is handled by LLMTask._exec_action
        session_input = {
            "message": initial_message,
            "session": initial_conversation_name,
            "yolo": initial_yolo,
            "attachments": initial_attachments,
            "model": self._get_model(ctx),
        }
        shared_ctx = SharedContext(
            input=session_input,
            print_fn=ctx.shared_print,  # Use current task's print function
        )
        session = Session(shared_ctx)
        result = await llm_task_core.async_run(session)
        self._print_conversation_name(ctx, initial_conversation_name)
        return result

    async def _run_interactive_session(
        self,
        ctx: AnyContext,
        llm_task_core: LLMTask,
        history_manager: AnyHistoryManager,
        ui_commands: dict[str, list[str]],
        initial_message: Any,
        initial_conversation_name: str,
        initial_yolo: bool,
        initial_attachments: list[UserContent],
    ) -> Any:
        from zrb.llm.ui.base_ui import BaseUI

        # Note: AsyncExitStack is handled by LLMTask._exec_action
        # 1. Resolve UIs from factories
        resolved_uis: list["UIProtocol"] = list(self._uis)
        for factory in self._ui_factories:
            factory_ui = factory(
                ctx=ctx,
                llm_task=llm_task_core,
                history_manager=history_manager,
                ui_commands=ui_commands,
                initial_message=initial_message,
                initial_conversation_name=initial_conversation_name,
                initial_yolo=initial_yolo,
                initial_attachments=initial_attachments,
            )
            if isinstance(factory_ui, list):
                resolved_uis.extend(factory_ui)
            else:
                resolved_uis.append(factory_ui)

        # 2. Resolve UI attributes for default UI
        ui_greeting = get_str_attr(ctx, self._ui_greeting, "", self._render_ui_greeting)
        ui_assistant_name = get_str_attr(
            ctx, self._ui_assistant_name, "", self._render_ui_assistant_name
        )
        ui_jargon = get_str_attr(ctx, self._ui_jargon, "", self._render_ui_jargon)
        ascii_art = get_str_attr(
            ctx, self._ui_ascii_art_name, "", self._render_ui_ascii_art_name
        )

        # Resolve custom commands
        resolved_custom_commands: list[AnyCustomCommand] = []
        for cmd in self._custom_commands:
            if callable(cmd):
                res = cmd()
                if isinstance(res, list):
                    resolved_custom_commands.extend(res)
                else:
                    resolved_custom_commands.append(res)
            else:
                resolved_custom_commands.append(cmd)

        # 3. Determine the UI to use
        from zrb.llm.app.lexer import CLIStyleLexer
        from zrb.llm.ui.default_ui import UI
        from zrb.llm.ui.multi_ui import MultiUI

        ui: "UIProtocol | None" = None

        if resolved_uis:
            # We have factory UIs - create default UI and combine them
            default_ui = UI(
                ctx=ctx,
                yolo_xcom_key=self._yolo_xcom_key,
                greeting=ui_greeting,
                assistant_name=ui_assistant_name,
                ascii_art=ascii_art,
                jargon=ui_jargon,
                output_lexer=CLIStyleLexer(),
                llm_task=llm_task_core,
                history_manager=history_manager,
                initial_message=initial_message,
                initial_attachments=initial_attachments,
                conversation_session_name=initial_conversation_name,
                is_yolo=initial_yolo,
                triggers=self._triggers,
                response_handlers=self._response_handlers,
                tool_policies=self._tool_policies,
                argument_formatters=self._argument_formatters,
                markdown_theme=self._markdown_theme,
                summarize_commands=ui_commands["summarize"],
                attach_commands=ui_commands["attach"],
                exit_commands=ui_commands["exit"],
                info_commands=ui_commands["info"],
                save_commands=ui_commands["save"],
                load_commands=ui_commands["load"],
                yolo_toggle_commands=ui_commands["yolo_toggle"],
                set_model_commands=ui_commands["set_model"],
                redirect_output_commands=ui_commands["redirect_output"],
                exec_commands=ui_commands["exec"],
                custom_commands=resolved_custom_commands,
                model=self._get_model(ctx),
            )
            # Add default UI first, then factory UIs
            all_uis = [default_ui] + resolved_uis
            if len(all_uis) == 1:
                ui = default_ui
            else:
                ui = MultiUI(all_uis)
                # Set up approval channel for MultiUI
                if len(self._approval_channels) == 1:
                    ui.set_approval_channel(self._approval_channels[0])
                elif len(self._approval_channels) > 1:
                    from zrb.llm.approval import MultiplexApprovalChannel

                    ui.set_approval_channel(
                        MultiplexApprovalChannel(self._approval_channels)
                    )
                # Set tool call handler so CLI mode has same formatters as standalone CLI
                ui.set_tool_call_handler(default_ui.tool_call_handler)
        else:
            # No factory UIs, use default UI
            ui = UI(
                ctx=ctx,
                yolo_xcom_key=self._yolo_xcom_key,
                greeting=ui_greeting,
                assistant_name=ui_assistant_name,
                ascii_art=ascii_art,
                jargon=ui_jargon,
                output_lexer=CLIStyleLexer(),
                llm_task=llm_task_core,
                history_manager=history_manager,
                initial_message=initial_message,
                initial_attachments=initial_attachments,
                conversation_session_name=initial_conversation_name,
                is_yolo=initial_yolo,
                triggers=self._triggers,
                response_handlers=self._response_handlers,
                tool_policies=self._tool_policies,
                argument_formatters=self._argument_formatters,
                markdown_theme=self._markdown_theme,
                summarize_commands=ui_commands["summarize"],
                attach_commands=ui_commands["attach"],
                exit_commands=ui_commands["exit"],
                info_commands=ui_commands["info"],
                save_commands=ui_commands["save"],
                load_commands=ui_commands["load"],
                yolo_toggle_commands=ui_commands["yolo_toggle"],
                set_model_commands=ui_commands["set_model"],
                redirect_output_commands=ui_commands["redirect_output"],
                exec_commands=ui_commands["exec"],
                custom_commands=resolved_custom_commands,
                model=self._get_model(ctx),
            )

        # 4. Run the UI
        if ui is None:
            raise ValueError("No UI available")
        if isinstance(ui, BaseUI) or hasattr(ui, "run_async"):
            await ui.run_async()
        else:
            raise ValueError(f"UI {type(ui)} does not implement run_async")
        last_output = getattr(ui, "last_output", "")
        final_conversation_name = self._get_ui_conversation_name(
            ui, initial_conversation_name
        )
        self._print_conversation_name(ctx, final_conversation_name)
        return last_output

    def _print_conversation_name(self, ctx: AnyContext, conversation_name: str):
        stylized_label = stylize_faint("Session")
        stylized_conversation_name = stylize_bold_yellow(conversation_name)
        ctx.print(
            stylize_faint(f"{stylized_label}: {stylized_conversation_name}"), plain=True
        )

    def _get_initial_conversation_name(self, ctx: AnyContext) -> str:
        conversation_name = str(
            get_attr(ctx, self._conversation_name, "", self._render_conversation_name)
        )
        if conversation_name.strip() == "":
            conversation_name = get_random_name()
        return conversation_name

    def _get_ui_conversation_name(
        self, ui: "UIProtocol", initial_conversation_name: str
    ) -> str:
        """Get the current conversation name from UI or fallback to initial name."""
        from zrb.llm.ui.base_ui import BaseUI

        if isinstance(ui, BaseUI):
            return ui.conversation_session_name
        return getattr(ui, "conversation_session_name", initial_conversation_name)

    def _get_model(self, ctx: AnyContext) -> str | Model:
        model = self._model
        rendered_model = get_attr(ctx, model, None, auto_render=self._render_model)
        if isinstance(rendered_model, str) and rendered_model.strip() == "":
            rendered_model = None
        if rendered_model is not None:
            return rendered_model
        return self._llm_config.model
