from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Callable

from zrb.builtin.pollux.config.limiter import LLMLimiter

# Context variable to propagate tool confirmation callback to sub-agents
tool_confirmation_var: ContextVar[Callable[[str], bool | Any] | None] = ContextVar(
    "tool_confirmation", default=None
)

if TYPE_CHECKING:
    from pydantic_ai import Agent, Tool
    from pydantic_ai._agent_graph import HistoryProcessor
    from pydantic_ai.models import Model
    from pydantic_ai.output import OutputDataT, OutputSpec
    from pydantic_ai.settings import ModelSettings
    from pydantic_ai.tools import ToolFuncEither
    from pydantic_ai.toolsets import AbstractToolset


def create_agent(
    model: "Model | str",
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

    final_output_type = output_type
    effective_toolsets = list(toolsets)
    if tools:
        effective_toolsets.append(FunctionToolset(tools=tools))

    if not yolo:
        final_output_type = output_type | DeferredToolRequests
        effective_toolsets = [ts.approval_required() for ts in effective_toolsets]

    return Agent(
        model=model,
        output_type=final_output_type,
        instructions=system_prompt,
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
    print_fn: Callable[[str], Any] = print,
    event_handler: Callable[[Any], Any] | None = None,
    tool_confirmation: Callable[[str], bool | Any] | None = None,
    initial_deferred_tool_requests: Any | None = None,
) -> tuple[Any, list[Any]]:
    """
    Runs the agent with rate limiting, history management, and optional CLI confirmation loop.
    Returns (result_output, new_message_history).
    """
    import asyncio
    import inspect

    from pydantic_ai import (
        AgentRunResultEvent,
        DeferredToolRequests,
        DeferredToolResults,
        ToolApproved,
        ToolDenied,
    )

    # Resolve tool confirmation callback (Arg > Context > None)
    effective_tool_confirmation = tool_confirmation
    if effective_tool_confirmation is None:
        effective_tool_confirmation = tool_confirmation_var.get()

    # Set context var for sub-agents
    token = tool_confirmation_var.set(effective_tool_confirmation)

    try:
        # 1. Prune & Throttle
        if message:
            message_history = limiter.fit_context_window(message_history, message)
            est_tokens = limiter.count_tokens(message_history) + limiter.count_tokens(
                message
            )
            await limiter.acquire(
                est_tokens, notifier=lambda msg: print_fn(msg) if msg else None
            )

        current_history = message_history
        current_message = message
        current_results = None
        next_deferred_requests = initial_deferred_tool_requests

        # 2. Execution Loop
        while True:
            result_output = None
            run_history = []

            if next_deferred_requests:
                result_output = next_deferred_requests
                run_history = current_history
                next_deferred_requests = None
            else:
                async for event in agent.run_stream_events(
                    current_message,
                    message_history=current_history,
                    deferred_tool_results=current_results,
                ):
                    if isinstance(event, AgentRunResultEvent):
                        result = event.result
                        result_output = result.output
                        run_history = result.all_messages()
                    elif event_handler:
                        await event_handler(event)

            # Handle Deferred Calls
            if isinstance(result_output, DeferredToolRequests):
                current_results = DeferredToolResults()
                all_requests = (result_output.calls or []) + (
                    result_output.approvals or []
                )

                if not all_requests:
                    return result_output, run_history

                for call in all_requests:
                    prompt_text = (
                        f"Execute tool '{call.tool_name}' with args {call.args}?"
                    )

                    if effective_tool_confirmation:
                        res = effective_tool_confirmation(prompt_text)
                        if inspect.isawaitable(res):
                            answer = await res
                        else:
                            answer = res
                    else:
                        # CLI Fallback
                        prompt_cli = f"\n[?] {prompt_text} (y/N) "
                        if print_fn == print:
                            user_input = await asyncio.to_thread(input, prompt_cli)
                        else:
                            # If print_fn is redirected (e.g. logging), we still try to use print/input for CLI
                            # But properly we should use print_fn to show the prompt?
                            # Using print() directly ensures it goes to stdout even if print_fn is logging.
                            # However, for consistency with 'input', we use standard IO.
                            # If we are in a non-interactive mode, this might hang or fail.
                            # Assuming interactive CLI.
                            user_input = await asyncio.to_thread(input, prompt_cli)

                        answer = user_input.strip().lower() in ("y", "yes")

                    if answer:
                        current_results.approvals[call.tool_call_id] = ToolApproved()
                    else:
                        current_results.approvals[call.tool_call_id] = ToolDenied(
                            "User denied"
                        )

                # Prepare next iteration
                current_message = None
                current_history = run_history
                continue

            return result_output, run_history

    finally:
        tool_confirmation_var.reset(token)
