import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from zrb.config.llm_rate_limitter import LLMRateLimitter
from zrb.context.any_context import AnyContext
from zrb.task.llm.history_processor import create_summarize_history_processor
from zrb.task.llm.tool_wrapper import wrap_func, wrap_tool

if TYPE_CHECKING:
    from pydantic_ai import Agent, Tool
    from pydantic_ai._agent_graph import HistoryProcessor
    from pydantic_ai.models import Model
    from pydantic_ai.output import OutputDataT, OutputSpec
    from pydantic_ai.settings import ModelSettings
    from pydantic_ai.toolsets import AbstractToolset

    ToolOrCallable = Tool | Callable


def create_agent_instance(
    ctx: AnyContext,
    model: "str | Model",
    rate_limitter: LLMRateLimitter | None = None,
    output_type: "OutputSpec[OutputDataT]" = str,
    system_prompt: str = "",
    model_settings: "ModelSettings | None" = None,
    tools: list["ToolOrCallable"] = [],
    toolsets: list["AbstractToolset[None]"] = [],
    retries: int = 3,
    yolo_mode: bool | list[str] | None = None,
    summarization_model: "Model | str | None" = None,
    summarization_model_settings: "ModelSettings | None" = None,
    summarization_system_prompt: str | None = None,
    summarization_retries: int = 2,
    summarization_token_threshold: int | None = None,
    history_processors: list["HistoryProcessor"] | None = None,
    auto_summarize: bool = True,
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
                execute_delegated_tool_call.__name__ = name
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
    # Create History processor with summarizer
    history_processors = [] if history_processors is None else history_processors
    if auto_summarize:
        history_processors += [
            create_summarize_history_processor(
                ctx=ctx,
                system_prompt=system_prompt,
                rate_limitter=rate_limitter,
                summarization_model=summarization_model,
                summarization_model_settings=summarization_model_settings,
                summarization_system_prompt=summarization_system_prompt,
                summarization_token_threshold=summarization_token_threshold,
                summarization_retries=summarization_retries,
            )
        ]
    # Return Agent
    return Agent[None, Any](
        model=model,
        output_type=output_type,
        instructions=system_prompt,
        tools=tool_list,
        toolsets=wrapped_toolsets,
        model_settings=model_settings,
        retries=retries,
        history_processors=history_processors,
    )


def get_agent(
    ctx: AnyContext,
    model: "str | Model",
    rate_limitter: LLMRateLimitter | None = None,
    output_type: "OutputSpec[OutputDataT]" = str,
    system_prompt: str = "",
    model_settings: "ModelSettings | None" = None,
    tools_attr: (
        "list[ToolOrCallable] | Callable[[AnyContext], list[ToolOrCallable]]"
    ) = [],
    additional_tools: "list[ToolOrCallable]" = [],
    toolsets_attr: "list[AbstractToolset[None] | str] | Callable[[AnyContext], list[AbstractToolset[None] | str]]" = [],  # noqa
    additional_toolsets: "list[AbstractToolset[None] | str]" = [],
    retries: int = 3,
    yolo_mode: bool | list[str] | None = None,
    summarization_model: "Model | str | None" = None,
    summarization_model_settings: "ModelSettings | None" = None,
    summarization_system_prompt: str | None = None,
    summarization_retries: int = 2,
    summarization_token_threshold: int | None = None,
    history_processors: list["HistoryProcessor"] | None = None,
) -> "Agent":
    """Retrieves the configured Agent instance or creates one if necessary."""
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
        rate_limitter=rate_limitter,
        output_type=output_type,
        system_prompt=system_prompt,
        tools=tools,
        toolsets=toolsets,
        model_settings=model_settings,
        retries=retries,
        yolo_mode=yolo_mode,
        summarization_model=summarization_model,
        summarization_model_settings=summarization_model_settings,
        summarization_system_prompt=summarization_system_prompt,
        summarization_retries=summarization_retries,
        summarization_token_threshold=summarization_token_threshold,
        history_processors=history_processors,
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
