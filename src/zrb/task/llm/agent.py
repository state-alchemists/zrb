import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from zrb.config.llm_rate_limitter import LLMRateLimiter, llm_rate_limitter
from zrb.context.any_context import AnyContext
from zrb.context.any_shared_context import AnySharedContext
from zrb.task.llm.error import extract_api_error_details
from zrb.task.llm.print_node import print_node
from zrb.task.llm.tool_wrapper import wrap_tool
from zrb.task.llm.typing import ListOfDict

if TYPE_CHECKING:
    from pydantic_ai import Agent, Tool
    from pydantic_ai.agent import AgentRun
    from pydantic_ai.mcp import MCPServer
    from pydantic_ai.models import Model
    from pydantic_ai.settings import ModelSettings

    ToolOrCallable = Tool | Callable
else:
    ToolOrCallable = Any


def create_agent_instance(
    ctx: AnyContext,
    model: "str | Model | None" = None,
    system_prompt: str = "",
    model_settings: "ModelSettings | None" = None,
    tools: list[ToolOrCallable] = [],
    mcp_servers: list["MCPServer"] = [],
    retries: int = 3,
) -> "Agent":
    """Creates a new Agent instance with configured tools and servers."""
    from pydantic_ai import Agent, Tool

    # Normalize tools
    tool_list = []
    for tool_or_callable in tools:
        if isinstance(tool_or_callable, Tool):
            tool_list.append(tool_or_callable)
        else:
            # Pass ctx to wrap_tool
            tool_list.append(wrap_tool(tool_or_callable, ctx))
    # Return Agent
    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=tool_list,
        mcp_servers=mcp_servers,
        model_settings=model_settings,
        retries=retries,
    )


def get_agent(
    ctx: AnyContext,
    agent_attr: "Agent | Callable[[AnySharedContext], Agent] | None",
    model: "str | Model | None",
    system_prompt: str,
    model_settings: "ModelSettings | None",
    tools_attr: (
        list[ToolOrCallable] | Callable[[AnySharedContext], list[ToolOrCallable]]
    ),
    additional_tools: list[ToolOrCallable],
    mcp_servers_attr: "list[MCPServer] | Callable[[AnySharedContext], list[MCPServer]]",
    additional_mcp_servers: "list[MCPServer]",
    retries: int = 3,
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
    # Get MCP Servers for agent
    mcp_servers = list(
        mcp_servers_attr(ctx) if callable(mcp_servers_attr) else mcp_servers_attr
    )
    mcp_servers.extend(additional_mcp_servers)
    # If no agent provided, create one using the configuration
    return create_agent_instance(
        ctx=ctx,
        model=model,
        system_prompt=system_prompt,
        tools=tools,
        mcp_servers=mcp_servers,
        model_settings=model_settings,
        retries=retries,
    )


async def run_agent_iteration(
    ctx: AnyContext,
    agent: "Agent",
    user_prompt: str,
    history_list: ListOfDict,
    rate_limitter: LLMRateLimiter | None = None,
    max_retry: int = 2,
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
                history_list=history_list,
                rate_limitter=rate_limitter,
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
    history_list: ListOfDict,
    rate_limitter: LLMRateLimiter | None = None,
) -> "AgentRun":
    from openai import APIError
    from pydantic_ai.messages import ModelMessagesTypeAdapter

    agent_payload = estimate_request_payload(agent, user_prompt, history_list)
    if rate_limitter:
        await rate_limitter.throttle(agent_payload)
    else:
        await llm_rate_limitter.throttle(agent_payload)

    async with agent.run_mcp_servers():
        async with agent.iter(
            user_prompt=user_prompt,
            message_history=ModelMessagesTypeAdapter.validate_python(history_list),
        ) as agent_run:
            async for node in agent_run:
                # Each node represents a step in the agent's execution
                # Reference: https://ai.pydantic.dev/agents/#streaming
                try:
                    await print_node(_get_plain_printer(ctx), agent_run, node)
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


def estimate_request_payload(
    agent: "Agent", user_prompt: str, history_list: ListOfDict
) -> str:
    system_prompts = agent._system_prompts if hasattr(agent, "_system_prompts") else ()
    return json.dumps(
        [
            {"role": "system", "content": "\n".join(system_prompts)},
            *history_list,
            {"role": "user", "content": user_prompt},
        ]
    )


def _get_plain_printer(ctx: AnyContext):
    def printer(*args, **kwargs):
        if "plain" not in kwargs:
            kwargs["plain"] = True
        return ctx.print(*args, **kwargs)

    return printer
