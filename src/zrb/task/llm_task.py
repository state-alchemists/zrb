import json
import os
from collections.abc import Callable
from typing import Any

from pydantic_ai import Agent, Tool
from pydantic_ai.messages import (
    FinalResultEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelMessagesTypeAdapter,
    PartDeltaEvent,
    PartStartEvent,
    TextPartDelta,
    ToolCallPartDelta,
)
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings

from zrb.attr.type import StrAttr, fstring
from zrb.config import LLM_MODEL, LLM_SYSTEM_PROMPT
from zrb.context.any_context import AnyContext
from zrb.context.any_shared_context import AnySharedContext
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.task.any_task import AnyTask
from zrb.task.base_task import BaseTask
from zrb.util.attr import get_attr, get_str_attr
from zrb.util.cli.style import stylize_faint
from zrb.util.file import read_file, write_file
from zrb.util.run import run_async

ListOfDict = list[dict[str, Any]]
ToolOrCallable = Tool | Callable


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
        model: (
            Callable[[AnySharedContext], Model | str | fstring] | Model | None
        ) = LLM_MODEL,
        model_settings: (
            ModelSettings | Callable[[AnySharedContext], ModelSettings] | None
        ) = None,
        render_model: bool = True,
        agent: Agent | Callable[[AnySharedContext], Agent] | None = None,
        system_prompt: StrAttr | None = LLM_SYSTEM_PROMPT,
        render_system_prompt: bool = True,
        message: StrAttr | None = None,
        tools: (
            list[ToolOrCallable] | Callable[[AnySharedContext], list[ToolOrCallable]]
        ) = [],
        conversation_history: (
            ListOfDict | Callable[[AnySharedContext], ListOfDict]
        ) = [],
        conversation_history_reader: (
            Callable[[AnySharedContext], ListOfDict] | None
        ) = None,
        conversation_history_writer: (
            Callable[[AnySharedContext, ListOfDict], None] | None
        ) = None,
        conversation_history_file: StrAttr | None = None,
        render_history_file: bool = True,
        execute_condition: bool | str | Callable[[AnySharedContext], bool] = True,
        retries: int = 2,
        retry_period: float = 0,
        readiness_check: list[AnyTask] | AnyTask | None = None,
        readiness_check_delay: float = 0.5,
        readiness_check_period: float = 5,
        readiness_failure_threshold: int = 1,
        readiness_timeout: int = 60,
        monitor_readiness: bool = False,
        max_call_iteration: int = 20,
        upstream: list[AnyTask] | AnyTask | None = None,
        fallback: list[AnyTask] | AnyTask | None = None,
        successor: list[AnyTask] | AnyTask | None = None,
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
        )
        self._model = model
        self._model_settings = model_settings
        self._agent = agent
        self._render_model = render_model
        self._system_prompt = system_prompt
        self._render_system_prompt = render_system_prompt
        self._message = message
        self._tools = tools
        self._additional_tools: list[ToolOrCallable] = []
        self._conversation_history = conversation_history
        self._conversation_history_reader = conversation_history_reader
        self._conversation_history_writer = conversation_history_writer
        self._conversation_history_file = conversation_history_file
        self._render_history_file = render_history_file
        self._max_call_iteration = max_call_iteration

    def set_model(self, model: Model | str):
        self._model = model

    def add_tool(self, tool: ToolOrCallable):
        self._additional_tools.append(tool)

    async def _exec_action(self, ctx: AnyContext) -> Any:
        history = await self._read_conversation_history(ctx)
        user_prompt = self._get_message(ctx)
        agent = self._get_agent(ctx)
        async with agent.iter(
            user_prompt=user_prompt,
            message_history=ModelMessagesTypeAdapter.validate_python(history),
        ) as agent_run:
            async for node in agent_run:
                # Each node represents a step in the agent's execution
                await self._print_node(ctx, agent_run, node)
        new_history = json.loads(agent_run.result.all_messages_json())
        await self._write_conversation_history(ctx, new_history)
        return agent_run.result.data

    async def _print_node(self, ctx: AnyContext, agent_run: Any, node: Any):
        if Agent.is_user_prompt_node(node):
            # A user prompt node => The user has provided input
            ctx.print(stylize_faint(f">> UserPromptNode: {node.user_prompt}"))
        elif Agent.is_model_request_node(node):
            # A model request node => We can stream tokens from the model"s request
            ctx.print(
                stylize_faint(">> ModelRequestNode: streaming partial request tokens")
            )
            async with node.stream(agent_run.ctx) as request_stream:
                is_streaming = False
                async for event in request_stream:
                    if isinstance(event, PartStartEvent):
                        if is_streaming:
                            ctx.print("", plain=True)
                        ctx.print(
                            stylize_faint(
                                f"[Request] Starting part {event.index}: {event.part!r}"
                            ),
                        )
                        is_streaming = False
                    elif isinstance(event, PartDeltaEvent):
                        if isinstance(event.delta, TextPartDelta):
                            ctx.print(
                                stylize_faint(f"{event.delta.content_delta}"),
                                end="",
                                plain=is_streaming,
                            )
                        elif isinstance(event.delta, ToolCallPartDelta):
                            ctx.print(
                                stylize_faint(f"{event.delta.args_delta}"),
                                end="",
                                plain=is_streaming,
                            )
                        is_streaming = True
                    elif isinstance(event, FinalResultEvent):
                        if is_streaming:
                            ctx.print("", plain=True)
                        ctx.print(
                            stylize_faint(f"[Result] tool_name={event.tool_name}"),
                        )
                        is_streaming = False
                if is_streaming:
                    ctx.print("", plain=True)
        elif Agent.is_call_tools_node(node):
            # A handle-response node => The model returned some data, potentially calls a tool
            ctx.print(
                stylize_faint(
                    ">> CallToolsNode: streaming partial response & tool usage"
                )
            )
            async with node.stream(agent_run.ctx) as handle_stream:
                async for event in handle_stream:
                    if isinstance(event, FunctionToolCallEvent):
                        ctx.print(
                            stylize_faint(
                                f"[Tools] The LLM calls tool={event.part.tool_name!r} with args={event.part.args} (tool_call_id={event.part.tool_call_id!r})"  # noqa
                            )
                        )
                    elif isinstance(event, FunctionToolResultEvent):
                        ctx.print(
                            stylize_faint(
                                f"[Tools] Tool call {event.tool_call_id!r} returned => {event.result.content}"  # noqa
                            )
                        )
        elif Agent.is_end_node(node):
            # Once an End node is reached, the agent run is complete
            ctx.print(stylize_faint(f"{agent_run.result.data}"))

    async def _write_conversation_history(
        self, ctx: AnyContext, conversations: list[Any]
    ):
        if self._conversation_history_writer is not None:
            await run_async(self._conversation_history_writer(ctx, conversations))
        history_file = self._get_history_file(ctx)
        if history_file != "":
            write_file(history_file, json.dumps(conversations, indent=2))

    def _get_model_settings(self, ctx: AnyContext) -> ModelSettings | None:
        if callable(self._model_settings):
            return self._model_settings(ctx)
        return self._model_settings

    def _get_agent(self, ctx: AnyContext) -> Agent:
        if isinstance(self._agent, Agent):
            return self._agent
        if callable(self._agent):
            return self._agent(ctx)
        tools_or_callables = list(
            self._tools(ctx) if callable(self._tools) else self._tools
        )
        tools_or_callables.extend(self._additional_tools)
        tools = [
            tool if isinstance(tool, Tool) else Tool(tool, takes_ctx=False)
            for tool in tools_or_callables
        ]
        return Agent(
            self._get_model(ctx),
            system_prompt=self._get_system_prompt(ctx),
            tools=tools,
            model_settings=self._get_model_settings(ctx),
        )

    def _get_model(self, ctx: AnyContext) -> str | Model | None:
        model = get_attr(
            ctx, self._model, "ollama_chat/llama3.1", auto_render=self._render_model
        )
        if isinstance(model, (Model, str)) or model is None:
            return model
        raise ValueError("Invalid model")

    def _get_system_prompt(self, ctx: AnyContext) -> str:
        return get_str_attr(
            ctx,
            self._system_prompt,
            "You are a helpful assistant",
            auto_render=self._render_system_prompt,
        )

    def _get_message(self, ctx: AnyContext) -> str:
        return get_str_attr(ctx, self._message, "How are you?", auto_render=True)

    async def _read_conversation_history(self, ctx: AnyContext) -> ListOfDict:
        if self._conversation_history_reader is not None:
            return await run_async(self._conversation_history_reader(ctx))
        if callable(self._conversation_history):
            return self._conversation_history(ctx)
        history_file = self._get_history_file(ctx)
        if (
            len(self._conversation_history) == 0
            and history_file != ""
            and os.path.isfile(history_file)
        ):
            return json.loads(read_file(history_file))
        return self._conversation_history

    def _get_history_file(self, ctx: AnyContext) -> str:
        return get_str_attr(
            ctx,
            self._conversation_history_file,
            "",
            auto_render=self._render_history_file,
        )
