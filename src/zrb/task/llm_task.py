import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic_ai import Agent, Tool
    from pydantic_ai.mcp import MCPServer
    from pydantic_ai.models import Model
    from pydantic_ai.settings import ModelSettings
else:
    Agent = Any
    Tool = Any
    MCPServer = Any
    Model = Any
    ModelSettings = Any

from zrb.attr.type import BoolAttr, IntAttr, StrAttr, fstring
from zrb.context.any_context import AnyContext
from zrb.context.any_shared_context import AnySharedContext
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.task.any_task import AnyTask
from zrb.task.base_task import BaseTask
from zrb.task.llm.agent import get_agent, run_agent_iteration
from zrb.task.llm.config import (
    get_model,
    get_model_settings,
)
from zrb.task.llm.context import extract_default_context, get_conversation_context
from zrb.task.llm.context_enrichment import maybe_enrich_context
from zrb.task.llm.history import (
    ConversationHistoryData,
    ListOfDict,
    read_conversation_history,
    write_conversation_history,
)
from zrb.task.llm.history_summarization import maybe_summarize_history
from zrb.task.llm.prompt import (
    get_combined_system_prompt,
    get_context_enrichment_prompt,
    get_summarization_prompt,
    get_user_message,
)
from zrb.util.cli.style import stylize_faint
from zrb.xcom.xcom import Xcom

if TYPE_CHECKING:
    ToolOrCallable = Tool | Callable
