import json
import traceback
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from zrb.attr.type import BoolAttr, IntAttr
from zrb.context.any_context import AnyContext
from zrb.llm_config import llm_config
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
else:
    Model = Any
    ModelSettings = Any


class EnrichmentConfig(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    model: Model | str | None = None
    settings: ModelSettings | None = None
    prompt: str
    retries: int = 1


class EnrichmentResult(BaseModel):
    response: dict[str, Any]  # or further decompose as needed


async def enrich_context(
    ctx: AnyContext,
    config: EnrichmentConfig,
    conversation_context: dict[str, Any],
    history_list: ListOfDict,
) -> dict[str, Any]:
    """Runs an LLM call to extract key info and merge it into the context."""
    from pydantic_ai import Agent

    ctx.log_info("Attempting to enrich conversation context...")
    # Prepare context and history for the enrichment prompt
    try:
        context_json = json.dumps(conversation_context)
        history_json = json.dumps(history_list)
        # The user prompt will now contain the dynamic data
        user_prompt_data = "\n".join(
            [
                "Extract context from the following conversation info",
                f"Existing Context: {context_json}",
                f"Conversation History: {history_json}",
            ]
        )
    except Exception as e:
        ctx.log_warning(f"Error formatting context/history for enrichment: {e}")
        return conversation_context  # Return original context if formatting fails

    enrichment_agent = Agent(
        model=config.model,
        # System prompt is part of the user prompt for this specific call
        system_prompt=config.prompt,  # Use the main prompt as system prompt
        tools=[],
        mcp_servers=[],
        model_settings=config.settings,
        retries=config.retries,
        output_type=EnrichmentResult,
    )

    try:
        ctx.print(stylize_faint("[Context Enrichment Triggered]"), plain=True)
        enrichment_run = await run_agent_iteration(
            ctx=ctx,
            agent=enrichment_agent,
            user_prompt=user_prompt_data,  # Pass the formatted data as user prompt
            history_list=[],  # Enrichment agent doesn't need prior history itself
        )
        if enrichment_run and enrichment_run.result.output:
            response = enrichment_run.result.output.response
            usage = enrichment_run.result.usage()
            ctx.print(stylize_faint(f"[Token Usage] {usage}"), plain=True)
            if response:
                conversation_context.update(response)
                ctx.log_info("Context enriched based on history.")
                ctx.log_info(
                    f"Updated conversation context: {json.dumps(conversation_context)}"
                )
        else:
            ctx.log_warning("Context enrichment returned no data")
    except Exception as e:
        ctx.log_warning(f"Error during context enrichment LLM call: {e}")
        traceback.print_exc()
    return conversation_context


def get_context_enrichment_threshold(
    ctx: AnyContext,
    context_enrichment_threshold_attr: IntAttr | None,
    render_context_enrichment_threshold: bool,
) -> int:
    """Gets the context enrichment threshold, handling defaults and errors."""
    try:
        return get_int_attr(
            ctx,
            context_enrichment_threshold_attr,
            # Use llm_config default if attribute is None
            llm_config.get_default_context_enrichment_threshold(),
            auto_render=render_context_enrichment_threshold,
        )
    except ValueError as e:
        ctx.log_warning(
            f"Could not convert context_enrichment_threshold to int: {e}. "
            "Defaulting to -1 (no threshold)."
        )
        return -1


def should_enrich_context(
    ctx: AnyContext,
    history_list: ListOfDict,
    should_enrich_context_attr: BoolAttr | None,  # Allow None
    render_enrich_context: bool,
    context_enrichment_threshold_attr: IntAttr | None,
    render_context_enrichment_threshold: bool,
) -> bool:
    """
    Determines if context enrichment should occur based on history, threshold, and config.
    """
    history_part_count = count_part_in_history_list(history_list)
    if history_part_count == 0:
        return False
    enrichment_threshold = get_context_enrichment_threshold(
        ctx,
        context_enrichment_threshold_attr,
        render_context_enrichment_threshold,
    )
    if enrichment_threshold == -1 or enrichment_threshold > history_part_count:
        return False
    return get_bool_attr(
        ctx,
        should_enrich_context_attr,
        llm_config.get_default_enrich_context(),
        auto_render=render_enrich_context,
    )


async def maybe_enrich_context(
    ctx: AnyContext,
    history_list: ListOfDict,
    conversation_context: dict[str, Any],
    should_enrich_context_attr: BoolAttr | None,
    render_enrich_context: bool,
    context_enrichment_threshold_attr: IntAttr | None,
    render_context_enrichment_threshold: bool,
    model: str | Model | None,
    model_settings: ModelSettings | None,
    context_enrichment_prompt: str,
) -> dict[str, Any]:
    """Enriches context based on history if enabled and threshold met."""
    shorten_history_list = replace_system_prompt_in_history_list(history_list)
    if should_enrich_context(
        ctx,
        shorten_history_list,
        should_enrich_context_attr,
        render_enrich_context,
        context_enrichment_threshold_attr,
        render_context_enrichment_threshold,
    ):
        return await enrich_context(
            ctx=ctx,
            config=EnrichmentConfig(
                model=model,
                settings=model_settings,
                prompt=context_enrichment_prompt,
            ),
            conversation_context=conversation_context,
            history_list=shorten_history_list,
        )
    return conversation_context
