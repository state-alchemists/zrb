from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Callable

from zrb.llm.config.config import llm_config as default_llm_config
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.util.attachment import normalize_attachments
from zrb.llm.util.prompt import expand_prompt

# Context variable to propagate tool confirmation callback to sub-agents
tool_confirmation_var: ContextVar[Callable[[Any], Any] | None] = ContextVar(
    "tool_confirmation", default=None
)

if TYPE_CHECKING:
    from pydantic_ai import Agent, DeferredToolRequests, DeferredToolResults, Tool
    from pydantic_ai._agent_graph import HistoryProcessor
    from pydantic_ai.messages import UserPromptPart
    from pydantic_ai.models import Model
    from pydantic_ai.output import OutputDataT, OutputSpec
    from pydantic_ai.settings import ModelSettings
    from pydantic_ai.tools import ToolFuncEither
    from pydantic_ai.toolsets import AbstractToolset


def create_agent(
    model: "Model | str | None" = None,
    system_prompt: str = "",
    tools: list["Tool | ToolFuncEither"] = [],
    toolsets: list["AbstractToolset[None]"] = [],
    model_settings: "ModelSettings | None" = None,
    history_processors: list["HistoryProcessor"] | None = None,
    output_type: "OutputSpec[OutputDataT]" = str,
    retries: int = 1,
    yolo: bool = False,
) -> "Agent[None, Any]":
    from pydantic_ai import Agent, DeferredToolRequests
    from pydantic_ai.toolsets import FunctionToolset

    # Expand system prompt with references
    effective_system_prompt = expand_prompt(system_prompt)

    final_output_type = output_type
    effective_toolsets = list(toolsets)
    if tools:
        effective_toolsets.append(FunctionToolset(tools=tools))

    if not yolo:
        final_output_type = output_type | DeferredToolRequests
        effective_toolsets = [ts.approval_required() for ts in effective_toolsets]

    if model is None:
        model = default_llm_config.model

    return Agent(
        model=model,
        output_type=final_output_type,
        instructions=effective_system_prompt,
        toolsets=effective_toolsets,
        model_settings=model_settings,
        history_processors=history_processors,
        retries=retries,
    )


async def run_agent(
    agent: "Agent[None, Any]",
    message: str | None,
    message_history: list[Any],
    limiter: LLMLimiter,
    attachments: list[Any] | None = None,
    print_fn: Callable[[str], Any] = print,
    event_handler: Callable[[Any], Any] | None = None,
    tool_confirmation: Callable[[Any], Any] | None = None,
) -> tuple[Any, list[Any]]:
    """
    Runs the agent with rate limiting, history management, and optional CLI confirmation loop.
    Returns (result_output, new_message_history).
    """
    import asyncio

    from pydantic_ai import AgentRunResultEvent, DeferredToolRequests

    # Resolve tool confirmation callback (Arg > Context > None)
    effective_tool_confirmation = tool_confirmation
    if effective_tool_confirmation is None:
        effective_tool_confirmation = tool_confirmation_var.get()

    # Set context var for sub-agents
    token = tool_confirmation_var.set(effective_tool_confirmation)

    try:
        # Expand user message with references
        effective_message = expand_prompt(message) if message else message

        # Prepare Prompt Content
        prompt_content = _get_prompt_content(effective_message, attachments, print_fn)

        # 1. Prune & Throttle
        current_history = await _acquire_rate_limit(
            limiter, prompt_content, message_history, print_fn
        )
        current_message = prompt_content
        current_results = None

        # 2. Execution Loop
        while True:
            result_output = None
            run_history = []

            async for event in agent.run_stream_events(
                current_message,
                message_history=current_history,
                deferred_tool_results=current_results,
            ):
                await asyncio.sleep(0)
                if isinstance(event, AgentRunResultEvent):
                    result = event.result
                    result_output = result.output
                    run_history = result.all_messages()
                if event_handler:
                    await event_handler(event)

            # Handle Deferred Calls
            if isinstance(result_output, DeferredToolRequests):
                current_results = await _process_deferred_requests(
                    result_output, effective_tool_confirmation
                )
                if current_results is None:
                    return result_output, run_history
                # Prepare next iteration
                current_message = None
                current_history = run_history
                continue
            return result_output, run_history
    finally:
        tool_confirmation_var.reset(token)


def _get_prompt_content(
    message: str | None, attachments: list[Any] | None, print_fn: Callable[[str], Any]
) -> "list[UserPromptPart] | str | None":
    from pydantic_ai.messages import UserPromptPart

    prompt_content = message
    if attachments:
        attachments = normalize_attachments(attachments, print_fn)
        parts: list[UserPromptPart] = []
        if message:
            parts.append(UserPromptPart(content=message))
        parts.extend(attachments)
        prompt_content = parts
    return prompt_content


async def _acquire_rate_limit(
    limiter: LLMLimiter,
    message: str | None,
    message_history: list[Any],
    print_fn: Callable[[str], Any],
) -> list[Any]:
    """Prunes history and waits if rate limits are exceeded."""
    if not message:
        return message_history

    # Prune
    pruned_history = limiter.fit_context_window(message_history, message)

    # Throttle
    est_tokens = limiter.count_tokens(pruned_history) + limiter.count_tokens(message)
    await limiter.acquire(
        est_tokens, notifier=lambda msg: print_fn(msg) if msg else None
    )

    return pruned_history


async def _process_deferred_requests(
    result_output: "DeferredToolRequests",
    effective_tool_confirmation: Callable[[Any], Any] | None,
) -> "DeferredToolResults | None":
    """Handles tool approvals/denials via callback or CLI fallback."""
    import asyncio
    import inspect

    from pydantic_ai import DeferredToolResults, ToolApproved, ToolDenied

    all_requests = (result_output.calls or []) + (result_output.approvals or [])
    if not all_requests:
        return None

    current_results = DeferredToolResults()

    for call in all_requests:
        if effective_tool_confirmation:
            res = effective_tool_confirmation(call)
            if inspect.isawaitable(res):
                result = await res
            else:
                result = res
            current_results.approvals[call.tool_call_id] = result
        else:
            # CLI Fallback
            prompt_text = f"Execute tool '{call.tool_name}' with args {call.args}?"
            prompt_cli = f"\n[?] {prompt_text} (y/N) "

            # We use asyncio.to_thread(input, ...) to avoid blocking the loop
            user_input = await asyncio.to_thread(input, prompt_cli)
            answer = user_input.strip().lower() in ("y", "yes")

            if answer:
                current_results.approvals[call.tool_call_id] = ToolApproved()
            else:
                current_results.approvals[call.tool_call_id] = ToolDenied("User denied")

    return current_results
