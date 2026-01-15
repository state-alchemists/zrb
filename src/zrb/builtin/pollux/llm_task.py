from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from zrb.attr.type import BoolAttr, StrAttr, fstring
from zrb.builtin.pollux.history_manager import AnyHistoryManager, FileHistoryManager
from zrb.builtin.pollux.util.stream_response import (
    create_event_handler,
    create_faint_printer,
)
from zrb.config.llm_config import LLMConfig
from zrb.config.llm_config import llm_config as default_llm_config
from zrb.config.llm_rate_limitter import LLMRateLimitter
from zrb.config.llm_rate_limitter import llm_rate_limitter as default_llm_rate_limitter
from zrb.context.any_context import AnyContext
from zrb.context.print_fn import PrintFn
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.task.any_task import AnyTask
from zrb.task.base_task import BaseTask
from zrb.util.attr import get_attr, get_bool_attr

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
        llm_config: LLMConfig | None = None,
        llm_rate_limitter: LLMRateLimitter | None = None,
        model: (
            "Callable[[AnyContext], Model | str | fstring | None] | Model | None"
        ) = None,
        render_model: bool = True,
        model_settings: (
            "ModelSettings | Callable[[AnyContext], ModelSettings] | None"
        ) = None,
        small_model: (
            "Callable[[AnyContext], Model | str | fstring | None] | Model | None"
        ) = None,
        render_small_model: bool = True,
        small_model_settings: (
            "ModelSettings | Callable[[AnyContext], ModelSettings] | None"
        ) = None,
        conversation_name: StrAttr | None = None,
        render_conversation_name: bool = True,
        history_manager: AnyHistoryManager | None = None,
        deferred_tool_results: Any = None,
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
        self._llm_rate_limitter = (
            default_llm_rate_limitter
            if llm_rate_limitter is None
            else llm_rate_limitter
        )
        self._system_prompt = system_prompt
        self._render_system_prompt = render_system_prompt
        self._tools = tools
        self._toolsets = toolsets
        self._message = message
        self._render_message = render_message
        self._model = model
        self._render_model = render_model
        self._model_settings = model_settings
        self._small_model = small_model
        self._render_small_model = render_small_model
        self._small_model_settings = small_model_settings
        self._conversation_name = conversation_name
        self._render_conversation_name = render_conversation_name
        self._history_manager = (
            FileHistoryManager(history_dir="~/.llm_chat")
            if history_manager is None
            else history_manager
        )
        self._deferred_tool_results = deferred_tool_results
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
        from pydantic_ai import (
            AgentRunResultEvent,
            DeferredToolRequests,
        )

        conversation_name = str(
            get_attr(
                ctx, self._conversation_name, "default", self._render_conversation_name
            )
        )
        message_history = self._history_manager.load(conversation_name)

        # Resolve deferred_tool_results
        deferred_tool_results = get_attr(ctx, self._deferred_tool_results, None)

        # Get message or request via helper
        run_message_or_request = self._get_user_message(
            ctx, message_history, deferred_tool_results
        )

        if isinstance(run_message_or_request, DeferredToolRequests):
            return run_message_or_request

        run_message = run_message_or_request

        system_prompt = str(
            get_attr(ctx, self._system_prompt, "", self._render_system_prompt)
        )
        yolo = get_attr(ctx, self._yolo, False)
        if isinstance(yolo, str):
            yolo = yolo.lower() == "true"

        agent = self._create_agent(
            ctx=ctx,
            system_prompt=system_prompt,
            tools=self._tools,
            toolsets=self._toolsets,
            yolo=yolo,
        )
        print_event = create_faint_printer(ctx)
        handle_event = create_event_handler(print_event)
        result = None
        async for event in agent.run_stream_events(
            run_message,
            message_history=message_history,
            deferred_tool_results=deferred_tool_results,
        ):
            if isinstance(event, AgentRunResultEvent):
                result = event.result
                new_message_history = result.all_messages()
                self._history_manager.update(conversation_name, new_message_history)
                self._history_manager.save(conversation_name)
                ctx.log_debug(f"All messages: {result.all_messages()}")
            else:
                await handle_event(event)

        output = result.output if result else None
        return output

    def _get_user_message(
        self, ctx: AnyContext, message_history: list[Any], deferred_tool_results: Any
    ) -> Any:
        from pydantic_ai import DeferredToolRequests, ToolCallPart

        # If resuming with results, we pass None as message
        if deferred_tool_results:
            return None

        # Otherwise, resolve the configured message
        message = get_attr(ctx, self._message, "", self._render_message)

        # RECOVERY LOGIC: Check if history is in a pending state
        if message_history:
            last_msg = message_history[-1]
            pending_calls = []
            if hasattr(last_msg, "parts"):
                for part in last_msg.parts:
                    if isinstance(part, ToolCallPart):
                        pending_calls.append(part)

            if pending_calls:
                # We have pending calls. Return DeferredToolRequests to trigger UI approval flow.
                # Use calls=pending_calls assuming pydantic_ai expects pending requests in calls list for DeferredToolRequests
                # Or approvals list?
                # For output of agent (requesting approval), usually calls list.
                # Let's try populating both or check DeferredToolRequests signature.
                # Standard is calls=[ToolCallPart...]
                try:
                    req = DeferredToolRequests(approvals=pending_calls)
                except:
                    # Fallback
                    req = DeferredToolRequests(calls=pending_calls)
                    if hasattr(req, "approvals") and not req.approvals:
                        req.approvals.extend(pending_calls)

                return req

        return message

    def _create_agent(
        self,
        ctx: AnyContext,
        output_type: "OutputSpec[OutputDataT]" = str,
        system_prompt: str = "",
        history_processors: list["HistoryProcessor"] | None = None,
        tools: list["Tool | ToolFuncEither"] = [],
        toolsets: list["AbstractToolset[None]"] = [],
        retries: int = 1,
        is_small: bool = False,
        yolo: bool = False,
    ) -> "Agent[None, Any]":
        from pydantic_ai import Agent, DeferredToolRequests
        from pydantic_ai.toolsets import FunctionToolset

        final_output_type = output_type
        # Copy to avoid modifying original list
        effective_toolsets = list(toolsets)
        # If we have individual tools, wrap them in a toolset
        # so we can apply approval_required globally
        if tools:
            effective_toolsets.append(FunctionToolset(tools=tools))
        if not yolo:
            final_output_type = output_type | DeferredToolRequests
            # Wrap all toolsets with native approval mechanism
            effective_toolsets = [ts.approval_required() for ts in effective_toolsets]
        return Agent(
            model=self._get_model(ctx, is_small),
            output_type=final_output_type,
            instructions=system_prompt,
            toolsets=effective_toolsets,
            model_settings=self._get_model_settings(ctx, is_small),
            history_processors=history_processors,
            retries=retries,
        )

    def _get_model_settings(
        self,
        ctx: AnyContext,
        is_small: bool = False,
    ) -> "ModelSettings | None":
        model_settings = (
            self._small_model_settings if is_small else self._model_settings
        )
        rendered_model_settings = get_attr(ctx, model_settings, None)
        if rendered_model_settings is not None:
            return rendered_model_settings
        if is_small:
            return self._llm_config.default_small_model_settings
        return self._llm_config.default_model_settings

    def _get_model(
        self,
        ctx: AnyContext,
        render_model: bool,
        is_small: bool = False,
    ) -> "str | Model":
        model = self._small_model if is_small else self._model
        rendered_model = get_attr(ctx, model, None, auto_render=render_model)
        if rendered_model is not None:
            return rendered_model
        if is_small:
            return self._llm_config.default_small_model
        return self._llm_config.default_model
