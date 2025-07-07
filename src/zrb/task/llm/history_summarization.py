import json
import traceback
from typing import TYPE_CHECKING

from zrb.attr.type import BoolAttr, IntAttr
from zrb.config.llm_config import llm_config
from zrb.config.llm_rate_limitter import LLMRateLimiter, llm_rate_limitter
from zrb.context.any_context import AnyContext
from zrb.task.llm.agent import run_agent_iteration
from zrb.task.llm.history import (
    count_part_in_history_list,
    replace_system_prompt_in_history_list,
)
from zrb.task.llm.typing import ListOfDict
from zrb.util.attr import get_bool_attr, get_int_attr
from zrb.util.cli.style import stylize_faint

if TYPE_CHECKING:
    from pydantic_ai.models import Model
    from pydantic_ai.settings import ModelSettings


def _count_token_in_history(history_list: ListOfDict) -> int:
    """Counts the total number of tokens in a conversation history list."""
    text_to_count = json.dumps(history_list)
    return llm_rate_limitter.count_token(text_to_count)


def get_history_summarization_token_threshold(
    ctx: AnyContext,
    history_summarization_token_threshold_attr: IntAttr | None,
    render_history_summarization_token_threshold: bool,
) -> int:
    """Gets the history summarization token threshold, handling defaults and errors."""
    try:
        return get_int_attr(
            ctx,
            history_summarization_token_threshold_attr,
            llm_config.default_history_summarization_token_threshold,
            auto_render=render_history_summarization_token_threshold,
        )
    except ValueError as e:
        ctx.log_warning(
            f"Could not convert history_summarization_token_threshold to int: {e}. "
            "Defaulting to -1 (no threshold)."
        )
        return -1


def should_summarize_history(
    ctx: AnyContext,
    history_list: ListOfDict,
    should_summarize_history_attr: BoolAttr | None,
    render_summarize_history: bool,
    history_summarization_token_threshold_attr: IntAttr | None,
    render_history_summarization_token_threshold: bool,
) -> bool:
    """Determines if history summarization should occur based on token length and config."""
    history_part_count = count_part_in_history_list(history_list)
    if history_part_count == 0:
        return False
    summarization_token_threshold = get_history_summarization_token_threshold(
        ctx,
        history_summarization_token_threshold_attr,
        render_history_summarization_token_threshold,
    )
    history_token_count = _count_token_in_history(history_list)
    if (
        summarization_token_threshold == -1
        or summarization_token_threshold > history_token_count
    ):
        return False
    return get_bool_attr(
        ctx,
        should_summarize_history_attr,
        llm_config.default_summarize_history,
        auto_render=render_summarize_history,
    )


async def summarize_history(
    ctx: AnyContext,
    model: "Model | str | None",
    settings: "ModelSettings | None",
    prompt: str,
    previous_summary: str,
    history_list: ListOfDict,
    rate_limitter: LLMRateLimiter | None = None,
    retries: int = 3,
) -> str:
    """Runs an LLM call to update the conversation summary."""
    from pydantic_ai import Agent

    ctx.log_info("Attempting to summarize conversation history...")
    # Construct the user prompt for the summarization agent
    user_prompt = json.dumps(
        {"previous_summary": previous_summary, "recent_history": history_list}
    )
    summarization_agent = Agent(
        model=model,
        system_prompt=prompt,
        model_settings=settings,
        retries=retries,
    )

    try:
        ctx.print(stylize_faint("📝 Summarize"), plain=True)
        summary_run = await run_agent_iteration(
            ctx=ctx,
            agent=summarization_agent,
            user_prompt=user_prompt,
            history_list=[],
            rate_limitter=rate_limitter,
        )
        if summary_run and summary_run.result and summary_run.result.output:
            new_summary = str(summary_run.result.output)
            usage = summary_run.result.usage()
            ctx.print(stylize_faint(f"📝 Summarization Token: {usage}"), plain=True)
            ctx.print(plain=True)
            ctx.log_info("History summarized and updated.")
            ctx.log_info(f"New conversation summary:\n{new_summary}")
            return new_summary
        else:
            ctx.log_warning("History summarization failed or returned no data.")
    except BaseException as e:
        ctx.log_warning(f"Error during history summarization: {e}")
        traceback.print_exc()

    # Return the original summary if summarization fails
    return previous_summary


async def maybe_summarize_history(
    ctx: AnyContext,
    history_list: ListOfDict,
    conversation_summary: str,
    should_summarize_history_attr: BoolAttr | None,
    render_summarize_history: bool,
    history_summarization_token_threshold_attr: IntAttr | None,
    render_history_summarization_token_threshold: bool,
    model: "str | Model | None",
    model_settings: "ModelSettings | None",
    summarization_prompt: str,
    rate_limitter: LLMRateLimiter | None = None,
) -> tuple[ListOfDict, str]:
    """Summarizes history and updates context if enabled and threshold met."""
    shorten_history_list = replace_system_prompt_in_history_list(history_list)
    if should_summarize_history(
        ctx,
        shorten_history_list,
        should_summarize_history_attr,
        render_summarize_history,
        history_summarization_token_threshold_attr,
        render_history_summarization_token_threshold,
    ):
        new_summary = await summarize_history(
            ctx=ctx,
            model=model,
            settings=model_settings,
            prompt=summarization_prompt,
            previous_summary=conversation_summary,
            history_list=shorten_history_list,
            rate_limitter=rate_limitter,
        )
        # After summarization, the history is cleared and replaced by the new summary
        return [], new_summary
    return history_list, conversation_summary
