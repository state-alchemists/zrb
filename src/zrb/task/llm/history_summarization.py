import json
import traceback
from typing import TYPE_CHECKING

from zrb.attr.type import BoolAttr, IntAttr
from zrb.config.llm_config import llm_config
from zrb.config.llm_rate_limitter import LLMRateLimiter, llm_rate_limitter
from zrb.context.any_context import AnyContext
from zrb.task.llm.agent import run_agent_iteration
from zrb.task.llm.conversation_history import (
    count_part_in_history_list,
    inject_conversation_history_notes,
    replace_system_prompt_in_history,
)
from zrb.task.llm.conversation_history_model import ConversationHistory
from zrb.task.llm.history_summarization_tool import (
    create_history_summarization_tool,
)
from zrb.task.llm.typing import ListOfDict
from zrb.util.attr import get_bool_attr, get_int_attr
from zrb.util.cli.style import stylize_faint
from zrb.util.llm.prompt import make_prompt_section
from zrb.util.truncate import truncate_str

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
    system_prompt: str,
    conversation_history: ConversationHistory,
    rate_limitter: LLMRateLimiter | None = None,
    retries: int = 3,
) -> ConversationHistory:
    """Runs an LLM call to update the conversation summary."""
    from pydantic_ai import Agent

    inject_conversation_history_notes(conversation_history)
    ctx.log_info("Attempting to summarize conversation history...")
    # Construct the user prompt for the summarization agent
    user_prompt = "\n".join(
        [
            make_prompt_section(
                "Past Conversation",
                "\n".join(
                    [
                        make_prompt_section(
                            "Summary",
                            conversation_history.past_conversation_summary,
                            as_code=True,
                        ),
                        make_prompt_section(
                            "Last Transcript",
                            conversation_history.past_conversation_transcript,
                            as_code=True,
                        ),
                    ]
                ),
            ),
            make_prompt_section(
                "Recent Conversation (JSON)",
                json.dumps(truncate_str(conversation_history.history, 1000)),
                as_code=True,
            ),
            make_prompt_section(
                "Notes",
                "\n".join(
                    [
                        make_prompt_section(
                            "Long Term",
                            conversation_history.long_term_note,
                            as_code=True,
                        ),
                        make_prompt_section(
                            "Contextual",
                            conversation_history.contextual_note,
                            as_code=True,
                        ),
                    ]
                ),
            ),
        ]
    )
    summarize = create_history_summarization_tool(conversation_history)
    summarization_agent = Agent[None, str](
        model=model,
        output_type=summarize,
        system_prompt=system_prompt,
        model_settings=settings,
        retries=retries,
    )
    try:
        ctx.print(stylize_faint("  📝 Rollup Conversation"), plain=True)
        summary_run = await run_agent_iteration(
            ctx=ctx,
            agent=summarization_agent,
            user_prompt=user_prompt,
            attachments=[],
            history_list=[],
            rate_limitter=rate_limitter,
            log_indent_level=2,
        )
        if summary_run and summary_run.result and summary_run.result.output:
            usage = summary_run.result.usage()
            ctx.print(
                stylize_faint(f"  📝 Rollup Conversation Token: {usage}"), plain=True
            )
            ctx.print(plain=True)
            ctx.log_info("History summarized and updated.")
        else:
            ctx.log_warning("History summarization failed or returned no data.")
    except BaseException as e:
        ctx.log_warning(f"Error during history summarization: {e}")
        traceback.print_exc()
    # Return the original summary if summarization fails
    return conversation_history


async def maybe_summarize_history(
    ctx: AnyContext,
    conversation_history: ConversationHistory,
    should_summarize_history_attr: BoolAttr | None,
    render_summarize_history: bool,
    history_summarization_token_threshold_attr: IntAttr | None,
    render_history_summarization_token_threshold: bool,
    model: "str | Model | None",
    model_settings: "ModelSettings | None",
    summarization_prompt: str,
    rate_limitter: LLMRateLimiter | None = None,
) -> ConversationHistory:
    """Summarizes history and updates context if enabled and threshold met."""
    shorten_history = replace_system_prompt_in_history(conversation_history.history)
    if should_summarize_history(
        ctx,
        shorten_history,
        should_summarize_history_attr,
        render_summarize_history,
        history_summarization_token_threshold_attr,
        render_history_summarization_token_threshold,
    ):
        original_history = conversation_history.history
        conversation_history.history = shorten_history
        conversation_history = await summarize_history(
            ctx=ctx,
            model=model,
            settings=model_settings,
            system_prompt=summarization_prompt,
            conversation_history=conversation_history,
            rate_limitter=rate_limitter,
        )
        conversation_history.history = original_history
        if (
            conversation_history.past_conversation_summary != ""
            and conversation_history.past_conversation_transcript != ""
        ):
            conversation_history.history = []
    return conversation_history
