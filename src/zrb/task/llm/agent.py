import inspect
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from zrb.config.llm_rate_limitter import LLMRateLimiter, llm_rate_limitter
from zrb.context.any_context import AnyContext
from zrb.context.any_shared_context import AnySharedContext
from zrb.task.llm.error import extract_api_error_details
from zrb.task.llm.print_node import print_node
from zrb.task.llm.tool_wrapper import wrap_func, wrap_tool
from zrb.task.llm.typing import ListOfDict
from zrb.util.cli.style import stylize_faint

if TYPE_CHECKING:
    from pydantic_ai import Agent, Tool
    from pydantic_ai.agent import AgentRun
    from pydantic_ai.messages import UserContent
    from pydantic_ai.models import Model
    from pydantic_ai.output import OutputDataT, OutputSpec
    from pydantic_ai.settings import ModelSettings
    from pydantic_ai.toolsets import AbstractToolset

    ToolOrCallable = Tool | Callable


def create_agent_instance(
    ctx: AnyContext,
    model: "str | Model",
    output_type: "OutputSpec[OutputDataT]" = str,
    system_prompt: str = "",
    model_settings: "ModelSettings | None" = None,
    tools: "list[ToolOrCallable]" = [],
    toolsets: list["AbstractToolset[None]"] = [],
    retries: int = 3,
    yolo_mode: bool | list[str] | None = None,
) -> "Agent[None, Any]":
    """Creates a new Agent instance with configured tools and servers."""
    from pydantic_ai import Agent, RunContext, Tool
    from pydantic_ai.tools import GenerateToolJsonSchema
    from pydantic_ai.toolsets import ToolsetTool, WrapperToolset

    @dataclass
    class ConfirmationWrapperToolset(WrapperToolset):
        ctx: AnyContext
        yolo_mode: bool | list[str]

        async def call_tool(
            self, name: str, tool_args: dict, ctx: RunContext, tool: ToolsetTool[None]
        ) -> Any:
            # The `tool` object is passed in. Use it for inspection.
            # Define a temporary function that performs the actual tool call.
            async def execute_delegated_tool_call(**params):
                # Pass all arguments down the chain.
                return await self.wrapped.call_tool(name, tool_args, ctx, tool)

            # For the confirmation UI, make our temporary function look like the real one.
            try:
                execute_delegated_tool_call.__name__ = tool.function.__name__
                execute_delegated_tool_call.__doc__ = tool.function.__doc__
                execute_delegated_tool_call.__signature__ = inspect.signature(
                    tool.function
                )
            except (AttributeError, TypeError):
                pass  # Ignore if we can't inspect the original function
            # Use the existing wrap_func to get the confirmation logic
            wrapped_executor = wrap_func(
                execute_delegated_tool_call, self.ctx, self.yolo_mode
            )
            # Call the wrapped executor. This will trigger the confirmation prompt.
            return await wrapped_executor(**tool_args)

    if yolo_mode is None:
        yolo_mode = False
    # Normalize tools
    tool_list = []
    for tool_or_callable in tools:
        if isinstance(tool_or_callable, Tool):
            tool_list.append(tool_or_callable)
            # Update tool's function
            tool = tool_or_callable
            tool_list.append(
                Tool(
                    function=wrap_func(tool.function, ctx, yolo_mode),
                    takes_ctx=tool.takes_ctx,
                    max_retries=tool.max_retries,
                    name=tool.name,
                    description=tool.description,
                    prepare=tool.prepare,
                    docstring_format=tool.docstring_format,
                    require_parameter_descriptions=tool.require_parameter_descriptions,
                    schema_generator=GenerateToolJsonSchema,
                    strict=tool.strict,
                )
            )
        else:
            # Turn function into tool
            tool_list.append(wrap_tool(tool_or_callable, ctx, yolo_mode))
    # Wrap toolsets
    wrapped_toolsets = [
        ConfirmationWrapperToolset(wrapped=toolset, ctx=ctx, yolo_mode=yolo_mode)
        for toolset in toolsets
    ]
    # Return Agent
    return Agent[None, Any](
        model=model,
        output_type=output_type,
        system_prompt=system_prompt,
        tools=tool_list,
        toolsets=wrapped_toolsets,
        model_settings=model_settings,
        retries=retries,
    )


def get_agent(
    ctx: AnyContext,
    agent_attr: "Agent | Callable[[AnySharedContext], Agent] | None",
    model: "str | Model",
    output_type: "OutputSpec[OutputDataT]" = str,
    system_prompt: str = "",
    model_settings: "ModelSettings | None" = None,
    tools_attr: (
        "list[ToolOrCallable] | Callable[[AnySharedContext], list[ToolOrCallable]]"
    ) = [],
    additional_tools: "list[ToolOrCallable]" = [],
    toolsets_attr: "list[AbstractToolset[None] | str] | Callable[[AnySharedContext], list[AbstractToolset[None] | str]]" = [],  # noqa
    additional_toolsets: "list[AbstractToolset[None] | str]" = [],
    retries: int = 3,
    yolo_mode: bool | list[str] | None = None,
) -> "Agent":
    """Retrieves the configured Agent instance or creates one if necessary."""
    from pydantic_ai import Agent

    # Render agent instance and return if agent_attr is already an agent
    if isinstance(agent_attr, Agent):
        return agent_attr
    if callable(agent_attr):
        agent_instance = agent_attr(ctx)
        if not isinstance(agent_instance, Agent):
            err_msg = (
                "Callable agent factory did not return an Agent instance, "
                f"got: {type(agent_instance)}"
            )
            raise TypeError(err_msg)
        return agent_instance
    # Get tools for agent
    tools = list(tools_attr(ctx) if callable(tools_attr) else tools_attr)
    tools.extend(additional_tools)
    # Get Toolsets for agent
    toolset_or_str_list = list(
        toolsets_attr(ctx) if callable(toolsets_attr) else toolsets_attr
    )
    toolset_or_str_list.extend(additional_toolsets)
    toolsets = _render_toolset_or_str_list(ctx, toolset_or_str_list)
    # If no agent provided, create one using the configuration
    return create_agent_instance(
        ctx=ctx,
        model=model,
        output_type=output_type,
        system_prompt=system_prompt,
        tools=tools,
        toolsets=toolsets,
        model_settings=model_settings,
        retries=retries,
        yolo_mode=yolo_mode,
    )


