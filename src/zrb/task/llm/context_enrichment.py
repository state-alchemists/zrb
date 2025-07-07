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


async def enrich_context(
    ctx: AnyContext,
    model: "Model | str | None",
    settings: "ModelSettings | None",
    prompt: str,
    previous_long_term_context: str,
    history_list: ListOfDict,
    rate_limitter: LLMRateLimiter | None = None,
    retries: int = 3,
) -> str:
    """Runs an LLM call to update the long-term context and returns the new context string."""
    from pydantic_ai import Agent

    ctx.log_info("Attempting to enrich conversation context...")
    # Construct the user prompt according to the new prompt format
    user_prompt = json.dumps(
        {
            "previous_long_term_context": previous_long_term_context,
            "recent_conversation_history": history_list,
        }
    )
    enrichment_agent = Agent(
        model=model,
        system_prompt=prompt,
        model_settings=settings,
        retries=retries,
    )

    try:
        ctx.print(stylize_faint("💡 Enrich Context"), plain=True)
        enrichment_run = await run_agent_iteration(
            ctx=ctx,
            agent=enrichment_agent,
            user_prompt=user_prompt,
            history_list=[],  # Enrichment agent works off the prompt, not history
            rate_limitter=rate_limitter,
        )
        if enrichment_run and enrichment_run.result.output:
            new_long_term_context = str(enrichment_run.result.output)
            usage = enrichment_run.result.usage()
            ctx.print(
                stylize_faint(f"💡 Context Enrichment Token: {usage}"), plain=True
            )
            ctx.print(plain=True)
            ctx.log_info("Context enriched based on history.")
            ctx.log_info(f"Updated long-term context:\n{new_long_term_context}")
            return new_long_term_context
        else:
            ctx.log_warning("Context enrichment returned no data.")
    except BaseException as e:
        ctx.log_warning(f"Error during context enrichment LLM call: {e}")
        traceback.print_exc()

    # Return the original context if enrichment fails
    return previous_long_term_context


def get_context_enrichment_token_threshold(
    ctx: AnyContext,
    context_enrichment_token_threshold_attr: IntAttr | None,
    render_context_enrichment_token_threshold: bool,
) -> int:
    """Gets the context enrichment token threshold, handling defaults and errors."""
    try:
        return get_int_attr(
            ctx,
            context_enrichment_token_threshold_attr,
            llm_config.default_context_enrichment_token_threshold,
            auto_render=render_context_enrichment_token_threshold,
        )
    except ValueError as e:
        ctx.log_warning(
            f"Could not convert context_enrichment_token_threshold to int: {e}. "
            "Defaulting to -1 (no threshold)."
        )
        return -1


def should_enrich_context(
    ctx: AnyContext,
    history_list: ListOfDict,
    should_enrich_context_attr: BoolAttr | None,
    render_enrich_context: bool,
    context_enrichment_token_threshold_attr: IntAttr | None,
    render_context_enrichment_token_threshold: bool,
) -> bool:
    """
    Determines if context enrichment should occur based on history, token threshold, and config.
    """
    history_part_count = count_part_in_history_list(history_list)
    if history_part_count == 0:
        return False
    enrichment_token_threshold = get_context_enrichment_token_threshold(
        ctx,
        context_enrichment_token_threshold_attr,
        render_context_enrichment_token_threshold,
    )
    history_token_count = _count_token_in_history(history_list)
    if (
        enrichment_token_threshold == -1
        or enrichment_token_threshold > history_token_count
    ):
        return False
    return get_bool_attr(
        ctx,
        should_enrich_context_attr,
        llm_config.default_enrich_context,
        auto_render=render_enrich_context,
    )


async def maybe_enrich_context(
    ctx: AnyContext,
    history_list: ListOfDict,
    long_term_context: str,
    should_enrich_context_attr: BoolAttr | None,
    render_enrich_context: bool,
    context_enrichment_token_threshold_attr: IntAttr | None,
    render_context_enrichment_token_threshold: bool,
    model: "str | Model | None",
    model_settings: "ModelSettings | None",
    context_enrichment_prompt: str,
    rate_limitter: LLMRateLimiter | None = None,
) -> str:
    """Enriches context based on history if enabled and token threshold met."""
    shorten_history_list = replace_system_prompt_in_history_list(history_list)
    if should_enrich_context(
        ctx,
        shorten_history_list,
        should_enrich_context_attr,
        render_enrich_context,
        context_enrichment_token_threshold_attr,
        render_context_enrichment_token_threshold,
    ):
        return await enrich_context(
            ctx=ctx,
            model=model,
            settings=model_settings,
            prompt=context_enrichment_prompt,
            previous_long_term_context=long_term_context,
            history_list=shorten_history_list,
            rate_limitter=rate_limitter,
        )
    return long_term_context
