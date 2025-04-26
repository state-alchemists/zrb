from collections.abc import Callable
from textwrap import dedent

from pydantic_ai import Tool
from pydantic_ai.mcp import MCPServer
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings

from zrb.context.any_context import AnyContext
from zrb.task.llm.agent import create_agent_instance, run_agent_iteration

ToolOrCallable = Tool | Callable


def create_henchman_tool(
    tool_name: str,
    tool_description: str,
    henchman_system_prompt: str,
    henchman_model: str | Model | None = None,
    henchman_model_settings: ModelSettings | None = None,
    henchman_tools: list[ToolOrCallable] = [],
    henchman_mcp_servers: list[MCPServer] = [],
) -> Callable[[AnyContext, str], str]:
    """
    Create an LLM "henchman" tool function for use by a main LLM agent.

    This factory configures and returns an async function that, when called
    by the main agent, instantiates and runs a sub-agent (the henchman)
    with a given query and returns the henchman's final response.

    Args:
        tool_name: The name of the tool for the main agent.
        tool_description: The description of the tool for the main agent.
        henchman_system_prompt: The system prompt for the henchman agent.
        henchman_model: The model for the henchman agent (optional).
        henchman_model_settings: Model settings for the henchman (optional).
        henchman_tools: A list of tools (Tool instances or callables) for the
            henchman agent (optional).
        henchman_mcp_servers: A list of MCP servers for the henchman agent (optional).

    Returns:
        An async callable function that takes a context and a query string,
        runs the henchman agent, and returns the henchman's final message content.
    """

    async def run_henchman(ctx: AnyContext, query: str) -> str:
        """
        Runs the henchman agent with the given query.
        """
        # Create the henchman agent instance
        henchman_agent = create_agent_instance(
            ctx=ctx,
            model=henchman_model,
            system_prompt=henchman_system_prompt,
            model_settings=henchman_model_settings,
            tools_attr=henchman_tools,  # Pass tools from factory closure
            additional_tools=[],  # No additional tools added after factory creation
            mcp_servers_attr=henchman_mcp_servers,  # Pass servers from factory closure
            additional_mcp_servers=[],  # No additional servers added after factory creation
        )

        # Run the henchman agent iteration
        # Start with an empty history for the sub-agent
        agent_run = await run_agent_iteration(
            ctx=ctx,
            agent=henchman_agent,
            user_prompt=query,
            history_list=[],  # Start with empty history for the henchman
        )

        # Return the henchman's final message content
        if agent_run and agent_run.result:
            # Return the final message content as a string
            return agent_run.result.message_content()
        else:
            ctx.log_warning("Henchman agent run did not produce a result.")
            return "Henchman agent failed to produce a result."

    # Set the name and docstring for the callable function
    run_henchman.__name__ = tool_name
    run_henchman.__doc__ = dedent(
        f"""
        {tool_description}

        Args:
            query (str): The query or task for the henchman agent.

        Returns:
            str: The final response or result from the henchman agent.
        """
    ).strip()

    return run_henchman