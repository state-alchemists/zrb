import json
from collections.abc import Callable
from textwrap import dedent

from pydantic_ai import Tool
from pydantic_ai.mcp import MCPServer
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings

from zrb.context.any_context import AnyContext
from zrb.task.llm.agent import create_agent_instance, run_agent_iteration
from zrb.task.llm.config import get_model, get_model_settings
from zrb.task.llm.prompt import get_combined_system_prompt

ToolOrCallable = Tool | Callable


def create_sub_agent_tool(
    tool_name: str,
    tool_description: str,
    sub_agent_system_prompt: str | None = None,  # Make optional
    sub_agent_model: str | Model | None = None,
    sub_agent_model_settings: ModelSettings | None = None,
    sub_agent_tools: list[ToolOrCallable] = [],
    sub_agent_mcp_servers: list[MCPServer] = [],
) -> Callable[[AnyContext, str], str]:
    """
    Create an LLM "sub-agent" tool function for use by a main LLM agent.

    This factory configures and returns an async function that, when called
    by the main agent, instantiates and runs a sub-agent (the sub-agent)
    with a given query and returns the sub-agent's final response.

    Args:
        tool_name: The name of the tool for the main agent.
        tool_description: The description of the tool for the main agent.
        sub_agent_system_prompt: The system prompt for the sub-agent.
        sub_agent_model: The model for the sub-agent (optional).
        sub_agent_model_settings: Model settings for the sub-agent (optional).
        sub_agent_tools: A list of tools (Tool instances or callables) for the
            sub-agent (optional).
        sub_agent_mcp_servers: A list of MCP servers for the sub-agent (optional).

    Returns:
        An async callable function that takes a context and a query string,
        runs the sub-agent, and returns the sub-agent's final message content.
    """

    async def run_sub_agent(ctx: AnyContext, query: str) -> str:
        """
        Runs the sub-agent with the given query.
        """
        # Resolve parameters, falling back to llm_config defaults if None
        resolved_model = get_model(
            ctx=ctx,
            model_attr=sub_agent_model,
            render_model=True,  # Assuming we always want to render model string attributes
            model_base_url_attr=None,
            # Sub-agent tool doesn't have separate base_url/api_key params
            render_model_base_url=False,
            model_api_key_attr=None,
            render_model_api_key=False,
        )
        resolved_model_settings = get_model_settings(
            ctx=ctx,
            model_settings_attr=sub_agent_model_settings,
        )

        if sub_agent_system_prompt is None:
            resolved_system_prompt = get_combined_system_prompt(
                ctx=ctx,
                persona_attr=None,
                render_persona=False,
                system_prompt_attr=None,
                render_system_prompt=False,
                special_instruction_prompt_attr=None,
                render_special_instruction_prompt=False,
            )
        else:
            resolved_system_prompt = sub_agent_system_prompt

        # Create the sub-agent instance
        sub_agent_agent = create_agent_instance(
            ctx=ctx,
            model=resolved_model,
            system_prompt=resolved_system_prompt,
            model_settings=resolved_model_settings,
            tools_attr=sub_agent_tools,  # Pass tools from factory closure
            additional_tools=[],  # No additional tools added after factory creation
            mcp_servers_attr=sub_agent_mcp_servers,  # Pass servers from factory closure
            additional_mcp_servers=[],  # No additional servers added after factory creation
        )

        # Run the sub-agent iteration
        # Start with an empty history for the sub-agent
        sub_agent_run = await run_agent_iteration(
            ctx=ctx,
            agent=sub_agent_agent,
            user_prompt=query,
            history_list=[],  # Start with empty history for the sub-agent
        )

        # Return the sub-agent's final message content
        if sub_agent_run and sub_agent_run.result:
            # Return the final message content as a string
            return json.dumps({"result": sub_agent_run.result.output})
        else:
            ctx.log_warning("Sub-agent run did not produce a result.")
            return "Sub-agent failed to produce a result."

    # Set the name and docstring for the callable function
    run_sub_agent.__name__ = tool_name
    run_sub_agent.__doc__ = dedent(
        f"""
        {tool_description}

        Args:
            query (str): The query or task for the sub-agent.

        Returns:
            str: The final response or result from the sub-agent.
        """
    ).strip()

    return run_sub_agent
