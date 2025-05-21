from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic_ai import Agent, Tool
    from pydantic_ai.agent import AgentRun
    from pydantic_ai.mcp import MCPServer
    from pydantic_ai.models import Model
    from pydantic_ai.settings import ModelSettings
else:
    Agent = Any
    Tool = Any
    AgentRun = Any
    MCPServer = Any
    ModelMessagesTypeAdapter = Any
    Model = Any
    ModelSettings = Any

from zrb.context.any_context import AnyContext
from zrb.context.any_shared_context import AnySharedContext
from zrb.task.llm.error import extract_api_error_details
from zrb.task.llm.print_node import print_node
from zrb.task.llm.tool_wrapper import wrap_tool
from zrb.task.llm.typing import ListOfDict

ToolOrCallable = Tool | Callable


def create_agent_instance(
    ctx: AnyContext,
    model: str | Model | None,
    system_prompt: str,
    model_settings: ModelSettings | None,
    tools_attr: (
        list[ToolOrCallable] | Callable[[AnySharedContext], list[ToolOrCallable]]
    ),
    additional_tools: list[ToolOrCallable],
    mcp_servers_attr: list[MCPServer] | Callable[[AnySharedContext], list[MCPServer]],
    additional_mcp_servers: list[MCPServer],
) -> Agent:
    """Creates a new Agent instance with configured tools and servers."""
    # Get tools
    from pydantic_ai import Agent, Tool

    tools_or_callables = list(tools_attr(ctx) if callable(tools_attr) else tools_attr)
    tools_or_callables.extend(additional_tools)
    tools = []
    for tool_or_callable in tools_or_callables:
        if isinstance(tool_or_callable, Tool):
            tools.append(tool_or_callable)
        else:
            # Pass ctx to wrap_tool
            tools.append(wrap_tool(tool_or_callable, ctx))
    # Get MCP Servers
    mcp_servers = list(
        mcp_servers_attr(ctx) if callable(mcp_servers_attr) else mcp_servers_attr
    )
    mcp_servers.extend(additional_mcp_servers)
    # Return Agent
    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=tools,
        mcp_servers=mcp_servers,
        model_settings=model_settings,
        retries=3,  # Consider making retries configurable?
    )


def get_agent(
    ctx: AnyContext,
    agent_attr: Agent | Callable[[AnySharedContext], Agent] | None,
    model: str | Model | None,
    system_prompt: str,
    model_settings: ModelSettings | None,
    tools_attr: (
        list[ToolOrCallable] | Callable[[AnySharedContext], list[ToolOrCallable]]
    ),
    additional_tools: list[ToolOrCallable],
    mcp_servers_attr: list[MCPServer] | Callable[[AnySharedContext], list[MCPServer]],
    additional_mcp_servers: list[MCPServer],
) -> Agent:
    """Retrieves the configured Agent instance or creates one if necessary."""
    from pydantic_ai import Agent

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
    # If no agent provided, create one using the configuration
    return create_agent_instance(
        ctx=ctx,
        model=model,
        system_prompt=system_prompt,
        model_settings=model_settings,
        tools_attr=tools_attr,
        additional_tools=additional_tools,
        mcp_servers_attr=mcp_servers_attr,
        additional_mcp_servers=additional_mcp_servers,
    )


async def run_agent_iteration(
    ctx: AnyContext,
    agent: Agent,
    user_prompt: str,
    history_list: ListOfDict,
) -> AgentRun:
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
    from openai import APIError
    from pydantic_ai.messages import ModelMessagesTypeAdapter

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


def _get_plain_printer(ctx: AnyContext):
    def printer(*args, **kwargs):
        if "plain" not in kwargs:
            kwargs["plain"] = True
        return ctx.print(*args, **kwargs)

    return printer
