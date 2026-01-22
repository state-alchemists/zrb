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
from zrb.llm.app.confirmation.handler import ConfirmationMiddleware
from zrb.llm.config.config import LLMConfig
from zrb.llm.config.config import llm_config as default_llm_config
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.history_manager.file_history_manager import FileHistoryManager
from zrb.llm.prompt.compose import PromptManager
from zrb.llm.task.llm_task import LLMTask
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
        system_prompt: (
            "Callable[[AnyContext], str | fstring | None] | str | None"
        ) = None,
        render_system_prompt: bool = False,
        prompt_manager: PromptManager | None = None,
        tools: list["Tool | ToolFuncEither"] = [],
        toolsets: list["AbstractToolset[None]"] = [],
        message: StrAttr | None = None,
        render_message: bool = True,
        attachment: "UserContent | list[UserContent] | Callable[[AnyContext], UserContent | list[UserContent]] | None" = None,  # noqa
        history_processors: list["HistoryProcessor"] = [],
        llm_config: LLMConfig | None = None,
        llm_limitter: LLMLimiter | None = None,
        model: (
            "Callable[[AnyContext], Model | str | fstring | None] | Model | None"
        ) = None,
        render_model: bool = True,
        model_settings: (
            "ModelSettings | Callable[[AnyContext], ModelSettings] | None"
        ) = None,
        conversation_name: StrAttr | None = None,
        render_conversation_name: bool = True,
        history_manager: AnyHistoryManager | None = None,
        tool_confirmation: Callable[[Any], Any] | None = None,
        yolo: BoolAttr = False,
        ui_summarize_commands: list[str] = [],
        ui_attach_commands: list[str] = [],
        ui_exit_commands: list[str] = [],
        ui_info_commands: list[str] = [],
        ui_save_commands: list[str] = [],
        ui_load_commands: list[str] = [],
        ui_redirect_output_commands: list[str] = [],
        ui_yolo_toggle_commands: list[str] = [],
        ui_exec_commands: list[str] = [],
        ui_greeting: StrAttr | None = None,
        render_ui_greeting: bool = True,
        ui_assistant_name: StrAttr | None = None,
        render_ui_assistant_name: bool = True,
        ui_jargon: StrAttr | None = None,
        render_ui_jargon: bool = True,
        ui_ascii_art: StrAttr | None = None,
        render_ui_ascii_art_name: bool = True,
        triggers: list[Callable[[], AsyncIterable[Any]]] = [],
        confirmation_middlewares: list[ConfirmationMiddleware] = [],
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
        self._tools = tools
        self._toolsets = toolsets
        self._message = message
        self._render_message = render_message
        self._attachment = attachment
        self._history_processors = history_processors
        self._model = model
        self._render_model = render_model
        self._model_settings = model_settings
        self._conversation_name = conversation_name
        self._render_conversation_name = render_conversation_name
        self._history_manager = (
            FileHistoryManager(history_dir=CFG.LLM_HISTORY_DIR)
            if history_manager is None
            else history_manager
        )
        self._tool_confirmation = tool_confirmation
        self._yolo = yolo
        self._ui_summarize_commands = ui_summarize_commands
        self._ui_attach_commands = ui_attach_commands
        self._ui_exit_commands = ui_exit_commands
        self._ui_info_commands = ui_info_commands
        self._ui_save_commands = ui_save_commands
        self._ui_load_commands = ui_load_commands
        self._ui_redirect_output_commands = ui_redirect_output_commands
        self._ui_yolo_toggle_commands = ui_yolo_toggle_commands
        self._ui_exec_commands = ui_exec_commands
        self._ui_greeting = ui_greeting
        self._render_ui_greeting = render_ui_greeting
        self._ui_assistant_name = ui_assistant_name
        self._render_ui_assistant_name = render_ui_assistant_name
        self._ui_jargon = ui_jargon
        self._render_ui_jargon = render_ui_jargon
        self._ui_ascii_art_name = ui_ascii_art
        self._render_ui_ascii_art_name = render_ui_ascii_art_name
        self._triggers = triggers
        self._confirmation_middlewares = confirmation_middlewares
        self._markdown_theme = markdown_theme
        self._interactive = interactive

    @property
    def prompt_manager(self) -> PromptManager:
        if self._prompt_manager is None:
            raise ValueError(f"Task {self.name} doesn't have prompt_manager")
        return self._prompt_manager

    def add_toolset(self, *toolset: "AbstractToolset"):
        self.append_toolset(*toolset)

    def append_toolset(self, *toolset: "AbstractToolset"):
        self._toolsets += list(toolset)

    def add_tool(self, *tool: "Tool | ToolFuncEither"):
        self.append_tool(*tool)

    def append_tool(self, *tool: "Tool | ToolFuncEither"):
        self._tools += list(tool)

    def add_history_processor(self, *processor: "HistoryProcessor"):
        self.append_history_processor(*processor)

    def append_history_processor(self, *processor: "HistoryProcessor"):
        self._history_processors += list(processor)

    def add_confirmation_middleware(self, *middleware: ConfirmationMiddleware):
        self.prepend_confirmation_middleware(*middleware)

    def prepend_confirmation_middleware(self, *middleware: ConfirmationMiddleware):
        self._confirmation_middlewares = (
            list(middleware) + self._confirmation_middlewares
        )

    def add_trigger(
        self,
        *trigger: Callable[[], AsyncIterable[Any]],
    ):
        self.append_trigger(*trigger)

    def append_trigger(
        self,
        *trigger: Callable[[], AsyncIterable[Any]],
    ):
        self._triggers += trigger

    async def _exec_action(self, ctx: AnyContext) -> Any:
        from zrb.llm.app.lexer import CLIStyleLexer
        from zrb.llm.app.ui import UI

        initial_conversation_name = self._get_conversation_name(ctx)
        initial_yolo = get_bool_attr(ctx, self._yolo, False)
        initial_message = get_attr(ctx, self._message, "", self._render_message)
        initial_attachments = get_attachments(ctx, self._attachment)
        ui_greeting = get_str_attr(ctx, self._ui_greeting, "", self._render_ui_greeting)
        ui_assistant_name = get_str_attr(
            ctx, self._ui_assistant_name, "", self._render_ui_assistant_name
        )
        ui_jargon = get_str_attr(ctx, self._ui_jargon, "", self._render_ui_jargon)
        ascii_art = get_str_attr(
            ctx, self._ui_ascii_art_name, "", self._render_ui_ascii_art_name
        )
        interactive = get_bool_attr(ctx, self._interactive, True)

        llm_task_core = LLMTask(
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
            tools=self._tools,
            toolsets=self._toolsets,
            history_processors=self._history_processors,
            llm_config=self._llm_config,
            llm_limitter=self._llm_limitter,
            model=self._model,
            render_model=self._render_model,
            model_settings=self._model_settings,
            history_manager=self._history_manager,
            message="{ctx.input.message}",
            conversation_name="{ctx.input.session}",
            yolo="{ctx.input.yolo}",
            attachment=lambda ctx: ctx.input.attachments,
            summarize_command=self._ui_summarize_commands,
        )

        if not interactive:
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

        async with AsyncExitStack() as stack:
            # Enter context for all toolsets that support it
            for toolset in self._toolsets:
                if hasattr(toolset, "__aenter__"):
                    await stack.enter_async_context(toolset)

            ui = UI(
                greeting=ui_greeting,
                assistant_name=ui_assistant_name,
                ascii_art=ascii_art,
                jargon=ui_jargon,
                output_lexer=CLIStyleLexer(),
                llm_task=llm_task_core,
                history_manager=self._history_manager,
                initial_message=initial_message,
                initial_attachments=initial_attachments,
                conversation_session_name=initial_conversation_name,
                yolo=initial_yolo,
                triggers=self._triggers,
                confirmation_middlewares=self._confirmation_middlewares,
                markdown_theme=self._markdown_theme,
                summarize_commands=self._ui_summarize_commands,
                attach_commands=self._ui_attach_commands,
                exit_commands=self._ui_exit_commands,
                info_commands=self._ui_info_commands,
                save_commands=self._ui_save_commands,
                load_commands=self._ui_load_commands,
                yolo_toggle_commands=self._ui_yolo_toggle_commands,
                redirect_output_commands=self._ui_redirect_output_commands,
                exec_commands=self._ui_exec_commands,
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

    def _get_model(self, ctx: AnyContext) -> "str | Model":
        model = self._model
        rendered_model = get_attr(ctx, model, None, auto_render=self._render_model)
        if rendered_model is not None:
            return rendered_model
        return self._llm_config.model
