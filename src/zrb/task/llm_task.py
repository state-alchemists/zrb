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
from zrb.util.llm.tool import callable_to_tool_schema

ListOfDict = list[dict[str, Any]]


class AdditionalTool(BaseModel):
    fn: Callable
    name: str | None
    description: str | None


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
        render_model: bool = True,
        system_prompt: StrAttr | None = LLM_SYSTEM_PROMPT,
        render_system_prompt: bool = True,
        message: StrAttr | None = None,
        tools: (
            dict[str, Callable] | Callable[[AnySharedContext], dict[str, Callable]]
        ) = {},
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

    def add_tool(
        self, tool: Callable, name: str | None = None, description: str | None = None
    ):
        self._additional_tools.append(
            AdditionalTool(fn=tool, name=name, description=description)
        )

    async def _exec_action(self, ctx: AnyContext) -> Any:
        from litellm import acompletion, supports_function_calling

        model = self._get_model(ctx)
        try:
            allow_function_call = supports_function_calling(model=model)
        except Exception:
            allow_function_call = False
        model_kwargs = self._get_model_kwargs(ctx)
        ctx.log_debug("MODEL KWARGS", model_kwargs)
        system_prompt = self._get_system_prompt(ctx)
        ctx.log_debug("SYSTEM PROMPT", system_prompt)
        history = self._get_history(ctx)
        ctx.log_debug("HISTORY PROMPT", history)
        user_message = {"role": "user", "content": self._get_message(ctx)}
        ctx.print(stylize_faint(f"{user_message}"))
        messages = history + [user_message]
        available_tools = self._get_tools(ctx)
        available_tools["scratchpad"] = scratchpad
        if allow_function_call:
            tool_schema = [
                callable_to_tool_schema(tool, name)
                for name, tool in available_tools.items()
            ]
            for additional_tool in self._additional_tools:
                fn = additional_tool.fn
                tool_name = additional_tool.name or fn.__name__
                tool_description = additional_tool.description
                available_tools[tool_name] = additional_tool.fn
                tool_schema.append(
                    callable_to_tool_schema(
                        fn, name=tool_name, description=tool_description
                    )
                )
            model_kwargs["tools"] = tool_schema
            ctx.log_debug("TOOL SCHEMA", tool_schema)
        history_file = self._get_history_file(ctx)
        while True:
            response = await acompletion(
                model=model,
                messages=[{"role": "system", "content": system_prompt}] + messages,
                **model_kwargs,
            )
            response_message = response.choices[0].message
            ctx.print(stylize_faint(f"{response_message.to_dict()}"))
            messages.append(response_message.to_dict())
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
                    ctx.print(stylize_faint(f"{tool_call_message}"))
                    messages.append(tool_call_message)
                continue
            if history_file != "":
                os.makedirs(os.path.dirname(history_file), exist_ok=True)
                with open(history_file, "w") as f:
                    f.write(json.dumps(messages, indent=2))
            return response_message.content

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

    def _get_tools(self, ctx: AnyContext) -> dict[str, Callable]:
        if callable(self._tools):
            return self._tools(ctx)
        return self._tools

    def _get_history(self, ctx: AnyContext) -> ListOfDict:
        if callable(self._history):
            return self._history(ctx)
        history_file = self._get_history_file(ctx)
        if (
            len(self._history) == 0
            and history_file != ""
            and os.path.isfile(history_file)
        ):
            with open(history_file, "r") as f:
                return json.loads(f.read())
        return self._history

    def _get_history_file(self, ctx: AnyContext) -> str:
        return get_str_attr(
            ctx, self._history_file, "", auto_render=self._render_history_file
        )
