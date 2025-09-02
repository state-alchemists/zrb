import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from zrb.attr.type import BoolAttr, IntAttr, StrAttr, StrListAttr, fstring
from zrb.config.llm_rate_limitter import LLMRateLimiter
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
    get_yolo_mode,
)
from zrb.task.llm.conversation_history import (
    inject_conversation_history_notes,
    read_conversation_history,
    write_conversation_history,
)
from zrb.task.llm.conversation_history_model import ConversationHistory
from zrb.task.llm.history_summarization import maybe_summarize_history
from zrb.task.llm.prompt import (
    get_attachments,
    get_summarization_system_prompt,
    get_system_and_user_prompt,
    get_user_message,
)
from zrb.util.cli.style import stylize_faint
from zrb.xcom.xcom import Xcom

if TYPE_CHECKING:
    from pydantic_ai import Agent, Tool
    from pydantic_ai.messages import UserContent
    from pydantic_ai.models import Model
    from pydantic_ai.settings import ModelSettings
    from pydantic_ai.toolsets import AbstractToolset

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
            "Callable[[AnySharedContext], Model | str | fstring] | Model | None"
        ) = None,
        render_model: bool = True,
        model_base_url: StrAttr | None = None,
        render_model_base_url: bool = True,
        model_api_key: StrAttr | None = None,
        render_model_api_key: bool = True,
        model_settings: (
            "ModelSettings | Callable[[AnySharedContext], ModelSettings] | None"
        ) = None,
        agent: "Agent | Callable[[AnySharedContext], Agent] | None" = None,
        persona: StrAttr | None = None,
        render_persona: bool = False,
        system_prompt: StrAttr | None = None,
        render_system_prompt: bool = False,
        special_instruction_prompt: StrAttr | None = None,
        render_special_instruction_prompt: bool = False,
        modes: StrListAttr | None = None,
        render_modes: bool = True,
        message: StrAttr | None = None,
        attachment: "UserContent | list[UserContent] | Callable[[AnySharedContext], UserContent | list[UserContent]] | None" = None,  # noqa
        render_message: bool = True,
        tools: (
            list["ToolOrCallable"]
            | Callable[[AnySharedContext], list["ToolOrCallable"]]
        ) = [],
        toolsets: (
            list["AbstractToolset[Agent]"] | Callable[[AnySharedContext], list["Tool"]]
        ) = [],
        conversation_history: (
            ConversationHistory
            | Callable[[AnySharedContext], ConversationHistory | dict | list]
            | dict
            | list
        ) = ConversationHistory(),
        conversation_history_reader: (
            Callable[[AnySharedContext], ConversationHistory | dict | list | None]
            | None
        ) = None,
        conversation_history_writer: (
            Callable[[AnySharedContext, ConversationHistory], None] | None
        ) = None,
        conversation_history_file: StrAttr | None = None,
        render_history_file: bool = True,
        summarize_history: BoolAttr | None = None,
        render_summarize_history: bool = True,
        summarization_prompt: StrAttr | None = None,
        render_summarization_prompt: bool = False,
        history_summarization_token_threshold: IntAttr | None = None,
        render_history_summarization_token_threshold: bool = True,
        rate_limitter: LLMRateLimiter | None = None,
        execute_condition: bool | str | Callable[[AnySharedContext], bool] = True,
        retries: int = 2,
        retry_period: float = 0,
        yolo_mode: StrListAttr | BoolAttr | None = None,
        is_yolo_mode: BoolAttr | None = None,
        render_yolo_mode: bool = True,
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
        self._modes = modes
        self._render_modes = render_modes
        self._message = message
        self._render_message = render_message
        self._summarization_prompt = summarization_prompt
        self._render_summarization_prompt = render_summarization_prompt
        self._tools = tools
        self._rate_limitter = rate_limitter
        self._additional_tools: list["ToolOrCallable"] = []
        self._toolsets = toolsets
        self._additional_toolsets: list["AbstractToolset[Agent]"] = []
        self._conversation_history = conversation_history
        self._conversation_history_reader = conversation_history_reader
        self._conversation_history_writer = conversation_history_writer
        self._conversation_history_file = conversation_history_file
        self._render_history_file = render_history_file
        self._should_summarize_history = summarize_history
        self._render_summarize_history = render_summarize_history
        self._history_summarization_token_threshold = (
            history_summarization_token_threshold
        )
        self._render_history_summarization_token_threshold = (
            render_history_summarization_token_threshold
        )
        self._max_call_iteration = max_call_iteration
        self._conversation_context = conversation_context
        self._yolo_mode = yolo_mode
        if is_yolo_mode is not None:
            print("[DEPRECATED] use `yolo_mode` instead of `is_yolo_mode`")
            if self._yolo_mode is None:
                self._yolo_mode = is_yolo_mode
        self._render_yolo_mode = render_yolo_mode
        self._attachment = attachment

    def add_tool(self, *tool: "ToolOrCallable"):
        self.append_tool(*tool)

    def append_tool(self, *tool: "ToolOrCallable"):
        for single_tool in tool:
            self._additional_tools.append(single_tool)

    def add_toolset(self, *toolset: "AbstractToolset[Agent]"):
        self.append_toolset(*toolset)

    def append_toolset(self, *toolset: "AbstractToolset[Agent]"):
        for single_toolset in toolset:
            self._additional_toolsets.append(single_toolset)

    def set_should_summarize_history(self, summarize_history: bool):
        self._should_summarize_history = summarize_history

    def set_history_summarization_token_threshold(
        self, summarization_token_threshold: int
    ):
        self._history_summarization_token_threshold = summarization_token_threshold

    def set_modes(self, modes: StrListAttr):
        self._modes = modes

    def set_yolo_mode(self, yolo_mode: StrListAttr | BoolAttr):
        self._yolo_mode = yolo_mode

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
        yolo_mode = get_yolo_mode(
            ctx=ctx,
            yolo_mode_attr=self._yolo_mode,
            render_yolo_mode=self._render_yolo_mode,
        )
        summarization_prompt = get_summarization_system_prompt(
            ctx=ctx,
            summarization_prompt_attr=self._summarization_prompt,
            render_summarization_prompt=self._render_summarization_prompt,
        )
        user_message = get_user_message(ctx, self._message, self._render_message)
        attachments = get_attachments(ctx, self._attachment)
        # 1. Prepare initial state (read history from previous session)
        conversation_history = await read_conversation_history(
            ctx=ctx,
            conversation_history_reader=self._conversation_history_reader,
            conversation_history_file_attr=self._conversation_history_file,
            render_history_file=self._render_history_file,
            conversation_history_attr=self._conversation_history,
        )
        inject_conversation_history_notes(conversation_history)
        # 2. Get system prompt and user prompt
        system_prompt, user_message = get_system_and_user_prompt(
            ctx=ctx,
            user_message=user_message,
            persona_attr=self._persona,
            render_persona=self._render_persona,
            system_prompt_attr=self._system_prompt,
            render_system_prompt=self._render_system_prompt,
            special_instruction_prompt_attr=self._special_instruction_prompt,
            render_special_instruction_prompt=self._render_special_instruction_prompt,
            modes_attr=self._modes,
            render_modes=self._render_modes,
            conversation_history=conversation_history,
        )
        ctx.log_debug(f"SYSTEM PROMPT: {system_prompt}")
        # 3. Get the agent instance
        agent = get_agent(
            ctx=ctx,
            agent_attr=self._agent,
            model=model,
            system_prompt=system_prompt,
            model_settings=model_settings,
            tools_attr=self._tools,
            additional_tools=self._additional_tools,
            toolsets_attr=self._toolsets,
            additional_toolsets=self._additional_toolsets,
            yolo_mode=yolo_mode,
        )
        # 4. Run the agent iteration and save the results/history
        result = await self._execute_agent(
            ctx=ctx,
            agent=agent,
            user_prompt=user_message,
            attachments=attachments,
            conversation_history=conversation_history,
        )
        # 5. Summarize
        conversation_history = await maybe_summarize_history(
            ctx=ctx,
            conversation_history=conversation_history,
            should_summarize_history_attr=self._should_summarize_history,
            render_summarize_history=self._render_summarize_history,
            history_summarization_token_threshold_attr=(
                self._history_summarization_token_threshold
            ),
            render_history_summarization_token_threshold=(
                self._render_history_summarization_token_threshold
            ),
            model=model,
            model_settings=model_settings,
            summarization_prompt=summarization_prompt,
            rate_limitter=self._rate_limitter,
        )
        # 6. Write conversation history
        await write_conversation_history(
            ctx=ctx,
            history_data=conversation_history,
            conversation_history_writer=self._conversation_history_writer,
            conversation_history_file_attr=self._conversation_history_file,
            render_history_file=self._render_history_file,
        )
        return result

    async def _execute_agent(
        self,
        ctx: AnyContext,
        agent: "Agent",
        user_prompt: str,
        attachments: "list[UserContent]",
        conversation_history: ConversationHistory,
    ) -> Any:
        """Executes the agent, processes results, and saves history."""
        try:
            agent_run = await run_agent_iteration(
                ctx=ctx,
                agent=agent,
                user_prompt=user_prompt,
                attachments=attachments,
                history_list=conversation_history.history,
                rate_limitter=self._rate_limitter,
            )

            if agent_run and agent_run.result:
                new_history_list = json.loads(agent_run.result.all_messages_json())
                conversation_history.history = new_history_list
                xcom_usage_key = f"{self.name}-usage"
                if xcom_usage_key not in ctx.xcom:
                    ctx.xcom[xcom_usage_key] = Xcom([])
                usage = agent_run.result.usage()
                ctx.xcom[xcom_usage_key].push(usage)
                ctx.print(stylize_faint(f"  💸 Token: {usage}"), plain=True)
                return agent_run.result.output
            else:
                ctx.log_warning("Agent run did not produce a result.")
                return None  # Or handle as appropriate
        except Exception as e:
            ctx.log_error(f"Error during agent execution or history saving: {str(e)}")
            raise  # Re-raise the exception after logging
