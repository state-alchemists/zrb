import json
import traceback
from textwrap import dedent
from typing import Any

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings

from zrb.attr.type import BoolAttr
from zrb.context.any_context import AnyContext
from zrb.llm_config import llm_config
from zrb.task.llm.agent import run_agent_iteration
from zrb.task.llm.typing import ListOfDict
from zrb.util.attr import get_bool_attr


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
    ctx.log_info("Attempting to enrich conversation context...")
    # Prepare context and history for the enrichment prompt
    try:
        context_json = json.dumps(conversation_context)
        history_json = json.dumps(history_list)
        # The user prompt will now contain the dynamic data
        user_prompt_data = dedent(
            f"""
            Analyze the following
            # Current Context
            {context_json}
            # Conversation History
            {history_json}
        """
        ).strip()
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
        result_type=EnrichmentResult,
    )

    try:
        enrichment_run = await run_agent_iteration(
            ctx=ctx,
            agent=enrichment_agent,
            user_prompt=user_prompt_data,  # Pass the formatted data as user prompt
            history_list=[],  # Enrichment agent doesn't need prior history itself
        )
        if enrichment_run and enrichment_run.result.data:
            response = enrichment_run.result.data.response
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


def should_enrich_context(
    ctx: AnyContext,
    history_list: ListOfDict,
    should_enrich_context_attr: BoolAttr | None,  # Allow None
    render_enrich_context: bool,
) -> bool:
    """Determines if context enrichment should occur based on history and config."""
    if len(history_list) == 0:
        return False
    # Use llm_config default if attribute is None
    default_value = llm_config.get_default_enrich_context()
    return get_bool_attr(
        ctx,
        should_enrich_context_attr,
        default_value,  # Pass the default from llm_config
        auto_render=render_enrich_context,
    )


async def maybe_enrich_context(
    ctx: AnyContext,
    history_list: ListOfDict,
    conversation_context: dict[str, Any],
    should_enrich_context_attr: BoolAttr | None,  # Allow None
    render_enrich_context: bool,
    model: str | Model | None,
    model_settings: ModelSettings | None,
    context_enrichment_prompt: str,
) -> dict[str, Any]:
    """Enriches context based on history if enabled."""
    if should_enrich_context(
        ctx, history_list, should_enrich_context_attr, render_enrich_context
    ):
        # Use the enrich_context function now defined in this file
        return await enrich_context(
            ctx=ctx,
            config=EnrichmentConfig(
                model=model,
                settings=model_settings,
                prompt=context_enrichment_prompt,
            ),
            conversation_context=conversation_context,
            history_list=history_list,
        )
    return conversation_context
