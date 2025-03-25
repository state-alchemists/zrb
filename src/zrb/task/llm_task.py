import functools
import json
import logging
import os
import traceback
from collections.abc import Callable
from typing import Any, Union

from pydantic_ai import Agent, Tool
from pydantic_ai.messages import (
    FinalResultEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelMessagesTypeAdapter,
    PartDeltaEvent,
    PartStartEvent,
    TextPartDelta,
    ToolCallPartDelta,
)
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings

from zrb.attr.type import StrAttr, fstring
from zrb.context.any_context import AnyContext
from zrb.context.any_shared_context import AnySharedContext
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.llm_config import LLMConfig
from zrb.llm_config import llm_config as default_llm_config
from zrb.task.any_task import AnyTask
from zrb.task.base_task import BaseTask
from zrb.util.attr import get_attr, get_str_attr
from zrb.util.cli.style import stylize_faint
from zrb.util.file import read_file, write_file
from zrb.util.run import run_async

# Set up logging
logger = logging.getLogger(__name__)

# Type aliases for improved readability
ListOfDict = list[dict[str, Any]]
ToolOrCallable = Tool | Callable
ModelType = Union[Callable[[AnySharedContext], Union[Model, str, fstring]], Model, None]


class LLMTask(BaseTask):
    """
    Task for working with Large Language Models (LLMs).
    
    LLMTask provides integration with various LLM providers through the pydantic-ai
    library. It supports configuring models, managing conversation history, and
    executing LLM-based tasks with various tool integrations.
    
    This task type enables both simple chat functionality and complex agent-based
    workflows that can use tools to interact with external systems.
    """
    def __init__(
        self,
        name: str,
        color: int | None = None,
        icon: str | None = None,
        description: str | None = None,
        cli_only: bool = False,
        input: list[AnyInput | None] | AnyInput | None = None,
        env: list[AnyEnv | None] | AnyEnv | None = None,
        model: ModelType = None,
        render_model: bool = True,
        model_base_url: StrAttr = None,
        render_model_base_url: bool = True,
        model_api_key: StrAttr = None,
        render_model_api_key: bool = True,
        model_settings: (
            ModelSettings | Callable[[AnySharedContext], ModelSettings] | None
        ) = None,
        agent: Agent | Callable[[AnySharedContext], Agent] | None = None,
        system_prompt: StrAttr | None = None,
        render_system_prompt: bool = True,
        message: StrAttr | None = None,
        tools: (
            list[ToolOrCallable] | Callable[[AnySharedContext], list[ToolOrCallable]]
        ) = [],
        conversation_history: (
            ListOfDict | Callable[[AnySharedContext], ListOfDict]
        ) = [],
        conversation_history_reader: (
            Callable[[AnySharedContext], ListOfDict] | None
        ) = None,
        conversation_history_writer: (
            Callable[[AnySharedContext, ListOfDict], None] | None
        ) = None,
        conversation_history_file: StrAttr | None = None,
        render_history_file: bool = True,
        execute_condition: bool | str | Callable[[AnySharedContext], bool] = True,
        retries: int = 2,
        retry_period: float = 0,
        readiness_check: list[AnyTask] | AnyTask | None = None,
        readiness_check_delay: float = 0.5,
        readiness_check_period: float = 5,
        readiness_failure_threshold: int = 1,
        readiness_timeout: int = 60,
        monitor_readiness: bool = False,
        max_call_iteration: int = 20,
        upstream: list[AnyTask] | AnyTask | None = None,
        fallback: list[AnyTask] | AnyTask | None = None,
        successor: list[AnyTask] | AnyTask | None = None,
    ):
        """
        Initialize an LLM Task.
        
        Args:
            name: Task name
            color: ANSI color code for CLI output
            icon: Icon character for CLI output
            description: Task description
            cli_only: Whether the task is CLI only
            input: Task inputs
            env: Environment variables
            model: LLM model identifier or instance (string or Model object)
            render_model: Whether to render the model name as a template
            model_base_url: Custom base URL for model API
            render_model_base_url: Whether to render the base URL as a template
            model_api_key: API key for model authentication
            render_model_api_key: Whether to render the API key as a template
            model_settings: Additional model settings
            agent: Custom agent implementation
            system_prompt: System prompt to guide model behavior
            render_system_prompt: Whether to render the system prompt as a template
            message: User message to send to model
            tools: List of tools the model can use
            conversation_history: Initial conversation history
            conversation_history_reader: Function to read conversation history
            conversation_history_writer: Function to write conversation history
            conversation_history_file: File to store conversation history
            render_history_file: Whether to render the history file path as a template
            execute_condition: Condition for task execution
            retries: Number of task retries on failure
            retry_period: Wait time between retries
            readiness_check: Tasks to check readiness
            readiness_check_delay: Delay before first readiness check
            readiness_check_period: Period between readiness checks
            readiness_failure_threshold: Number of failures before readiness failure
            readiness_timeout: Timeout for readiness checks
            monitor_readiness: Whether to monitor readiness
            max_call_iteration: Maximum number of tool calls per user message
            upstream: Tasks that must complete before this task
            fallback: Fallback tasks to execute if this task fails
            successor: Tasks to execute after this task completes
        """
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
            successor=successor,
        )
        self._model = model
        self._render_model = render_model
        self._model_base_url = model_base_url
        self._render_model_base_url = render_model_base_url
        self._model_api_key = model_api_key
        self._render_model_api_key = render_model_api_key
        self._model_settings = model_settings
        self._agent = agent
        self._system_prompt = system_prompt
        self._render_system_prompt = render_system_prompt
        self._message = message
        self._tools = tools
        self._additional_tools: list[ToolOrCallable] = []
        self._conversation_history = conversation_history
        self._conversation_history_reader = conversation_history_reader
        self._conversation_history_writer = conversation_history_writer
        self._conversation_history_file = conversation_history_file
        self._render_history_file = render_history_file
        self._max_call_iteration = max_call_iteration

    def add_tool(self, tool: ToolOrCallable):
        """
        Add a tool to the LLM task.
        
        This method allows dynamically adding tools to the task after initialization.
        Tools can be either pydantic_ai Tool instances or callable functions that
        will be wrapped into Tool objects.
        
        Args:
            tool: A Tool instance or callable function to add
        """
        logger.info(f"Adding tool to LLM task '{self.name}'")
        self._additional_tools.append(tool)

    async def _exec_action(self, ctx: AnyContext) -> Any:
        """
        Execute the LLM task action.
        
        This method handles the core execution flow for LLM tasks:
        1. Loads conversation history
        2. Gets the user message
        3. Initializes the agent
        4. Runs the agent with the message and history
        5. Updates conversation history with results
        
        Args:
            ctx: The execution context
            
        Returns:
            The agent execution result data
            
        Raises:
            RuntimeError: If there's an error during agent execution
        """
        try:
            logger.info(f"Executing LLM task '{self.name}'")
            
            # Load conversation history
            history = await self._read_conversation_history(ctx)
            
            # Get user message
            user_prompt = self._get_message(ctx)
            if not user_prompt:
                logger.warning("Empty user prompt provided")
            
            # Initialize agent
            agent = self._get_agent(ctx)
            if not agent:
                raise RuntimeError("Failed to initialize agent")
                
            # Execute agent
            async with agent.iter(
                user_prompt=user_prompt,
                message_history=ModelMessagesTypeAdapter.validate_python(history),
            ) as agent_run:
                async for node in agent_run:
                    # Each node represents a step in the agent's execution
                    await self._print_node(ctx, agent_run, node)
                
                # Update conversation history
                new_history = json.loads(agent_run.result.all_messages_json())
                await self._write_conversation_history(ctx, new_history)
                
                logger.info(f"LLM task '{self.name}' execution completed successfully")
                return agent_run.result.data
                
        except Exception as e:
            logger.error(f"Error executing LLM task '{self.name}': {str(e)}")
            raise

    async def _print_node(self, ctx: AnyContext, agent_run: Any, node: Any):
        """
        Process and display agent execution nodes.
        
        This method handles the various types of nodes produced during agent execution,
        displaying appropriate information for each node type, including user prompts,
        model requests, tool calls, and results.
        
        Args:
            ctx: The execution context for printing output
            agent_run: The current agent run instance
            node: The agent execution node to process
        """
        """
        Process and display agent execution nodes.
        
        This method handles the various types of nodes produced during agent execution,
        displaying appropriate information for each node type, including user prompts,
        model requests, tool calls, and results.
        
        Args:
            ctx: The execution context for printing output
            agent_run: The current agent run instance
            node: The agent execution node to process
        """
        try:
            if Agent.is_user_prompt_node(node):
                # User prompt node - represents user input
                logger.debug("Processing user prompt node")
                ctx.print(stylize_faint(f">> UserPromptNode: {node.user_prompt}"))
                
            elif Agent.is_model_request_node(node):
                # Model request node - stream tokens from the model's request
                logger.debug("Processing model request node")
                ctx.print(
                    stylize_faint(">> ModelRequestNode: streaming partial request tokens")
                )
                
                try:
                    async with node.stream(agent_run.ctx) as request_stream:
                        is_streaming = False
                        async for event in request_stream:
                            if isinstance(event, PartStartEvent):
                                if is_streaming:
                                    ctx.print("", plain=True)
                                msg = f"[Request] Starting part {event.index}"
                                ctx.print(
                                    stylize_faint(f"{msg}: {event.part!r}")
                                )
                                is_streaming = False
                                
                            elif isinstance(event, PartDeltaEvent):
                                if isinstance(event.delta, TextPartDelta):
                                    ctx.print(
                                        stylize_faint(f"{event.delta.content_delta}"),
                                        end="",
                                        plain=is_streaming,
                                    )
                                elif isinstance(event.delta, ToolCallPartDelta):
                                    ctx.print(
                                        stylize_faint(f"{event.delta.args_delta}"),
                                        end="",
                                        plain=is_streaming,
                                    )
                                is_streaming = True
                                
                            elif isinstance(event, FinalResultEvent):
                                if is_streaming:
                                    ctx.print("", plain=True)
                                ctx.print(
                                    stylize_faint(f"[Result] tool_name={event.tool_name}")
                                )
                                is_streaming = False
                                
                        # Clean up any incomplete streams
                        if is_streaming:
                            ctx.print("", plain=True)
                except Exception as e:
                    logger.error(f"Error streaming model request: {str(e)}")
                    error_msg = f"[Error] Failed to stream model request: {str(e)}"
                    ctx.print(stylize_faint(error_msg))
                    
            elif Agent.is_call_tools_node(node):
                # Handle tool calls from the model
                logger.debug("Processing call tools node")
                ctx.print(
                    stylize_faint(
                        ">> CallToolsNode: streaming partial response & tool usage"
                    )
                )
                
                try:
                    async with node.stream(agent_run.ctx) as handle_stream:
                        async for event in handle_stream:
                            if isinstance(event, FunctionToolCallEvent):
                                # Fix for Claude when using empty parameters
                                if event.part.args == "":
                                    event.part.args = {}
                                    
                                logger.debug(f"Tool call: {event.part.tool_name}")
                                ctx.print(
                                    stylize_faint(
                                        f"[Tools] The LLM calls tool={event.part.tool_name!r} with args={event.part.args} (tool_call_id={event.part.tool_call_id!r})"  # noqa
                                    )
                                )
                            elif isinstance(event, FunctionToolResultEvent):
                                logger.debug(f"Tool result: {event.tool_call_id}")
                                ctx.print(
                                    stylize_faint(
                                        f"[Tools] Tool call {event.tool_call_id!r} returned => {event.result.content}"  # noqa
                                    )
                                )
                except Exception as e:
                    logger.error(f"Error processing tool calls: {str(e)}")
                    ctx.print(stylize_faint(f"[Error] Failed to process tool calls: {str(e)}"))
                    
            elif Agent.is_end_node(node):
                # Final node - agent execution complete
                logger.debug("Processing end node")
                ctx.print(stylize_faint(f"{agent_run.result.data}"))
                
        except Exception as e:
            logger.error(f"Error processing agent node: {str(e)}")
            ctx.print(stylize_faint(f"[Error] Failed to process agent node: {str(e)}"))

    async def _write_conversation_history(
        self, ctx: AnyContext, conversations: list[Any]
    ):
        """
        Save conversation history to a file or through a custom writer function.
        
        Args:
            ctx: The execution context
            conversations: List of conversation message dictionaries to save
            
        Raises:
            None: Exceptions are caught and logged
        """
        try:
            # Use custom writer if provided
            if self._conversation_history_writer is not None:
                logger.debug("Using custom conversation history writer")
                await run_async(self._conversation_history_writer(ctx, conversations))
                
            # Save to file if path is provided
            history_file = self._get_history_file(ctx)
            if history_file:
                logger.debug(f"Saving conversation history to file: {history_file}")
                try:
                    write_file(history_file, json.dumps(conversations, indent=2))
                    logger.debug(f"Saved {len(conversations)} messages to history file")
                except Exception as e:
                    logger.error(f"Failed to write conversation history: {str(e)}")
        except Exception as e:
            logger.error(f"Error saving conversation history: {str(e)}")

    def _get_model_settings(self, ctx: AnyContext) -> ModelSettings | None:
        """
        Get model settings for the current context.
        
        Args:
            ctx: The execution context
            
        Returns:
            ModelSettings object or None if not configured
        """
        try:
            if callable(self._model_settings):
                logger.debug("Getting model settings from callable")
                return self._model_settings(ctx)
            logger.debug("Using static model settings")
            return self._model_settings
        except Exception as e:
            logger.error(f"Error getting model settings: {str(e)}")
            return None

    def _get_agent(self, ctx: AnyContext) -> Agent:
        """
        Create or retrieve the agent for LLM interaction.
        
        This method handles the logic for getting the appropriate agent:
        1. Return the agent directly if it's an Agent instance
        2. Call the agent factory function if it's callable
        3. Create a new agent with the current configuration if no agent is provided
        
        Args:
            ctx: The execution context
            
        Returns:
            Agent instance configured for the current task
            
        Raises:
            ValueError: If the agent cannot be created
        """
        try:
            # Case 1: Direct agent instance provided
            if isinstance(self._agent, Agent):
                logger.debug("Using provided Agent instance")
                return self._agent
                
            # Case 2: Agent factory function provided
            if callable(self._agent):
                logger.debug("Creating Agent from callable")
                return self._agent(ctx)
                
            # Case 3: Create agent from tools and settings
            logger.debug("Creating new Agent from configuration")
            
            # Get tools - combine predefined and additional tools
            tools_or_callables = list(
                self._tools(ctx) if callable(self._tools) else self._tools
            )
            tools_or_callables.extend(self._additional_tools)
            
            # Wrap callable tools as Tool objects
            tools = []
            for tool in tools_or_callables:
                if isinstance(tool, Tool):
                    tools.append(tool)
                else:
                    tool_name = getattr(tool, '__name__', str(tool))
                    logger.debug(f"Wrapping callable as Tool: {tool_name}")
                    tools.append(Tool(_wrap_tool(tool), takes_ctx=False))
            
            # Create and return the agent
            model = self._get_model(ctx)
            system_prompt = self._get_system_prompt(ctx)
            model_settings = self._get_model_settings(ctx)
            
            logger.debug(f"Creating agent with {len(tools)} tools")
            return Agent(
                model,
                system_prompt=system_prompt,
                tools=tools,
                model_settings=model_settings,
                retries=3,  # Note: This is different from self.retries
            )
            
        except Exception as e:
            error_msg = f"Failed to create agent: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e

    def _get_model(self, ctx: AnyContext) -> str | Model | None:
        model = get_attr(ctx, self._model, None, auto_render=self._render_model)
        if model is None:
            return default_llm_config.get_default_model()
        if isinstance(model, str):
            model_base_url = self._get_model_base_url(ctx)
            model_api_key = self._get_model_api_key(ctx)
            llm_config = LLMConfig(
                default_model_name=model,
                default_base_url=model_base_url,
                default_api_key=model_api_key,
            )
            if model_base_url is None and model_api_key is None:
                default_model_provider = default_llm_config.get_default_model_provider()
                if default_model_provider is not None:
                    llm_config.set_default_provider(default_model_provider)
            return llm_config.get_default_model()
        raise ValueError(f"Invalid model: {model}")

    def _get_model_base_url(self, ctx: AnyContext) -> str | None:
        base_url = get_attr(
            ctx, self._model_base_url, None, auto_render=self._render_model_base_url
        )
        if isinstance(base_url, str) or base_url is None:
            return base_url
        raise ValueError(f"Invalid model base URL: {base_url}")

    def _get_model_api_key(self, ctx: AnyContext) -> str | None:
        api_key = get_attr(
            ctx, self._model_api_key, None, auto_render=self._render_model_api_key
        )
        if isinstance(api_key, str) or api_key is None:
            return api_key
        raise ValueError(f"Invalid model API key: {api_key}")

    def _get_system_prompt(self, ctx: AnyContext) -> str:
        system_prompt = get_attr(
            ctx,
            self._system_prompt,
            None,
            auto_render=self._render_system_prompt,
        )
        if system_prompt is not None:
            return system_prompt
        return default_llm_config.get_default_system_prompt()

    def _get_message(self, ctx: AnyContext) -> str:
        return get_str_attr(ctx, self._message, "How are you?", auto_render=True)

    async def _read_conversation_history(self, ctx: AnyContext) -> ListOfDict:
        if self._conversation_history_reader is not None:
            return await run_async(self._conversation_history_reader(ctx))
        if callable(self._conversation_history):
            return self._conversation_history(ctx)
        history_file = self._get_history_file(ctx)
        if (
            len(self._conversation_history) == 0
            and history_file != ""
            and os.path.isfile(history_file)
        ):
            return json.loads(read_file(history_file))
        return self._conversation_history

    def _get_history_file(self, ctx: AnyContext) -> str:
        return get_str_attr(
            ctx,
            self._conversation_history_file,
            "",
            auto_render=self._render_history_file,
        )


def _wrap_tool(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Optionally, you can include more details from traceback if needed.
            error_details = traceback.format_exc()
            return f"Error: {e}\nDetails: {error_details}"

    return wrapper
