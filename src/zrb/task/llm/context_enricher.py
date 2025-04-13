import json
import traceback
from textwrap import dedent
from typing import Any

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings

from zrb.context.any_context import AnyContext
from zrb.task.llm.agent_runner import run_agent_iteration
from zrb.task.llm.history import ListOfDict


# Configuration model for context enrichment
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
                ctx.log_info("History summarized and added/updated in context.")
                ctx.log_info(
                    f"New conversation context: {json.dumps(conversation_context)}"
                )
        else:
            ctx.log_warning("Context enrichment return no data")
    except Exception as e:
        ctx.log_warning(f"Error during context enrichment LLM call: {e}")
        traceback.print_exc()
    return conversation_context
