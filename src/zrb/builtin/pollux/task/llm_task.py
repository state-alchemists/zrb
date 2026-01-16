from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from zrb.attr.type import BoolAttr, StrAttr, fstring
from zrb.builtin.pollux.agent import create_agent, run_agent
from zrb.builtin.pollux.config.config import LLMConfig
from zrb.builtin.pollux.config.config import llm_config as default_llm_config
from zrb.builtin.pollux.config.limiter import LLMLimiter
from zrb.builtin.pollux.config.limiter import llm_limiter as default_llm_limitter
from zrb.builtin.pollux.history_manager import AnyHistoryManager, FileHistoryManager
from zrb.builtin.pollux.util.stream_response import (
    create_event_handler,
    create_faint_printer,
)
from zrb.context.any_context import AnyContext
from zrb.context.print_fn import PrintFn
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.task.any_task import AnyTask
from zrb.task.base_task import BaseTask
from zrb.util.attr import get_attr, get_bool_attr
from zrb.util.string.name import get_random_name

if TYPE_CHECKING:
    from pydantic_ai import Agent, Tool
    from pydantic_ai._agent_graph import HistoryProcessor
    from pydantic_ai.models import Model
    from pydantic_ai.output import OutputDataT, OutputSpec
    from pydantic_ai.settings import ModelSettings
    from pydantic_ai.tools import ToolFuncEither
    from pydantic_ai.toolsets import AbstractToolset


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
        system_prompt: StrAttr | None = None,
        render_system_prompt: bool = False,
        tools: list["Tool | ToolFuncEither"] = [],
        toolsets: list["AbstractToolset[None]"] = [],
        message: StrAttr | None = None,
        render_message: bool = True,
        history_processors: list["HistoryProcessor"] | None = None,
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
        deferred_tool_results: Any = None,
        return_deferred_tool_call: BoolAttr = True,
        yolo: BoolAttr = False,
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
        self._system_prompt = system_prompt
        self._render_system_prompt = render_system_prompt
        self._tools = tools
        self._toolsets = toolsets
        self._message = message
        self._render_message = render_message
        self._history_processors = history_processors
        self._model = model
        self._render_model = render_model
        self._model_settings = model_settings
        self._conversation_name = conversation_name
        self._render_conversation_name = render_conversation_name
        self._history_manager = (
            FileHistoryManager(history_dir="~/.llm_chat")
            if history_manager is None
            else history_manager
        )
        self._deferred_tool_results = deferred_tool_results
        self._return_deferred_tool_call = return_deferred_tool_call
        self._yolo = yolo

    def add_toolset(self, *toolset: "AbstractToolset"):
        self.append_toolset(*toolset)

    def append_toolset(self, *toolset: "AbstractToolset"):
        self._toolsets += list(toolset)

    def add_tool(self, *tool: "Tool | ToolFuncEither"):
        self.append_tool(*tool)

    def append_tool(self, *tool: "Tool | ToolFuncEither"):
        tools = [single_tool for single_tool in tool]
        self._tools += tools

    async def _exec_action(self, ctx: AnyContext) -> Any:
        from pydantic_ai import DeferredToolRequests

        conversation_name = self._get_conversation_name(ctx)
        message_history = self._history_manager.load(conversation_name)

        deferred_tool_results = get_attr(ctx, self._deferred_tool_results, None)

        run_message_or_request = self._get_user_message(
            ctx, message_history, deferred_tool_results
        )
        if isinstance(run_message_or_request, DeferredToolRequests):
            return run_message_or_request

        run_message = run_message_or_request

        system_prompt = str(
            get_attr(ctx, self._system_prompt, "", self._render_system_prompt)
        )
        yolo = get_bool_attr(ctx, self._yolo, False)

        agent = create_agent(
            model=self._get_model(ctx),
            system_prompt=system_prompt,
            tools=self._tools,
            toolsets=self._toolsets,
            model_settings=self._get_model_settings(ctx),
            history_processors=self._history_processors,
            yolo=yolo,
        )

        print_event = create_faint_printer(ctx)
        handle_event = create_event_handler(print_event)

        return_deferred = get_bool_attr(ctx, self._return_deferred_tool_call, True)

        output, new_history = await run_agent(
            agent=agent,
            message=run_message,
            message_history=message_history,
            deferred_tool_results=deferred_tool_results,
            limiter=self._llm_limitter,
            print_fn=ctx.print,
            event_handler=handle_event,
            return_deferred_tool_call=return_deferred,
        )

        self._history_manager.update(conversation_name, new_history)
        self._history_manager.save(conversation_name)
        ctx.log_debug(f"All messages: {new_history}")

        return output

    def _get_conversation_name(self, ctx: AnyContext) -> str:
        conversation_name = str(
            get_attr(ctx, self._conversation_name, "", self._render_conversation_name)
        )
        if conversation_name.strip() == "":
            conversation_name = get_random_name()
        return conversation_name

    def _get_user_message(
        self, ctx: AnyContext, message_history: list[Any], deferred_tool_results: Any
    ) -> Any:
        from pydantic_ai import DeferredToolRequests, ToolCallPart

        if deferred_tool_results:
            return None

        if message_history:
            last_msg = message_history[-1]
            pending_calls = []
            if hasattr(last_msg, "parts"):
                for part in last_msg.parts:
                    if isinstance(part, ToolCallPart):
                        pending_calls.append(part)
            if pending_calls:
                try:
                    req = DeferredToolRequests(approvals=pending_calls)
                except Exception:
                    req = DeferredToolRequests(calls=pending_calls)
                    if hasattr(req, "approvals") and not req.approvals:
                        req.approvals.extend(pending_calls)
                return req

        message = get_attr(ctx, self._message, "", self._render_message)
        return message

    def _get_model_settings(
        self,
        ctx: AnyContext,
    ) -> "ModelSettings | None":
        model_settings = self._model_settings
        rendered_model_settings = get_attr(ctx, model_settings, None)
        if rendered_model_settings is not None:
            return rendered_model_settings
        return self._llm_config.model_settings

    def _get_model(
        self,
        ctx: AnyContext,
    ) -> "str | Model":
        model = self._model
        rendered_model = get_attr(ctx, model, None, auto_render=self._render_model)
        if rendered_model is not None:
            return rendered_model
        return self._llm_config.model
