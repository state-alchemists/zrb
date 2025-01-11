import json
import os
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from zrb.attr.type import StrAttr
from zrb.config import LLM_MODEL, LLM_SYSTEM_PROMPT
from zrb.context.any_context import AnyContext
from zrb.context.any_shared_context import AnySharedContext
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.task.any_task import AnyTask
from zrb.task.base_task import BaseTask
from zrb.util.attr import get_str_attr
from zrb.util.cli.style import stylize_faint
from zrb.util.file import read_file, write_file
from zrb.util.llm.tool import callable_to_tool_schema

ListOfDict = list[dict[str, Any]]


class AdditionalTool(BaseModel):
    fn: Callable
    name: str | None


def scratchpad(thought: str) -> str:
    """Use this tool to note your thought and planning"""
    return thought


def end_conversation(final_answer: str) -> str:
    """End conversation with a final answer containing all necessary information"""
    return final_answer


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
        model: StrAttr | None = LLM_MODEL,
        render_model: bool = True,
        system_prompt: StrAttr | None = LLM_SYSTEM_PROMPT,
        render_system_prompt: bool = True,
        message: StrAttr | None = None,
        tools: list[Callable] | Callable[[AnySharedContext], list[Callable]] = [],
        history: ListOfDict | Callable[[AnySharedContext], ListOfDict] = [],
        history_file: StrAttr | None = None,
        render_history_file: bool = True,
        model_kwargs: (
            dict[str, Any] | Callable[[AnySharedContext], dict[str, Any]]
        ) = {},
        execute_condition: bool | str | Callable[[AnySharedContext], bool] = True,
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
        self._model_kwargs = model_kwargs
        self._system_prompt = system_prompt
        self._render_system_prompt = render_system_prompt
        self._message = message
        self._tools = tools
        self._history = history
        self._history_file = history_file
        self._render_history_file = render_history_file
        self._additional_tools: list[AdditionalTool] = []

    def add_tool(self, tool: Callable):
        self._tools.append(tool)

    async def _exec_action(self, ctx: AnyContext) -> Any:
        import litellm
        from litellm.utils import supports_function_calling

        model = self._get_model(ctx)
        try:
            function_call_supported = supports_function_calling(model=model)
        except Exception:
            function_call_supported = False
            litellm.add_function_to_prompt = True
        if not function_call_supported:
            ctx.log_warning(f"Model {model} doesn't support function call")
        available_tools = self._get_available_tools(ctx)
        if not function_call_supported:
            available_tools["end_conversation"] = end_conversation
        tool_schema = [callable_to_tool_schema(tool) for tool in available_tools.values()]
        ctx.log_debug("TOOL SCHEMA", tool_schema)
        model_kwargs = self._get_model_kwargs(ctx)
        ctx.log_debug("MODEL KWARGS", model_kwargs)
        system_prompt = self._get_system_prompt(ctx)
        ctx.log_debug("SYSTEM PROMPT", system_prompt)
        history = self._get_history(ctx)
        ctx.log_debug("HISTORY PROMPT", history)
        user_message = {"role": "user", "content": self._get_message(ctx)}
        ctx.print(stylize_faint(f"{user_message}"))
        conversations = history + [user_message]
        model_kwargs["tools"] = tool_schema
        history_file = self._get_history_file(ctx)
        while True:
            llm_response = await self._get_llm_response(
                model=model,
                system_prompt=system_prompt,
                conversations=conversations,
                model_kwargs=model_kwargs
            )
            llm_response_dict = llm_response.to_dict()
            ctx.print(stylize_faint(f"{llm_response_dict}"))
            conversations.append(llm_response_dict)
            ctx.log_debug("RESPONSE MESSAGE", llm_response)
            if hasattr(llm_response, "tool_calls") and llm_response.tool_calls:
                # noqa Reference: https://docs.litellm.ai/docs/completion/function_call#full-code---parallel-function-calling-with-gpt-35-turbo-1106
                for tool_call in llm_response.tool_calls:
                    function_name = tool_call.function.name
                    function_kwargs = json.loads(tool_call.function.arguments)
                    tool_call_message = {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": self._get_tool_result(
                            available_tools, function_name, function_kwargs
                        ),
                    }
                    ctx.print(stylize_faint(f"{tool_call_message}"))
                    conversations.append(tool_call_message)
                continue
            elif not function_call_supported:
                try:
                    payload = json.loads(llm_response.content)
                    function_name = payload["name"]
                    function_kwargs = payload["arguments"]
                    tool_call_message = self._create_fallback_scratchpad_call_message(
                        self._get_tool_result(available_tools, function_name, function_kwargs)
                    )
                    ctx.print(stylize_faint(f"{tool_call_message}"))
                    conversations.append(tool_call_message)
                    if function_name == "end_conversation":
                        write_file(history_file, json.dumps(conversations, indent=2))
                        return function_kwargs.get("final_answer", "")
                except Exception as e:
                    ctx.log_error(e)
                    tool_call_message = self._create_fallback_scratchpad_call_message(f"{e}")
                    conversations.append(tool_call_message)
                continue
            if history_file != "":
                write_file(history_file, json.dumps(conversations, indent=2))
            return llm_response.content

    async def _get_llm_response(
        self,
        model: str,
        system_prompt: str,
        conversations: list[Any],
        model_kwargs: dict[str, Any]
    ) -> Any:
        from litellm import acompletion
        llm_response = await acompletion(
            model=model,
            messages=[{"role": "system", "content": system_prompt}] + conversations,
            **model_kwargs,
        )
        return llm_response.choices[0].message

    def _create_fallback_scratchpad_call_message(self, message: str) -> dict[str, Any]:
        return {
            "role": "assistant",
            "content": json.dumps({"name": "scratchpad", "arguments": {"thought": message}}),
        }

    def _get_tool_result(
        self,
        available_tools: dict[str, Callable],
        function_name: str,
        function_kwargs: dict[str, Any],
    ) -> str:
        if function_name not in available_tools:
            return f"[ERROR] Invalid tool: {function_name}"
        function_to_call = available_tools[function_name]
        try:
            return function_to_call(**function_kwargs)
        except Exception as e:
            return f"[ERROR] {e}"

    def _get_model(self, ctx: AnyContext) -> str:
        return get_str_attr(
            ctx, self._model, "ollama_chat/llama3.1", auto_render=self._render_model
        )

    def _get_system_prompt(self, ctx: AnyContext) -> str:
        return get_str_attr(
            ctx,
            self._system_prompt,
            "You are a helpful assistant",
            auto_render=self._render_system_prompt,
        )

    def _get_message(self, ctx: AnyContext) -> str:
        return get_str_attr(ctx, self._message, "How are you?", auto_render=True)

    def _get_model_kwargs(self, ctx: AnyContext) -> dict[str, Callable]:
        if callable(self._model_kwargs):
            return self._model_kwargs(ctx)
        return {**self._model_kwargs}

    def _get_available_tools(self, ctx: AnyContext) -> dict[str, Callable]:
        tools = {"scratchpad": scratchpad}
        tool_list = self._tools(ctx) if callable(self._tools) else self._tools
        for tool in tool_list:
            tools[tool.__name__] = tool
        return tools

    def _get_history(self, ctx: AnyContext) -> ListOfDict:
        if callable(self._history):
            return self._history(ctx)
        history_file = self._get_history_file(ctx)
        if (
            len(self._history) == 0
            and history_file != ""
            and os.path.isfile(history_file)
        ):
            return json.loads(read_file(history_file))
        return self._history

    def _get_history_file(self, ctx: AnyContext) -> str:
        return get_str_attr(
            ctx, self._history_file, "", auto_render=self._render_history_file
        )
