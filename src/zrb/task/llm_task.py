import json
from collections.abc import Callable
from typing import Any

from zrb.attr.type import StrAttr
from zrb.config import LLM_MODEL, LLM_SYSTEM_PROMPT
from zrb.context.any_context import AnyContext
from zrb.context.any_shared_context import AnySharedContext
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.task.any_task import AnyTask
from zrb.task.base_task import BaseTask
from zrb.util.attr import get_str_attr
from zrb.util.llm.tool import callable_to_tool_schema

DictList = list[dict[str, Any]]


def scratchpad(thought: str) -> str:
    """Use this tool to note your thought and planning"""
    return thought


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
        system_prompt: StrAttr | None = LLM_SYSTEM_PROMPT,
        message: StrAttr | None = None,
        tools: (
            dict[str, Callable] | Callable[[AnySharedContext], dict[str, Callable]]
        ) = {},
        tool_schema: DictList | Callable[[AnySharedContext], DictList] = [],
        history: DictList | Callable[[AnySharedContext], DictList] = [],
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
        )
        self._model = model
        self._system_prompt = system_prompt
        self._message = message
        self._tools = tools
        self._tool_schema = tool_schema
        self._history = history

    async def _exec_action(self, ctx: AnyContext) -> Any:
        from litellm import completion

        system_prompt = self._get_system_prompt(ctx)
        ctx.log_debug("SYSTEM PROMPT", system_prompt)
        history = self._get_history(ctx)
        ctx.log_debug("HISTORY PROMPT", history)
        user_message = self._get_message(ctx)
        ctx.log_debug("USER MESSAGE", user_message)
        messages = (
            [{"role": "system", "content": system_prompt}]
            + history
            + [{"role": "user", "content": user_message}]
        )
        available_tools = self._get_tools(ctx)
        available_tools["scratchpad"] = scratchpad
        tool_schema = self._get_tool_schema(ctx)
        for tool_name, tool in available_tools.items():
            matched_tool_schema = [
                schema
                for schema in tool_schema
                if "function" in schema
                and "name" in schema["function"]
                and schema["function"]["name"] == tool_name
            ]
            if len(matched_tool_schema) == 0:
                tool_schema.append(callable_to_tool_schema(tool))
        ctx.log_debug("TOOL SCHEMA", tool_schema)
        while True:
            response = completion(
                model=self._get_model(ctx), messages=messages, tools=tool_schema
            )
            response_message = response.choices[0].message
            ctx.print(response_message)
            messages.append(response_message)
            tool_calls = response_message.tool_calls
            if tool_calls:
                # noqa Reference: https://docs.litellm.ai/docs/completion/function_call#full-code---parallel-function-calling-with-gpt-35-turbo-1106
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_to_call = available_tools[function_name]
                    function_kwargs = json.loads(tool_call.function.arguments)
                    function_response = function_to_call(**function_kwargs)
                    tool_call_message = {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": function_response,
                    }
                    ctx.print(tool_call_message)
                    messages.append(tool_call_message)
                continue
            return response_message.content

    def _get_model(self, ctx: AnyContext) -> str:
        return get_str_attr(ctx, self._model, "ollama_chat/llama3.1", auto_render=True)

    def _get_system_prompt(self, ctx: AnyContext) -> str:
        return get_str_attr(
            ctx, self._system_prompt, "You are a helpful assistant", auto_render=True
        )

    def _get_message(self, ctx: AnyContext) -> str:
        return get_str_attr(ctx, self._message, "How are you?", auto_render=True)

    def _get_tools(self, ctx: AnyContext) -> dict[str, Callable]:
        if callable(self._tools):
            return self._tools(ctx)
        return self._tools

    def _get_tool_schema(self, ctx: AnyContext) -> DictList:
        if callable(self._tool_schema):
            return self._tool_schema(ctx)
        return self._tool_schema

    def _get_history(self, ctx: AnyContext) -> DictList:
        if callable(self._history):
            return self._history(ctx)
        return self._history
