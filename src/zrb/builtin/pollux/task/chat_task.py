from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from zrb.attr.type import BoolAttr, StrAttr, fstring
from zrb.builtin.pollux.app.confirmation.handler import ConfirmationMiddleware
from zrb.builtin.pollux.config.config import LLMConfig
from zrb.builtin.pollux.config.limiter import LLMLimiter
from zrb.builtin.pollux.history_manager import AnyHistoryManager
from zrb.builtin.pollux.prompt.compose import PromptManager
from zrb.builtin.pollux.task.llm_task import LLMTask
from zrb.builtin.pollux.util.attachment import get_attachments
from zrb.context.any_context import AnyContext
from zrb.context.print_fn import PrintFn
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.input.bool_input import BoolInput
from zrb.input.str_input import StrInput
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
        summarize_command: list[str] = [],
        ui_greeting: StrAttr | None = None,
        render_ui_greeting: bool = True,
        ui_assistant_name: StrAttr | None = None,
        render_ui_assistant_name: bool = True,
        ui_jargon: StrAttr | None = None,
        render_ui_jargon: bool = True,
        triggers: list[Callable[[], Any]] = [],
        confirmation_middlewares: list[ConfirmationMiddleware] = [],
        execute_condition: bool | str | Callable[[AnyContext], bool] = True,
        retries: int = 2,
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
        self._llm_config = llm_config
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
        self._history_manager = history_manager
        self._tool_confirmation = tool_confirmation
        self._yolo = yolo
        self._summarize_command = summarize_command
        self._ui_greeting = ui_greeting
        self._render_ui_greeting = render_ui_greeting
        self._ui_assistant_name = ui_assistant_name
        self._render_ui_assistant_name = render_ui_assistant_name
        self._ui_jargon = ui_jargon
        self._render_ui_jargon = render_ui_jargon
        self._triggers = triggers
        self._confirmation_middlewares = confirmation_middlewares

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

    def add_history_processors(self, *processor: "HistoryProcessor"):
        self.append_history_processors(*processor)

    def append_history_processors(self, *processor: "HistoryProcessor"):
        self._history_processors += list(processor)

    async def _exec_action(self, ctx: AnyContext) -> Any:
        from zrb.builtin.pollux.app.lexer import CLIStyleLexer
        from zrb.builtin.pollux.app.ui import UI

        initial_conversation_name = self._get_conversation_name(ctx)
        initial_yolo = get_bool_attr(ctx, self._yolo, False)
        initial_message = get_attr(ctx, self._message, "", self._render_message)
        initial_attachments = get_attachments(ctx, self._attachment)
        ui_greeting = get_str_attr(ctx, self._ui_greeting, "", self._render_ui_greeting)
        ui_assistant_name = get_str_attr(
            ctx, self._ui_assistant_name, "", self._render_ui_assistant_name
        )
        ui_jargon = get_str_attr(ctx, self._ui_jargon, "", self._render_ui_jargon)

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
            llm_config=self._llm_config,
            llm_limitter=self._llm_limitter,
            tools=self._tools,
            toolsets=self._toolsets,
            history_processors=self._history_processors,
            model=self._model,
            render_model=self._render_model,
            model_settings=self._model_settings,
            history_manager=self._history_manager,
            message="{ctx.input.message}",
            conversation_name="{ctx.input.session}",
            yolo="{ctx.input.yolo}",
            attachment=lambda ctx: ctx.input.attachments,
            summarize_command=self._summarize_command,
        )
        ui = UI(
            greeting=ui_greeting,
            assistant_name=ui_assistant_name,
            jargon=ui_jargon,
            output_lexer=CLIStyleLexer(),
            llm_task=llm_task_core,
            initial_message=initial_message,
            initial_attachments=initial_attachments,
            conversation_session_name=initial_conversation_name,
            yolo=initial_yolo,
            triggers=self._triggers,
            confirmation_middlewares=self._confirmation_middlewares,
        )
        return await ui.run_async()

    def _get_conversation_name(self, ctx: AnyContext) -> str:
        conversation_name = str(
            get_attr(ctx, self._conversation_name, "", self._render_conversation_name)
        )
        if conversation_name.strip() == "":
            conversation_name = get_random_name()
        return conversation_name