def _render_toolset_or_str_list(
    ctx: AnyContext, toolset_or_str_list: list["AbstractToolset[None] | str"]
) -> list["AbstractToolset[None]"]:
    from pydantic_ai.mcp import load_mcp_servers

    toolsets = []
    for toolset_or_str in toolset_or_str_list:
        if isinstance(toolset_or_str, str):
            try:
                servers = load_mcp_servers(toolset_or_str)
                for server in servers:
                    toolsets.append(server)
            except Exception as e:
                ctx.log_error(f"Invalid MCP Config {toolset_or_str}: {e}")
            continue
        toolsets.append(toolset_or_str)
    return toolsets


async def run_agent_iteration(
    ctx: AnyContext,
    agent: "Agent[None, Any]",
    user_prompt: str,
    attachments: "list[UserContent] | None" = None,
    history_list: ListOfDict | None = None,
    rate_limitter: LLMRateLimiter | None = None,
    max_retry: int = 2,
    log_indent_level: int = 0,
) -> "AgentRun":
    """
    Runs a single iteration of the agent execution loop.

    Args:
        ctx: The task context.
        agent: The Pydantic AI agent instance.
        user_prompt: The user's input prompt.
        history_list: The current conversation history.

    Returns:
        The agent run result object.

    Raises:
        Exception: If any error occurs during agent execution.
    """
    if max_retry < 0:
        raise ValueError("Max retry cannot be less than 0")
    attempt = 0
    while attempt < max_retry:
        try:
            return await _run_single_agent_iteration(
                ctx=ctx,
                agent=agent,
                user_prompt=user_prompt,
                attachments=[] if attachments is None else attachments,
                history_list=[] if history_list is None else history_list,
                rate_limitter=(
                    llm_rate_limitter if rate_limitter is None else rate_limitter
                ),
                log_indent_level=log_indent_level,
            )
        except BaseException:
            attempt += 1
            if attempt == max_retry:
                raise
    raise Exception("Max retry exceeded")


async def _run_single_agent_iteration(
    ctx: AnyContext,
    agent: "Agent",
    user_prompt: str,
    attachments: "list[UserContent]",
    history_list: ListOfDict,
    rate_limitter: LLMRateLimiter,
    log_indent_level: int,
) -> "AgentRun":
    from openai import APIError
    from pydantic_ai.messages import ModelMessagesTypeAdapter

    agent_payload = _estimate_request_payload(
        agent, user_prompt, attachments, history_list
    )
    callback = _create_print_throttle_notif(ctx)
    if rate_limitter:
        await rate_limitter.throttle(agent_payload, callback)
    else:
        await llm_rate_limitter.throttle(agent_payload, callback)

    user_prompt_with_attachments = [user_prompt] + attachments
    async with agent:
        async with agent.iter(
            user_prompt=user_prompt_with_attachments,
            message_history=ModelMessagesTypeAdapter.validate_python(history_list),
        ) as agent_run:
            async for node in agent_run:
                # Each node represents a step in the agent's execution
                try:
                    await print_node(
                        _get_plain_printer(ctx), agent_run, node, log_indent_level
                    )
                except APIError as e:
                    # Extract detailed error information from the response
                    error_details = extract_api_error_details(e)
                    ctx.log_error(f"API Error: {error_details}")
                    raise
                except Exception as e:
                    ctx.log_error(f"Error processing node: {str(e)}")
                    ctx.log_error(f"Error type: {type(e).__name__}")
                    raise
            return agent_run


def _create_print_throttle_notif(ctx: AnyContext) -> Callable[[], None]:
    def _print_throttle_notif():
        ctx.print(stylize_faint("  ⌛>> Request Throttled"), plain=True)

    return _print_throttle_notif


def _estimate_request_payload(
    agent: "Agent",
    user_prompt: str,
    attachments: "list[UserContent]",
    history_list: ListOfDict,
) -> str:
    system_prompts = agent._system_prompts if hasattr(agent, "_system_prompts") else ()
    return json.dumps(
        [
            {"role": "system", "content": "\n".join(system_prompts)},
            *history_list,
            {"role": "user", "content": user_prompt},
            *[_estimate_attachment_payload(attachment) for attachment in attachments],
        ]
    )


def _estimate_attachment_payload(attachment: "UserContent") -> Any:
    if hasattr(attachment, "url"):
        return {"role": "user", "content": attachment.url}
    if hasattr(attachment, "data"):
        return {"role": "user", "content": "x" * len(attachment.data)}
    return ""


def _get_plain_printer(ctx: AnyContext):
    def printer(*args, **kwargs):
        if "plain" not in kwargs:
            kwargs["plain"] = True
        return ctx.print(*args, **kwargs)

    return printer
