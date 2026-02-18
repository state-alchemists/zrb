from __future__ import annotations

import re
import warnings
from typing import TYPE_CHECKING, Any, Callable

from zrb.attr.type import BoolAttr, StrAttr, StrListAttr, fstring
from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.context.print_fn import PrintFn
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.llm.agent import AnyToolConfirmation, create_agent, run_agent
from zrb.llm.config.config import LLMConfig
from zrb.llm.config.config import llm_config as default_llm_config
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.config.limiter import llm_limiter as default_llm_limitter
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.history_manager.file_history_manager import FileHistoryManager
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.manager import hook_manager as default_hook_manager
from zrb.llm.prompt.manager import PromptManager
from zrb.llm.summarizer import (
    summarize_history,
)
from zrb.llm.util.attachment import get_attachments
from zrb.llm.util.stream_response import (
    create_event_handler,
    create_faint_printer,
)
from zrb.task.any_task import AnyTask
from zrb.task.base_task import BaseTask
from zrb.util.attr import get_attr, get_bool_attr, get_str_list_attr
from zrb.util.cli.style import remove_style
from zrb.util.string.name import get_random_name
from zrb.util.string.thinking import remove_thinking_tags

if TYPE_CHECKING:
    from pydantic_ai import Tool, UserContent
    from pydantic_ai._agent_graph import HistoryProcessor
    from pydantic_ai.models import Model
    from pydantic_ai.settings import ModelSettings
    from pydantic_ai.tools import ToolFuncEither
    from pydantic_ai.toolsets import AbstractToolset

    from zrb.llm.tool_call.ui_protocol import UIProtocol


