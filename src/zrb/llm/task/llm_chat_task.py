from __future__ import annotations

from collections.abc import AsyncIterable, Callable
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING, Any

from zrb.attr.type import BoolAttr, StrAttr, fstring
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
from zrb.llm.history_processor.summarizer import (
    create_summarizer_history_processor,
)
from zrb.llm.prompt.manager import PromptManager
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
from zrb.util.string.name import get_random_name

if TYPE_CHECKING:
    from pydantic_ai import Tool, UserContent
    from pydantic_ai._agent_graph import HistoryProcessor
    from pydantic_ai.models import Model
    from pydantic_ai.settings import ModelSettings
    from pydantic_ai.tools import ToolFuncEither
    from pydantic_ai.toolsets import AbstractToolset
    from rich.theme import Theme


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
        yolo: BoolAttr = False,
        ui_summarize_commands: list[str] | None = None,
        ui_attach_commands: list[str] | None = None,
        ui_exit_commands: list[str] | None = None,
        ui_info_commands: list[str] | None = None,
        ui_save_commands: list[str] | None = None,
        ui_load_commands: list[str] | None = None,
        ui_redirect_output_commands: list[str] | None = None,
        ui_yolo_toggle_commands: list[str] | None = None,
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
        self._system_prompt = system_prompt
        self._render_system_prompt = render_system_prompt
        self._prompt_manager = prompt_manager
        self._tools = tools if tools is not None else []
        self._toolsets = toolsets if toolsets is not None else []
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
        if not self._history_processors:
            self._history_processors.append(create_summarizer_history_processor())
        self._model = model
        self._render_model = render_model
        self._model_settings = model_settings
        self._conversation_name = conversation_name
        self._render_conversation_name = render_conversation_name
        self._history_manager = history_manager
        self._tool_confirmation = tool_confirmation
        self._yolo = yolo
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
        initial_conversation_name = self._get_conversation_name(ctx)
        initial_yolo = get_bool_attr(ctx, self._yolo, False)
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

        # 3. Create core LLM task
        llm_task_core = self._create_llm_task_core(
            ctx, ui_commands["summarize"], history_manager, interactive
        )

        # 4. Run Interactive or Non-Interactive
        if not interactive:
            return await self._run_non_interactive_session(
                ctx=ctx,
                llm_task_core=llm_task_core,
                initial_message=initial_message,
                initial_conversation_name=initial_conversation_name,
                initial_yolo=initial_yolo,
                initial_attachments=initial_attachments,
            )

        return await self._run_interactive_ui(
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
        """Get all tools including those resolved from factories."""
        all_tools = list(self._tools)
        for factory in self._tool_factories:
            tool = factory(ctx)
            if isinstance(tool, list):
                all_tools.extend(tool)
            else:
                all_tools.append(tool)
        return all_tools

    def _get_all_toolsets(self, ctx: AnyContext) -> list[AbstractToolset[None]]:
        """Get all toolsets including those resolved from factories."""
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
    ) -> LLMTask:
        """Create the inner LLMTask that handles the actual processing."""
        from zrb.llm.agent.std_ui import StdUI
        from zrb.llm.tool_call import check_tool_policies

        # Determine the tool confirmation and ui to use
        tool_confirmation = self._tool_confirmation
        ui = None

        # If we have tool policies, response handlers, or argument formatters,
        # create a ToolCallHandler (or simple policy checker) that wraps existing config
        tool_policies = self._tool_policies
        response_handlers = self._response_handlers if interactive else []
        argument_formatters = self._argument_formatters if interactive else []

        if interactive:
            # Interactive mode: Let the UI handle everything
            tool_confirmation = None
            ui = None
        elif tool_policies:
            # Non-interactive: Use simple policy checker, with StdUI
            ui = StdUI()

            async def _simple_policy_checker(call):
                return await check_tool_policies(tool_policies, ui, call)

            tool_confirmation = _simple_policy_checker

        # Get all tools and toolsets including those from factories
        resolved_tools = self._get_all_tools(ctx)
        resolved_toolsets = self._get_all_toolsets(ctx)

        return LLMTask(
            name=f"{self.name}-process",
            input=[
                StrInput("message", "Message"),
                StrInput("session", "Conversation Session"),
                BoolInput("yolo", "YOLO Mode"),
                StrInput("attachments", "Attachments"),
            ],
            env=self.envs,
            system_prompt=self._system_prompt,
            render_system_prompt=self._render_system_prompt,
            prompt_manager=self._prompt_manager,
            tools=resolved_tools,
            toolsets=resolved_toolsets,
            history_processors=self._history_processors,
            llm_config=self._llm_config,
            llm_limitter=self._llm_limitter,
            model=self._model,
            render_model=self._render_model,
            model_settings=self._model_settings,
            history_manager=history_manager,
            tool_confirmation=tool_confirmation,
            ui=ui,
            message="{ctx.input.message}",
            conversation_name="{ctx.input.session}",
            yolo="{ctx.input.yolo}",
            attachment=lambda ctx: ctx.input.attachments,
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
        async with AsyncExitStack() as stack:
            # Enter context for all toolsets that support it
            for toolset in self._get_all_toolsets(ctx):
                if hasattr(toolset, "__aenter__"):
                    await stack.enter_async_context(toolset)

            session_input = {
                "message": initial_message,
                "session": initial_conversation_name,
                "yolo": initial_yolo,
                "attachments": initial_attachments,
            }
            shared_ctx = SharedContext(
                input=session_input,
                print_fn=ctx.shared_print,  # Use current task's print function
            )
            session = Session(shared_ctx)
            return await llm_task_core.async_run(session)

    async def _run_interactive_ui(
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
        from zrb.llm.app.lexer import CLIStyleLexer
        from zrb.llm.app.ui import UI

        # Resolve UI attributes
        ui_greeting = get_str_attr(ctx, self._ui_greeting, "", self._render_ui_greeting)
        ui_assistant_name = get_str_attr(
            ctx, self._ui_assistant_name, "", self._render_ui_assistant_name
        )
        ui_jargon = get_str_attr(ctx, self._ui_jargon, "", self._render_ui_jargon)
        ascii_art = get_str_attr(
            ctx, self._ui_ascii_art_name, "", self._render_ui_ascii_art_name
        )

        async with AsyncExitStack() as stack:
            # Enter context for all toolsets that support it
            for toolset in self._get_all_toolsets(ctx):
                if hasattr(toolset, "__aenter__"):
                    await stack.enter_async_context(toolset)

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

            ui = UI(
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
                yolo=initial_yolo,
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
                redirect_output_commands=ui_commands["redirect_output"],
                exec_commands=ui_commands["exec"],
                custom_commands=resolved_custom_commands,
                model=self._get_model(ctx),
            )
            await ui.run_async()
            return ui.last_output

    def _get_conversation_name(self, ctx: AnyContext) -> str:
        conversation_name = str(
            get_attr(ctx, self._conversation_name, "", self._render_conversation_name)
        )
        if conversation_name.strip() == "":
            conversation_name = get_random_name()
        return conversation_name

    def _get_model(self, ctx: AnyContext) -> str | Model:
        model = self._model
        rendered_model = get_attr(ctx, model, None, auto_render=self._render_model)
        if rendered_model is not None:
            return rendered_model
        return self._llm_config.model
