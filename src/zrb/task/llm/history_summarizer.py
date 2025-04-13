import json
from typing import Any

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings

from zrb.context.any_context import AnyContext
from zrb.task.llm.agent_runner import run_agent_iteration
from zrb.task.llm.history import ListOfDict


# Configuration model for history summarization
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
            ctx.log_info(f"Conversaion summary: {summary_text}")
        else:
            ctx.log_warning("History summarization failed or returned no data.")
    except Exception as e:
        ctx.log_warning(f"Error during history summarization: {e}")

    return conversation_context
