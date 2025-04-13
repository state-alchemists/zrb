from typing import Any

from openai import APIError
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessagesTypeAdapter

from zrb.context.any_context import AnyContext
from zrb.task.llm.error import extract_api_error_details
from zrb.task.llm.history import ListOfDict
from zrb.task.llm.print_node import print_node


async def run_agent_iteration(
    ctx: AnyContext,
    agent: Agent,
    user_prompt: str,
    history_list: ListOfDict,
) -> Any:
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
    async with agent.run_mcp_servers():
        async with agent.iter(
            user_prompt=user_prompt,
            message_history=ModelMessagesTypeAdapter.validate_python(history_list),
        ) as agent_run:
            async for node in agent_run:
                # Each node represents a step in the agent's execution
                # Reference: https://ai.pydantic.dev/agents/#streaming
                try:
                    await print_node(ctx.print, agent_run, node)
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