else:
    ToolOrCallable = Any


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
        persona: StrAttr | None = None,
        render_persona: bool = True,
        system_prompt: StrAttr | None = None,
        render_system_prompt: bool = True,
        special_instruction_prompt: StrAttr | None = None,
        render_special_instruction_prompt: bool = True,
        message: StrAttr | None = None,
        summarization_prompt: StrAttr | None = None,
        render_summarization_prompt: bool = True,
        enrich_context: BoolAttr | None = None,
        render_enrich_context: bool = True,
        context_enrichment_prompt: StrAttr | None = None,
        render_context_enrichment_prompt: bool = True,
        context_enrichment_threshold: IntAttr | None = None,
        render_context_enrichment_threshold: bool = True,
        tools: (
            list["ToolOrCallable"]
            | Callable[[AnySharedContext], list["ToolOrCallable"]]
        ) = [],
        mcp_servers: (
            list["MCPServer"] | Callable[[AnySharedContext], list["MCPServer"]]
        ) = [],
        conversation_history: (
            ConversationHistoryData
            | Callable[[AnySharedContext], ConversationHistoryData | dict | list]
            | dict
            | list
        ) = ConversationHistoryData(),
        conversation_history_reader: (
            Callable[[AnySharedContext], ConversationHistoryData | dict | list | None]
            | None
        ) = None,
        conversation_history_writer: (
            Callable[[AnySharedContext, ConversationHistoryData], None] | None
        ) = None,
        conversation_history_file: StrAttr | None = None,
        render_history_file: bool = True,
        summarize_history: BoolAttr | None = None,
        render_summarize_history: bool = True,
        history_summarization_threshold: IntAttr | None = None,
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
        self._persona = persona
        self._render_persona = render_persona
        self._system_prompt = system_prompt
        self._render_system_prompt = render_system_prompt
        self._special_instruction_prompt = special_instruction_prompt
        self._render_special_instruction_prompt = render_special_instruction_prompt
        self._message = message
        self._summarization_prompt = summarization_prompt
        self._render_summarization_prompt = render_summarization_prompt
        self._should_enrich_context = enrich_context
        self._render_enrich_context = render_enrich_context
        self._context_enrichment_prompt = context_enrichment_prompt
        self._render_context_enrichment_prompt = render_context_enrichment_prompt
        self._context_enrichment_threshold = context_enrichment_threshold
        self._render_context_enrichment_threshold = render_context_enrichment_threshold
        self._tools = tools
        self._additional_tools: list["ToolOrCallable"] = []
        self._mcp_servers = mcp_servers
        self._additional_mcp_servers: list["MCPServer"] = []
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
        self.append_tool(tool)

    def append_tool(self, tool: ToolOrCallable):
        self._additional_tools.append(tool)

    def add_mcp_server(self, mcp_server: MCPServer):
        self.append_mcp_server(mcp_server)

    def append_mcp_server(self, mcp_server: MCPServer):
        self._additional_mcp_servers.append(mcp_server)

    def set_should_enrich_context(self, enrich_context: bool):
        self._should_enrich_context = enrich_context

    def set_context_enrichment_threshold(self, enrichment_threshold: int):
        self._context_enrichment_threshold = enrichment_threshold

    def set_should_summarize_history(self, summarize_history: bool):
        self._should_summarize_history = summarize_history

    def set_history_summarization_threshold(self, summarization_threshold: int):
        self._history_summarization_threshold = summarization_threshold

    async def _exec_action(self, ctx: AnyContext) -> Any:
        # Get dependent configurations first
        model_settings = get_model_settings(ctx, self._model_settings)
        model = get_model(
            ctx=ctx,
            model_attr=self._model,
            render_model=self._render_model,
            model_base_url_attr=self._model_base_url,
            render_model_base_url=self._render_model_base_url,
            model_api_key_attr=self._model_api_key,
            render_model_api_key=self._render_model_api_key,
        )
        context_enrichment_prompt = get_context_enrichment_prompt(
            ctx=ctx,
            context_enrichment_prompt_attr=self._context_enrichment_prompt,
            render_context_enrichment_prompt=self._render_context_enrichment_prompt,
        )
        summarization_prompt = get_summarization_prompt(
            ctx=ctx,
            summarization_prompt_attr=self._summarization_prompt,
            render_summarization_prompt=self._render_summarization_prompt,
        )
        user_message = get_user_message(ctx, self._message)
        # Get the combined system prompt using the new getter
        system_prompt = get_combined_system_prompt(
            ctx=ctx,
            persona_attr=self._persona,
            render_persona=self._render_persona,
            system_prompt_attr=self._system_prompt,
            render_system_prompt=self._render_system_prompt,
            special_instruction_prompt_attr=self._special_instruction_prompt,
            render_special_instruction_prompt=self._render_special_instruction_prompt,
        )
        # 1. Prepare initial state (read history from previous session)
        conversation_history = await read_conversation_history(
            ctx=ctx,
            conversation_history_reader=self._conversation_history_reader,
            conversation_history_file_attr=self._conversation_history_file,
            render_history_file=self._render_history_file,
            conversation_history_attr=self._conversation_history,
        )
        history_list = conversation_history.history
        conversation_context = {
            **conversation_history.context,
            **get_conversation_context(ctx, self._conversation_context),
        }
        # 2. Enrich context (optional)
        conversation_context = await maybe_enrich_context(
            ctx=ctx,
            history_list=history_list,
            conversation_context=conversation_context,
            should_enrich_context_attr=self._should_enrich_context,
            render_enrich_context=self._render_enrich_context,
            context_enrichment_threshold_attr=self._context_enrichment_threshold,
            render_context_enrichment_threshold=self._render_context_enrichment_threshold,
            model=model,
            model_settings=model_settings,
            context_enrichment_prompt=context_enrichment_prompt,
        )
        # 3. Summarize history (optional, modifies history_list and context)
        history_list, conversation_context = await maybe_summarize_history(
            ctx=ctx,
            history_list=history_list,
            conversation_context=conversation_context,
            should_summarize_history_attr=self._should_summarize_history,
            render_summarize_history=self._render_summarize_history,
            history_summarization_threshold_attr=self._history_summarization_threshold,
            render_history_summarization_threshold=(
                self._render_history_summarization_threshold
            ),
            model=model,
            model_settings=model_settings,
            summarization_prompt=summarization_prompt,
        )
        # 4. Build the final user prompt and system prompt
        final_user_prompt, default_context = extract_default_context(user_message)
        final_system_prompt = "\n".join(
            [
                system_prompt,
                "# Context",
                json.dumps({**default_context, **conversation_context}),
            ]
        )
        # 5. Get the agent instance
        agent = get_agent(
            ctx=ctx,
            agent_attr=self._agent,
            model=model,
            system_prompt=final_system_prompt,
            model_settings=model_settings,
            tools_attr=self._tools,
            additional_tools=self._additional_tools,
            mcp_servers_attr=self._mcp_servers,
            additional_mcp_servers=self._additional_mcp_servers,
        )
        # 6. Run the agent iteration and save the results/history
        return await self._run_agent_and_save_history(
            ctx, agent, final_user_prompt, history_list, conversation_context
        )

    async def _run_agent_and_save_history(
        self,
        ctx: AnyContext,
        agent: Agent,
        user_prompt: str,
        history_list: ListOfDict,
        conversation_context: dict[str, Any],
    ) -> Any:
        """Executes the agent, processes results, and saves history."""
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
                    context=conversation_context,  # Save the final context state
                    history=new_history_list,
                )
                await write_conversation_history(
                    ctx=ctx,
                    history_data=data_to_write,
                    conversation_history_writer=self._conversation_history_writer,
                    conversation_history_file_attr=self._conversation_history_file,
                    render_history_file=self._render_history_file,
                )
                xcom_usage_key = f"{self.name}-usage"
                if xcom_usage_key not in ctx.xcom:
                    ctx.xcom[xcom_usage_key] = Xcom([])
                usage = agent_run.result.usage()
                ctx.xcom.get(xcom_usage_key).push(usage)
                ctx.print(stylize_faint(f"[Token Usage] {usage}"), plain=True)
                return agent_run.result.output
            else:
                ctx.log_warning("Agent run did not produce a result.")
                return None  # Or handle as appropriate
        except Exception as e:
            ctx.log_error(f"Error during agent execution or history saving: {str(e)}")
            raise  # Re-raise the exception after logging
