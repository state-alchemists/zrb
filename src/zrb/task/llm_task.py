import inspect
import json
from collections.abc import Callable
from textwrap import dedent
from typing import Any

from pydantic_ai import Agent, Tool
from pydantic_ai.mcp import MCPServer
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings

from zrb.attr.type import BoolAttr, IntAttr, StrAttr, fstring
from zrb.context.any_context import AnyContext
from zrb.context.any_shared_context import AnySharedContext
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.llm_config import LLMConfig
from zrb.llm_config import llm_config as default_llm_config
from zrb.task.any_task import AnyTask
from zrb.task.base_task import BaseTask
from zrb.task.llm.agent_runner import run_agent_iteration
from zrb.task.llm.context_enricher import EnrichmentConfig, enrich_context
from zrb.task.llm.default_context import get_default_context
from zrb.task.llm.history import ConversationHistoryData, ListOfDict
from zrb.task.llm.history_summarizer import SummarizationConfig, summarize_history
from zrb.task.llm.tool_wrapper import wrap_tool
from zrb.util.attr import get_attr, get_bool_attr, get_int_attr, get_str_attr
from zrb.util.file import write_file
from zrb.util.run import run_async

# ListOfDict moved to history.py
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
        summarization_prompt: StrAttr | None = None,
        render_summarization_prompt: bool = True,
        enrich_context: BoolAttr = False,
        render_enrich_context: bool = True,
        context_enrichment_prompt: StrAttr | None = None,
        render_context_enrichment_prompt: bool = True,
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
            Callable[[AnySharedContext], ConversationHistoryData | dict | list | None]
            | None
            # Allow returning raw dict/list or None
        ) = None,
        conversation_history_writer: (
            Callable[[AnySharedContext, ConversationHistoryData], None]
            | None
            # Writer expects the model instance
        ) = None,
        conversation_history_file: StrAttr | None = None,
        render_history_file: bool = True,
        summarize_history: BoolAttr = True,
        render_summarize_history: bool = True,
        history_summarization_threshold: IntAttr = 5,  # -1 means no summarization trigger
        render_history_summarization_threshold: bool = True,
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
        self._summarization_prompt = summarization_prompt
        self._render_summarization_prompt = render_summarization_prompt
        self._should_enrich_context = enrich_context
        self._render_enrich_context = render_enrich_context
        self._context_enrichment_prompt = context_enrichment_prompt
        self._render_context_enrichment_prompt = render_context_enrichment_prompt
        self._tools = tools
        self._additional_tools: list[ToolOrCallable] = []
        self._mcp_servers = mcp_servers
        self._additional_mcp_servers: list[MCPServer] = []
        self._conversation_history = conversation_history
        self._conversation_history_reader = conversation_history_reader
        self._conversation_history_writer = conversation_history_writer
        self._conversation_history_file = conversation_history_file
        self._render_history_file = render_history_file
        self._should_summarize_history = summarize_history
        self._render_summarize_history = render_summarize_history
        self._history_summarization_threshold = history_summarization_threshold
        self._render_history_summarization_threshold = (
            render_history_summarization_threshold
        )
        self._max_call_iteration = max_call_iteration
        self._conversation_context = conversation_context

    def add_tool(self, tool: ToolOrCallable):
        self._additional_tools.append(tool)

    def add_mcp_server(self, mcp_server: MCPServer):
        self._additional_mcp_servers.append(mcp_server)

    def set_should_enrich_context(self, enrich_context: bool):
        self._should_enrich_context = enrich_context

    def set_should_summarize_history(self, summarize_history: bool):
        self._should_summarize_history = summarize_history

    def set_history_summarization_threshold(self, summarization_threshold: int):
        self._history_summarization_threshold = summarization_threshold

    async def _exec_action(self, ctx: AnyContext) -> Any:
        history_data: ConversationHistoryData = await self._read_conversation_history(
            ctx
        )
        # Extract history list and conversation context
        history_list = history_data.history
        conversation_context = self._get_conversation_context(ctx)
        # Merge history context without overwriting existing keys
        for key, value in history_data.context.items():
            if key not in conversation_context:
                conversation_context[key] = value
        # Enrich context based on history (if enabled)
        if self._get_should_enrich_context(ctx, history_list):
            conversation_context = await enrich_context(
                ctx=ctx,
                config=EnrichmentConfig(
                    model=self._get_model(ctx),
                    settings=self._get_model_settings(ctx),
                    prompt=self._get_context_enrichment_prompt(ctx),
                ),
                conversation_context=conversation_context,
                history_list=history_list,
            )
        # Get history handling parameters
        if self._get_should_summarize_history(ctx, history_list):
            ctx.log_info("Summarize previous conversation")
            # Summarize the part to be removed and update context
            conversation_context = await summarize_history(
                ctx=ctx,
                config=SummarizationConfig(
                    model=self._get_model(ctx),
                    settings=self._get_model_settings(ctx),
                    prompt=self._get_summarization_prompt(ctx),
                ),
                conversation_context=conversation_context,
                history_list=history_list,  # Pass the full list for context
            )
            # Truncate the history list after summarization
            history_list = []
        # Construct user prompt
        user_prompt = self._get_user_prompt(ctx, conversation_context)
        # Create and run agent
        agent = self._get_agent(ctx)
        try:
            agent_run = await run_agent_iteration(
                ctx=ctx,
                agent=agent,
                user_prompt=user_prompt,
                history_list=history_list,
            )
            if agent_run:
                new_history_list = json.loads(agent_run.result.all_messages_json())
                data_to_write = ConversationHistoryData(
                    context=conversation_context,
                    history=new_history_list,
                )
                await self._write_conversation_history(
                    ctx, data_to_write
                )  # Pass the model instance
                return agent_run.result.data
        except Exception as e:
            ctx.log_error(f"Error in agent execution: {str(e)}")
            raise

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
                # This ctx refer to pydantic AI's ctx, not task ctx.
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

    def _get_user_prompt(
        self, ctx: AnyContext, conversation_context: dict[str, Any]
    ) -> str:
        user_message = self._get_user_message(ctx)
        enriched_context = {**get_default_context(user_message), **conversation_context}
        return dedent(
            f"""
            # Context
            {json.dumps(enriched_context)}
            # User Message
            {user_message}
            """.strip()
        )

    def _get_user_message(self, ctx: AnyContext) -> str:
        return get_str_attr(ctx, self._message, "How are you?", auto_render=True)

    def _get_summarization_prompt(self, ctx: AnyContext) -> str:
        summarization_prompt = get_attr(
            ctx,
            self._summarization_prompt,
            None,
            auto_render=self._render_summarization_prompt,
        )
        if summarization_prompt is not None:
            return summarization_prompt
        return default_llm_config.get_default_summarization_prompt()

    def _get_should_enrich_context(
        self, ctx: AnyContext, history_list: ListOfDict
    ) -> bool:
        if len(history_list) == 0:
            return False
        return get_bool_attr(
            ctx,
            self._should_enrich_context,
            True,  # Default to True if not specified
            auto_render=self._render_enrich_context,
        )

    def _get_context_enrichment_prompt(self, ctx: AnyContext) -> str:
        context_enrichment_prompt = get_attr(
            ctx,
            self._context_enrichment_prompt,
            None,
            auto_render=self._render_context_enrichment_prompt,
        )
        if context_enrichment_prompt is not None:
            return context_enrichment_prompt
        return default_llm_config.get_default_context_enrichment_prompt()

    async def _read_conversation_history(
        self, ctx: AnyContext
    ) -> ConversationHistoryData:  # Returns the model instance
        """Reads conversation history from reader, file, or attribute, with validation."""
        history_file = self._get_history_file(ctx)
        # Priority 1 & 2: Reader and File (handled by ConversationHistoryData)
        history_data = await ConversationHistoryData.read_from_sources(
            ctx=ctx,
            reader=self._conversation_history_reader,
            file_path=history_file,
        )
        if history_data:
            return history_data
        # Priority 3: Callable or direct conversation_history attribute
        raw_data_attr: Any = None
        if callable(self._conversation_history):
            try:
                raw_data_attr = await run_async(self._conversation_history(ctx))
            except Exception as e:
                ctx.log_warning(
                    f"Error executing callable conversation_history attribute: {e}. "
                    "Ignoring."
                )
        if raw_data_attr is None:
            raw_data_attr = self._conversation_history
        if raw_data_attr:
            history_data = ConversationHistoryData.parse_and_validate(
                ctx, raw_data_attr, "attribute"
            )
            if history_data:
                return history_data
        # Fallback: Return default value
        return ConversationHistoryData()

    def _get_history_file(self, ctx: AnyContext) -> str:
        return get_str_attr(
            ctx,
            self._conversation_history_file,
            "",
            auto_render=self._render_history_file,
        )

    def _get_should_summarize_history(
        self, ctx: AnyContext, history_list: ListOfDict
    ) -> bool:
        history_len = len(history_list)
        if history_len == 0:
            return False
        summarization_threshold = self._get_history_summarization_threshold(ctx)
        if summarization_threshold == -1:
            return False
        if summarization_threshold > history_len:
            return False
        return get_bool_attr(
            ctx,
            self._should_summarize_history,
            False,
            auto_render=self._render_summarize_history,
        )

    def _get_history_summarization_threshold(self, ctx: AnyContext) -> int:
        # Use get_int_attr with -1 as default (no limit)
        try:
            return get_int_attr(
                ctx,
                self._history_summarization_threshold,
                -1,
                auto_render=self._render_history_summarization_threshold,
            )
        except ValueError as e:
            ctx.log_warning(
                f"Could not convert history_summarization_threshold to int: {e}. "
                "Defaulting to -1 (no threshold)."
            )
            return -1

    def _get_conversation_context(self, ctx: AnyContext) -> dict[str, Any]:
        """
        Retrieves the conversation context.
        If a value in the context dict is callable, it executes it with ctx.
        """
        raw_context = get_attr(
            ctx, self._conversation_context, {}, auto_render=False
        )  # Context usually shouldn't be rendered
        if not isinstance(raw_context, dict):
            ctx.log_warning(
                f"Conversation context resolved to type {type(raw_context)}, "
                "expected dict. Returning empty context."
            )
            return {}
        # If conversation_context contains callable value, execute them.
        processed_context: dict[str, Any] = {}
        for key, value in raw_context.items():
            if callable(value):
                try:
                    # Check if the callable expects 'ctx'
                    sig = inspect.signature(value)
                    if "ctx" in sig.parameters:
                        processed_context[key] = value(ctx)
                    else:
                        processed_context[key] = value()
                except Exception as e:
                    ctx.log_warning(
                        f"Error executing callable for context key '{key}': {e}. "
                        "Skipping."
                    )
                    processed_context[key] = None
            else:
                processed_context[key] = value
        return processed_context