class LLMTask(BaseTask):

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
        hook_manager: HookManager | None = None,
        active_skills: StrListAttr | None = None,
        render_active_skills: bool = True,
        tools: list[Tool | ToolFuncEither] = [],
        toolsets: list[AbstractToolset[None]] = [],
        message: StrAttr | None = None,
        render_message: bool = True,
        attachment: (
            UserContent
            | list[UserContent]
            | Callable[[AnyContext], UserContent | list[UserContent]]
            | None
        ) = None,  # noqa
        history_processors: list[HistoryProcessor] = [],
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
        yolo: BoolAttr = False,
        dynamic_yolo: Callable[..., bool] | None = None,
        summarize_command: list[str] = [],
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
        self._llm_config = default_llm_config if llm_config is None else llm_config
        self._llm_limitter = (
            default_llm_limitter if llm_limitter is None else llm_limitter
        )
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
        self._system_prompt = system_prompt
        self._render_system_prompt = render_system_prompt
        self._prompt_manager = prompt_manager
        self._hook_manager = (
            default_hook_manager if hook_manager is None else hook_manager
        )
        self._active_skills = active_skills
        self._render_active_skills = render_active_skills
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
        self._ui = ui
        self._yolo = yolo
        self._dynamic_yolo = dynamic_yolo
        self._summarize_command = summarize_command

    @property
    def prompt_manager(self) -> PromptManager:
        if self._prompt_manager is None:
            raise ValueError(f"Task {self.name} doesn't have prompt_manager")
        return self._prompt_manager

    def set_ui(self, ui: UIProtocol | None):
        self._ui = ui

    @property
    def tool_confirmation(self) -> AnyToolConfirmation:
        return self._tool_confirmation

    @tool_confirmation.setter
    def tool_confirmation(self, value: AnyToolConfirmation):
        self._tool_confirmation = value

    def add_toolset(self, *toolset: AbstractToolset):
        self.append_toolset(*toolset)

    def append_toolset(self, *toolset: AbstractToolset):
        self._toolsets += list(toolset)

    def add_tool(self, *tool: Tool | ToolFuncEither):
        self.append_tool(*tool)

    def append_tool(self, *tool: Tool | ToolFuncEither):
        self._tools += list(tool)

    def add_history_processor(self, *processor: HistoryProcessor):
        self.append_history_processor(*processor)

    def append_history_processor(self, *processor: HistoryProcessor):
        self._history_processors += list(processor)

    async def _exec_action(self, ctx: AnyContext) -> Any:
        conversation_name = self._get_conversation_name(ctx)
        history_manager = self._get_history_manager(ctx)
        message_history = history_manager.load(conversation_name)
        user_message = get_attr(ctx, self._message, "", self._render_message)
        user_attachments = get_attachments(ctx, self._attachment)

        if await self._should_summarize(
            ctx, history_manager, conversation_name, user_message, message_history
        ):
            return "Conversation history compressed."

        agent = self._create_agent(ctx)
        handle_event = self._create_event_handler(ctx)
        effective_message, effective_attachments = self._get_effective_prompt(
            ctx, user_message, user_attachments, message_history
        )

        try:
            output, new_history = await run_agent(
                agent=agent,
                message=effective_message,
                message_history=message_history,
                limiter=self._llm_limitter,
                attachments=effective_attachments,
                print_fn=lambda *args, **kwargs: ctx.print(*args, **kwargs, plain=True),
                event_handler=handle_event,
                tool_confirmation=self._tool_confirmation,
                hook_manager=self._hook_manager,
                ui=self._ui,
            )
        except Exception as e:
            self._handle_run_error(ctx, history_manager, conversation_name, e)
            raise e

        history_manager.update(conversation_name, new_history)
        history_manager.save(conversation_name)
        ctx.log_debug(f"All messages: {new_history}")

        return self._post_process_output(output)

    def _get_history_manager(self, ctx: AnyContext) -> AnyHistoryManager:
        if self._history_manager is not None:
            return self._history_manager
        return FileHistoryManager(history_dir=CFG.LLM_HISTORY_DIR)

    async def _should_summarize(
        self,
        ctx: AnyContext,
        history_manager: AnyHistoryManager,
        conversation_name: str,
        user_message: Any,
        message_history: list[Any],
    ) -> bool:
        if (
            isinstance(user_message, str)
            and user_message.strip() in self._summarize_command
        ):
            ctx.print("Compressing conversation history...", plain=True)
            new_history = await summarize_history(message_history)
            history_manager.update(conversation_name, new_history)
            history_manager.save(conversation_name)
            return True
        return False

    def _create_agent(self, ctx: AnyContext) -> Any:
        yolo = (
            self._dynamic_yolo
            if self._dynamic_yolo is not None
            else get_bool_attr(ctx, self._yolo, False)
        )
        system_prompt = self._get_system_prompt(ctx)
        ctx.log_debug(f"SYSTEM PROMPT: {system_prompt}")
        return create_agent(
            model=self._get_model(ctx),
            system_prompt=system_prompt,
            tools=self._tools,
            toolsets=self._toolsets,
            model_settings=self._get_model_settings(ctx),
            history_processors=self._history_processors,
            yolo=yolo,
        )

    def _create_event_handler(self, ctx: AnyContext) -> Any:
        print_event = create_faint_printer(ctx.shared_print)
        return create_event_handler(
            print_event,
            show_tool_call_detail=CFG.LLM_SHOW_TOOL_CALL_DETAIL,
            show_tool_result=CFG.LLM_SHOW_TOOL_CALL_RESULT,
        )

    def _get_effective_prompt(
        self,
        ctx: AnyContext,
        user_message: str,
        user_attachments: list[Any] | None,
        message_history: list[Any],
    ) -> tuple[str, list[Any] | None]:
        # Detect retry and avoid duplicating the initial message if it's already in history
        # Also, if it's a retry, we might want to inform the LLM about the previous failure.
        if ctx.attempt > 1 and len(message_history) > 0:
            from pydantic_ai.messages import ModelRequest, UserPromptPart

            # Check if the last message (or one of the last few) is the user message
            found_user_message = False
            str_user_message = str(user_message)
            for msg in reversed(message_history):
                if isinstance(msg, ModelRequest):
                    for part in msg.parts:
                        if (
                            isinstance(part, UserPromptPart)
                            and str(part.content) == str_user_message
                        ):
                            found_user_message = True
                            break
                if found_user_message:
                    break

            if found_user_message:
                # User message is already in history, so we don't need to send it again.
                # Instead, we send a retry notice.
                ctx.log_info("Initial message found in history, sending retry notice.")
                return (
                    f"[System] This is retry attempt {ctx.attempt}. "
                    "The previous attempt failed. Please review the history and continue.",
                    None,
                )
        return user_message, user_attachments

    def _handle_run_error(
        self,
        ctx: AnyContext,
        history_manager: AnyHistoryManager,
        conversation_name: str,
        error: Exception,
    ):
        from pydantic_ai.messages import (
            ModelRequest,
            ModelResponse,
            ToolCallPart,
            ToolReturnPart,
            UserPromptPart,
        )

        new_history = getattr(error, "zrb_history", None)
        if new_history is None:
            return
        # Append error information to history so it's available on next retry
        # 1. Handle dangling tool calls if necessary
        if len(new_history) > 0:
            last_msg = new_history[-1]
            if isinstance(last_msg, ModelResponse):
                tool_returns = []
                for part in last_msg.parts:
                    if isinstance(part, ToolCallPart):
                        tool_returns.append(
                            ToolReturnPart(
                                tool_name=part.tool_name,
                                content=f"Error: {str(error)}",
                                tool_call_id=part.tool_call_id,
                            )
                        )
                if tool_returns:
                    new_history.append(ModelRequest(parts=tool_returns))

        # 2. Append general error information
        error_msg = f"[System] Error occurred: {str(error)}"
        new_history.append(ModelRequest(parts=[UserPromptPart(content=error_msg)]))
        history_manager.update(conversation_name, new_history)
        history_manager.save(conversation_name)

    def _post_process_output(self, output: Any) -> Any:
        if isinstance(output, str):
            # Remove ANSI escape codes first to ensure regex patterns work correctly
            output = remove_style(output)
            # Remove thinking/thought tags with proper nesting handling
            output = remove_thinking_tags(output)
        return output

    def _get_system_prompt(self, ctx: AnyContext) -> str:
        if self._prompt_manager is None:
            return ""
        compose_prompt = self._prompt_manager.compose_prompt()
        return compose_prompt(ctx)

    def _get_conversation_name(self, ctx: AnyContext) -> str:
        conversation_name = str(
            get_attr(ctx, self._conversation_name, "", self._render_conversation_name)
        )
        if conversation_name.strip() == "":
            conversation_name = get_random_name()
        return conversation_name

    def _get_model_settings(self, ctx: AnyContext) -> ModelSettings | None:
        model_settings = self._model_settings
        rendered_model_settings = get_attr(ctx, model_settings, None)
        if rendered_model_settings is not None:
            return rendered_model_settings
        return self._llm_config.model_settings

    def _get_model(self, ctx: AnyContext) -> str | Model:
        model = self._model
        rendered_model = get_attr(ctx, model, None, auto_render=self._render_model)
        if isinstance(rendered_model, str) and rendered_model.strip() == "":
            rendered_model = None
        if rendered_model is not None:
            return rendered_model
        return self._llm_config.model
