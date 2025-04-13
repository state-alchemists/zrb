import inspect
import json
from collections.abc import Callable
from typing import Any

from openai import APIError
from pydantic_ai import Agent, Tool
from pydantic_ai.mcp import MCPServer
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
from zrb.context.any_context import AnyContext
from zrb.context.any_shared_context import AnySharedContext
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.llm_config import LLMConfig
from zrb.llm_config import llm_config as default_llm_config
from zrb.task.any_task import AnyTask
from zrb.task.base_task import BaseTask
from zrb.task.llm.error import extract_api_error_details
from zrb.task.llm.history import ConversationHistoryData
from zrb.task.llm.tool_wrapper import wrap_tool
from zrb.util.attr import get_attr, get_str_attr
from zrb.util.cli.style import stylize_faint
from zrb.util.file import write_file
from zrb.util.run import run_async

ListOfDict = list[dict[str, Any]]
# Removed old ConversationHistoryData type alias
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
        ) = None,
        render_model: bool = True,
        model_base_url: StrAttr | None = None,
        render_model_base_url: bool = True,
        model_api_key: StrAttr | None = None,
        render_model_api_key: bool = True,
        model_settings: (
            ModelSettings | Callable[[AnySharedContext], ModelSettings] | None
        ) = None,
        agent: Agent | Callable[[AnySharedContext], Agent] | None = None,
        system_prompt: StrAttr | None = None,
        render_system_prompt: bool = True,
        message: StrAttr | None = None,
        tools: (
            list[ToolOrCallable] | Callable[[AnySharedContext], list[ToolOrCallable]]
        ) = [],
        mcp_servers: (
            list[MCPServer] | Callable[[AnySharedContext], list[MCPServer]]
        ) = [],
        conversation_history: (
            ConversationHistoryData  # Use the new BaseModel
            | Callable[
                [AnySharedContext], ConversationHistoryData | dict | list
            ]  # Allow returning raw dict/list too
            | dict  # Allow raw dict
            | list  # Allow raw list (old format)
        ) = ConversationHistoryData(),  # Default to an empty model instance
        conversation_history_reader: (
            Callable[[AnySharedContext], ConversationHistoryData | dict | list | None] | None
            # Allow returning raw dict/list or None
        ) = None,
        conversation_history_writer: (
            Callable[[AnySharedContext, ConversationHistoryData], None] | None
            # Writer expects the model instance
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
        conversation_context: (
            dict[str, Any] | Callable[[AnySharedContext], dict[str, Any]] | None
        ) = None,
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
        self._render_model = render_model
        self._model_base_url = model_base_url
        self._render_model_base_url = render_model_base_url
        self._model_api_key = model_api_key
        self._render_model_api_key = render_model_api_key
        self._model_settings = model_settings
        self._agent = agent
        self._system_prompt = system_prompt
        self._render_system_prompt = render_system_prompt
        self._message = message
        self._tools = tools
        self._additional_tools: list[ToolOrCallable] = []
        self._mcp_servers = mcp_servers
        self._additional_mcp_servers: list[MCPServer] = []
        self._conversation_history = conversation_history
        self._conversation_history_reader = conversation_history_reader
        self._conversation_history_writer = conversation_history_writer
        self._conversation_history_file = conversation_history_file
        self._render_history_file = render_history_file
        self._max_call_iteration = max_call_iteration
        self._conversation_context = conversation_context

    def add_tool(self, tool: ToolOrCallable):
        self._additional_tools.append(tool)

    def add_mcp_server(self, mcp_server: MCPServer):
        self._additional_mcp_servers.append(mcp_server)

    async def _exec_action(self, ctx: AnyContext) -> Any:
        history_data: ConversationHistoryData = await self._read_conversation_history(
            ctx
        )  # Now returns the model instance
        history_list = history_data.history  # Access history via attribute
        user_prompt = self._get_message(ctx)
        agent = self._get_agent(ctx)
        try:
            async with agent.run_mcp_servers():
                async with agent.iter(
                    user_prompt=user_prompt,
                    message_history=ModelMessagesTypeAdapter.validate_python(history_list),
                ) as agent_run:
                    async for node in agent_run:
                        # Each node represents a step in the agent's execution
                        # Reference: https://ai.pydantic.dev/agents/#streaming
                        try:
                            await self._print_node(ctx, agent_run, node)
                        except APIError as e:
                            # Extract detailed error information from the response
                            error_details = extract_api_error_details(e)
                            ctx.log_error(f"API Error: {error_details}")
                            raise
                        except Exception as e:
                            ctx.log_error(f"Error processing node: {str(e)}")
                            ctx.log_error(f"Error type: {type(e).__name__}")
                            raise
                    new_history_list = json.loads(agent_run.result.all_messages_json())
                    data_to_write = ConversationHistoryData(
                        context=self._get_conversation_context(ctx),
                        history=new_history_list,
                    )
                    await self._write_conversation_history(
                        ctx, data_to_write
                    )  # Pass the model instance
                    return agent_run.result.data
        except Exception as e:
            ctx.log_error(f"Error in agent execution: {str(e)}")
            raise

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
                        # Handle empty arguments across different providers
                        if event.part.args == "" or event.part.args is None:
                            event.part.args = {}
                        elif isinstance(
                            event.part.args, str
                        ) and event.part.args.strip() in ["null", "{}"]:
                            # Some providers might send "null" or "{}" as a string
                            event.part.args = {}
                        # Handle dummy property if present (from our schema sanitization)
                        if (
                            isinstance(event.part.args, dict)
                            and "_dummy" in event.part.args
                        ):
                            del event.part.args["_dummy"]
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
        self, ctx: AnyContext, history_data: ConversationHistoryData
    ):
        # Expects the model instance
        if self._conversation_history_writer is not None:
            # Pass the model instance directly to the writer
            await run_async(self._conversation_history_writer(ctx, history_data))
        history_file = self._get_history_file(ctx)
        if history_file != "":
            # Use model_dump_json for serialization
            write_file(history_file, history_data.model_dump_json(indent=2))

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
        tools = []
        for tool_or_callable in tools_or_callables:
            if isinstance(tool_or_callable, Tool):
                tools.append(tool_or_callable)
            else:
                # Inspect original callable for 'ctx' parameter
                original_sig = inspect.signature(tool_or_callable)
                takes_ctx = "ctx" in original_sig.parameters
                wrapped_tool = wrap_tool(tool_or_callable)
                tools.append(Tool(wrapped_tool, takes_ctx=takes_ctx))
        mcp_servers = list(
            self._mcp_servers(ctx) if callable(self._mcp_servers) else self._mcp_servers
        )
        mcp_servers.extend(self._additional_mcp_servers)
        return Agent(
            self._get_model(ctx),
            system_prompt=self._get_system_prompt(ctx),
            tools=tools,
            mcp_servers=mcp_servers,
            model_settings=self._get_model_settings(ctx),
            retries=3,
        )

    def _get_model(self, ctx: AnyContext) -> str | Model | None:
        model = get_attr(ctx, self._model, None, auto_render=self._render_model)
        if model is None:
            return default_llm_config.get_default_model()
        if isinstance(model, str):
            model_base_url = self._get_model_base_url(ctx)
            model_api_key = self._get_model_api_key(ctx)
            llm_config = LLMConfig(
                default_model_name=model,
                default_base_url=model_base_url,
                default_api_key=model_api_key,
            )
            if model_base_url is None and model_api_key is None:
                default_model_provider = default_llm_config.get_default_model_provider()
                if default_model_provider is not None:
                    llm_config.set_default_provider(default_model_provider)
            return llm_config.get_default_model()
        raise ValueError(f"Invalid model: {model}")

    def _get_model_base_url(self, ctx: AnyContext) -> str | None:
        base_url = get_attr(
            ctx, self._model_base_url, None, auto_render=self._render_model_base_url
        )
        if isinstance(base_url, str) or base_url is None:
            return base_url
        raise ValueError(f"Invalid model base URL: {base_url}")

    def _get_model_api_key(self, ctx: AnyContext) -> str | None:
        api_key = get_attr(
            ctx, self._model_api_key, None, auto_render=self._render_model_api_key
        )
        if isinstance(api_key, str) or api_key is None:
            return api_key
        raise ValueError(f"Invalid model API key: {api_key}")

    def _get_system_prompt(self, ctx: AnyContext) -> str:
        system_prompt = get_attr(
            ctx,
            self._system_prompt,
            None,
            auto_render=self._render_system_prompt,
        )
        if system_prompt is not None:
            return system_prompt
        return default_llm_config.get_default_system_prompt()

    def _get_message(self, ctx: AnyContext) -> str:
        return get_str_attr(ctx, self._message, "How are you?", auto_render=True)

    async def _read_conversation_history(
        self, ctx: AnyContext
    ) -> ConversationHistoryData:  # Returns the model instance
        """Reads conversation history using the ConversationHistoryData model's logic."""
        history_file = self._get_history_file(ctx)
        # Pass all potential sources to the class method
        return await ConversationHistoryData.read_from_sources(
            ctx=ctx,
            reader=self._conversation_history_reader,
            file_path=history_file,
            attribute_value=self._conversation_history,
            default_value=ConversationHistoryData(),  # Provide the default instance
        )

    def _get_history_file(self, ctx: AnyContext) -> str:
        return get_str_attr(
            ctx,
            self._conversation_history_file,
            "",
            auto_render=self._render_history_file,
        )

    def _get_conversation_context(self, ctx: AnyContext) -> dict[str, Any]:
        """Retrieves the conversation context."""
        context = get_attr(ctx, self._conversation_context, {}, auto_render=False) # Context usually shouldn't be rendered # noqa
        if isinstance(context, dict):
            return context
        ctx.log_warning(
            f"Conversation context resolved to type {type(context)}, expected dict. "
            "Returning empty context."
        )
        return {}
