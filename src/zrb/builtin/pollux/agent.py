from typing import TYPE_CHECKING, Any, Callable

from zrb.builtin.pollux.config.limiter import LLMLimiter

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
    deferred_tool_results: Any,
    limiter: LLMLimiter,
    print_fn: Callable[[str], Any] = print,
    event_handler: Callable[[Any], Any] | None = None,
    return_deferred_tool_call: bool = True,
) -> tuple[Any, list[Any]]:
    """
    Runs the agent with rate limiting, history management, and optional CLI confirmation loop.
    Returns (result_output, new_message_history).
    """
    import asyncio
    import sys

    from pydantic_ai import (
        AgentRunResultEvent,
        DeferredToolRequests,
        DeferredToolResults,
        ToolApproved,
        ToolDenied,
    )

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
    current_results = deferred_tool_results

    # 2. Execution Loop
    while True:
        result_output = None
        run_history = []

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
            if return_deferred_tool_call:
                return result_output, run_history

            # CLI Fallback Mode
            current_results = DeferredToolResults()
            all_requests = (result_output.calls or []) + (result_output.approvals or [])

            if not all_requests:
                return result_output, run_history

            for call in all_requests:
                # Use standard input for CLI
                # We assume we are in a terminal if no UI is present
                prompt_text = f"\n[?] Execute tool '{call.tool_name}' with args {call.args}? (y/N) "
                if print_fn == print:
                    # Direct stdout
                    answer = await asyncio.to_thread(input, prompt_text)
                else:
                    # Fallback
                    print_fn(prompt_text)
                    # We can't easily get input if print_fn is abstract, assume denial or wait?
                    # For safety, denial.
                    answer = "n"

                if answer.strip().lower() in ("y", "yes"):
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
