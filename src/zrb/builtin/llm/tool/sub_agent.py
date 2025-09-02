import json
from collections.abc import Callable
from textwrap import dedent
from typing import TYPE_CHECKING, Any, Coroutine

from zrb.context.any_context import AnyContext
from zrb.task.llm.agent import create_agent_instance, run_agent_iteration
from zrb.task.llm.config import get_model, get_model_settings
from zrb.task.llm.prompt import get_system_and_user_prompt

if TYPE_CHECKING:
    from pydantic_ai import Agent, Tool
    from pydantic_ai.models import Model
    from pydantic_ai.settings import ModelSettings
    from pydantic_ai.toolsets import AbstractToolset

    ToolOrCallable = Tool | Callable


def create_sub_agent_tool(
    tool_name: str,
    tool_description: str,
    system_prompt: str | None = None,
    model: "str | Model | None" = None,
    model_settings: "ModelSettings | None" = None,
    tools: "list[ToolOrCallable]" = [],
    toolsets: list["AbstractToolset[Agent]"] = [],
    yolo_mode: bool | list[str] | None = None,
    log_indent_level: int = 2,
) -> Callable[[AnyContext, str], Coroutine[Any, Any, str]]:
    """
    Creates a "tool that is another AI agent," capable of handling complex,
    multi-step sub-tasks.

    This powerful factory function generates a tool that, when used, spins up
    a temporary, specialized AI agent. This "sub-agent" has its own system
    prompt, tools, and context, allowing it to focus exclusively on
    accomplishing the task it's given without being distracted by the main
    conversation.

    This is ideal for delegating complex tasks like analyzing a file or a
    repository.

    Args:
        tool_name (str): The name for the generated sub-agent tool.
        tool_description (str): A clear description of the sub-agent's purpose
            and when to use it.
        system_prompt (str, optional): The system prompt that will guide the
            sub-agent's behavior.
        model (str | Model, optional): The language model the sub-agent will
            use.
        model_settings (ModelSettings, optional): Specific settings for the
            sub-agent's model.
        tools (list, optional): A list of tools that will be exclusively
            available to the sub-agent.
        toolsets (list, optional): A list of Toolset for the sub-agent.

    Returns:
        Callable: An asynchronous function that serves as the sub-agent tool.
            When called, it runs the sub-agent with a given query and returns
            its final result.
    """

    async def run_sub_agent(ctx: AnyContext, query: str) -> str:
        """
        Runs the sub-agent with the given query.
        """
        # Resolve parameters, falling back to llm_config defaults if None
        resolved_model = get_model(
            ctx=ctx,
            model_attr=model,
            render_model=True,  # Assuming we always want to render model string attributes
            model_base_url_attr=None,
            # Sub-agent tool doesn't have separate base_url/api_key params
            render_model_base_url=False,
            model_api_key_attr=None,
            render_model_api_key=False,
        )
        resolved_model_settings = get_model_settings(
            ctx=ctx,
            model_settings_attr=model_settings,
        )

        if system_prompt is None:
            resolved_system_prompt, query = get_system_and_user_prompt(
                ctx=ctx,
                user_message=query,
                persona_attr=None,
                system_prompt_attr=None,
                special_instruction_prompt_attr=None,
            )
        else:
            resolved_system_prompt = system_prompt
        # Create the sub-agent instance
        sub_agent_agent = create_agent_instance(
            ctx=ctx,
            model=resolved_model,
            system_prompt=resolved_system_prompt,
            model_settings=resolved_model_settings,
            tools=tools,
            toolsets=toolsets,
            yolo_mode=yolo_mode,
        )

        sub_agent_run = None
        # Run the sub-agent iteration
        # Start with an empty history for the sub-agent
        sub_agent_run = await run_agent_iteration(
            ctx=ctx,
            agent=sub_agent_agent,
            user_prompt=query,
            attachments=[],
            history_list=[],
            log_indent_level=log_indent_level,
        )

        # Return the sub-agent's final message content
        if sub_agent_run and sub_agent_run.result:
            # Return the final message content as a string
            return json.dumps({"result": sub_agent_run.result.output})
        ctx.log_warning("Sub-agent run did not produce a result.")
        raise ValueError(f"{tool_name} not returning any result")

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
