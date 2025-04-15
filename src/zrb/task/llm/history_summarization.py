import json
from typing import Any

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings

from zrb.attr.type import BoolAttr, IntAttr
from zrb.context.any_context import AnyContext
from zrb.task.llm.agent import run_agent_iteration
from zrb.task.llm.typing import ListOfDict
from zrb.util.attr import get_bool_attr, get_int_attr


def get_history_part_len(history_list: ListOfDict) -> int:
    """Calculates the total number of 'parts' in a history list."""
    history_part_len = 0
    for history in history_list:
        if "parts" in history:
            history_part_len += len(history["parts"])
        else:
            history_part_len += 1
    return history_part_len


def get_history_summarization_threshold(
    ctx: AnyContext,
    history_summarization_threshold_attr: IntAttr,
    render_history_summarization_threshold: bool,
) -> int:
    """Gets the history summarization threshold, handling defaults and errors."""
    try:
        return get_int_attr(
            ctx,
            history_summarization_threshold_attr,
            -1,  # Default to -1 (no threshold)
            auto_render=render_history_summarization_threshold,
        )
    except ValueError as e:
        ctx.log_warning(
            f"Could not convert history_summarization_threshold to int: {e}. "
            "Defaulting to -1 (no threshold)."
        )
        return -1


def should_summarize_history(
    ctx: AnyContext,
    history_list: ListOfDict,
    should_summarize_history_attr: BoolAttr,
    render_summarize_history: bool,
    history_summarization_threshold_attr: IntAttr,
    render_history_summarization_threshold: bool,
) -> bool:
    """Determines if history summarization should occur based on length and config."""
    history_part_len = get_history_part_len(history_list)
    if history_part_len == 0:
        return False
    summarization_threshold = get_history_summarization_threshold(
        ctx,
        history_summarization_threshold_attr,
        render_history_summarization_threshold,
    )
    if summarization_threshold == -1:  # -1 means no summarization trigger
        return False
    if summarization_threshold > history_part_len:
        return False
    return get_bool_attr(
        ctx,
        should_summarize_history_attr,
        False,  # Default to False if not specified
        auto_render=render_summarize_history,
    )


class SummarizationConfig(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    model: Model | str | None = None
    settings: ModelSettings | None = None
    prompt: str
    retries: int = 1


async def summarize_history(
    ctx: AnyContext,
    config: SummarizationConfig,
    conversation_context: dict[str, Any],
    history_list: ListOfDict,
) -> dict[str, Any]:
    """Runs an LLM call to summarize history and update the context."""
    ctx.log_info("Attempting to summarize conversation history...")

    summarization_agent = Agent(
        model=config.model,
        system_prompt=config.prompt,
        tools=[],  # No tools needed for summarization
        mcp_servers=[],
        model_settings=config.settings,
        retries=config.retries,
    )

    # Prepare context and history for summarization prompt
    try:
        context_json = json.dumps(conversation_context)
        history_to_summarize_json = json.dumps(history_list)
        summarization_user_prompt = (
            f"# Current Context\n{context_json}\n\n"
            f"# Conversation History to Summarize\n{history_to_summarize_json}"
        )
    except Exception as e:
        ctx.log_warning(f"Error formatting context/history for summarization: {e}")
        return conversation_context  # Return original context if formatting fails

    try:
        summary_run = await run_agent_iteration(
            ctx=ctx,
            agent=summarization_agent,
            user_prompt=summarization_user_prompt,
            history_list=[],  # Summarization agent doesn't need prior history
        )
        if summary_run and summary_run.result.data:
            summary_text = str(summary_run.result.data)
            # Update context with the new summary
            conversation_context["history_summary"] = summary_text
            ctx.log_info("History summarized and added/updated in context.")
            ctx.log_info(f"Conversation summary: {summary_text}")
        else:
            ctx.log_warning("History summarization failed or returned no data.")
    except Exception as e:
        ctx.log_warning(f"Error during history summarization: {e}")

    return conversation_context


async def maybe_summarize_history(
    ctx: AnyContext,
    history_list: ListOfDict,
    conversation_context: dict[str, Any],
    should_summarize_history_attr: BoolAttr,
    render_summarize_history: bool,
    history_summarization_threshold_attr: IntAttr,
    render_history_summarization_threshold: bool,
    model: str | Model | None,
    model_settings: ModelSettings | None,
    summarization_prompt: str,
) -> tuple[ListOfDict, dict[str, Any]]:
    """Summarizes history and updates context if enabled and threshold met."""
    if should_summarize_history(
        ctx,
        history_list,
        should_summarize_history_attr,
        render_summarize_history,
        history_summarization_threshold_attr,
        render_history_summarization_threshold,
    ):
        # Use summarize_history defined above
        updated_context = await summarize_history(
            ctx=ctx,
            config=SummarizationConfig(
                model=model,
                settings=model_settings,
                prompt=summarization_prompt,
            ),
            conversation_context=conversation_context,
            history_list=history_list,  # Pass the full list for context
        )
        # Truncate the history list after summarization
        return [], updated_context
    return history_list, conversation_context
