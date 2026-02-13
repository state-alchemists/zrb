import re
from dataclasses import replace
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Sequence

from zrb.config.config import CFG
from zrb.context.any_context import zrb_print
from zrb.llm.agent.summarizer import (
    create_conversational_summarizer_agent,
    create_message_summarizer_agent,
)
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.config.limiter import is_turn_start as is_turn_start_impl
from zrb.llm.config.limiter import llm_limiter as default_llm_limiter
from zrb.llm.summarizer.chunk_processor import (
    chunk_and_summarize as chunk_and_summarize_impl,
)
from zrb.llm.summarizer.chunk_processor import (
    consolidate_summaries as consolidate_summaries_impl,
)
from zrb.llm.summarizer.history_splitter import (
    find_safe_split_index as find_safe_split_index_impl,
)
from zrb.llm.summarizer.history_splitter import get_tool_pairs as get_tool_pairs_impl
from zrb.llm.summarizer.history_splitter import is_split_safe as is_split_safe_impl
from zrb.llm.summarizer.history_splitter import (
    split_history,
)
from zrb.llm.summarizer.message_converter import message_to_text as message_to_text_impl
from zrb.llm.summarizer.message_converter import (
    model_request_to_text as model_request_to_text_impl,
)
from zrb.llm.summarizer.message_converter import (
    model_response_to_text as model_response_to_text_impl,
)
from zrb.llm.summarizer.message_processor import (
    process_message_for_summarization as process_message_for_summarization_impl,
)
from zrb.llm.summarizer.message_processor import (
    process_tool_return_part as process_tool_return_part_impl,
)
from zrb.llm.summarizer.text_summarizer import (
    summarize_long_text as summarize_long_text_impl,
)
from zrb.llm.summarizer.text_summarizer import (
    summarize_text,
)
from zrb.llm.summarizer.text_summarizer import (
    summarize_text_plain as summarize_text_plain_impl,
)
from zrb.util.cli.style import stylize_error, stylize_yellow
from zrb.util.markdown import make_markdown_section

if TYPE_CHECKING:
    from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, Part
else:
    ModelMessage = Any
    ModelRequest = Any
    ModelResponse = Any
    Part = Any


def create_summarizer_history_processor(
    conversational_agent: Any = None,
    message_agent: Any = None,
    limiter: "LLMLimiter | None" = None,
    conversational_token_threshold: int | None = None,
    message_token_threshold: int | None = None,
    summary_window: int | None = None,
    # Backward compatibility
    agent: Any = None,
    token_threshold: int | None = None,
) -> "Callable[[list[ModelMessage]], Awaitable[list[ModelMessage]]]":
    """
    Creates a history processor that auto-summarizes history when it exceeds `token_threshold`.
    """
    llm_limiter = limiter or default_llm_limiter
    if conversational_token_threshold is None:
        conversational_token_threshold = (
            token_threshold or CFG.LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD
        )
    if message_token_threshold is None:
        message_token_threshold = CFG.LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD
    if summary_window is None:
        summary_window = CFG.LLM_HISTORY_SUMMARIZATION_WINDOW

    async def process_history(messages: "list[ModelMessage]") -> "list[ModelMessage]":
        # 1. Summarize individual fat messages first
        try:
            messages = await summarize_messages(
                messages,
                agent=message_agent,
                limiter=llm_limiter,
                message_token_threshold=message_token_threshold,
            )
        except Exception as e:
            zrb_print(
                stylize_error(f"  Error processing messages in history processor: {e}"),
                plain=True,
            )
            # Continue with original messages if summarization fails

        # 2. Check if total history exceeds threshold
        try:
            current_tokens = llm_limiter.count_tokens(messages)
            is_short_enough = len(messages) <= summary_window
            is_within_tokens = current_tokens <= conversational_token_threshold
            if is_short_enough and is_within_tokens:
                return messages

            zrb_print(
                stylize_yellow(
                    (
                        f"\n  History limits exceeded (tokens: {current_tokens}/{conversational_token_threshold}, messages: {len(messages)}/{summary_window}). "
                        "Compressing conversation..."
                    )
                ),
                plain=True,
            )
            result = await summarize_history(
                messages,
                agent=conversational_agent or agent,
                summary_window=summary_window,
                limiter=llm_limiter,
                conversational_token_threshold=conversational_token_threshold,
            )
            if result != messages:
                new_tokens = llm_limiter.count_tokens(result)
                zrb_print(
                    stylize_yellow(
                        f"  Conversation compressed "
                        f"({new_tokens}/{conversational_token_threshold})"
                    ),
                    plain=True,
                )
            else:
                zrb_print(
                    stylize_error("  Cannot compress conversation..."), plain=True
                )
            return result
        except Exception as e:
            zrb_print(
                stylize_error(f"  Error processing history in history processor: {e}"),
                plain=True,
            )
            return messages

    return process_history


async def summarize_messages(
    messages: "list[ModelMessage]",
    agent: Any = None,
    limiter: "LLMLimiter | None" = None,
    message_token_threshold: int | None = None,
) -> "list[ModelMessage]":
    """
    Summarizes individual tool call results (and other parts) if they exceed the threshold.
    """
    try:
        llm_limiter = limiter or default_llm_limiter
        if message_token_threshold is None:
            message_token_threshold = CFG.LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD

        summarizer_agent = agent or create_message_summarizer_agent()
        new_messages = []
        for msg in messages:
            new_msg = await process_message_for_summarization_impl(
                msg, summarizer_agent, llm_limiter, message_token_threshold
            )
            new_messages.append(new_msg)
        return new_messages
    except Exception as e:
        zrb_print(stylize_error(f"  Error in summarize_messages: {e}"), plain=True)
        return messages


async def summarize_history(
    messages: "list[ModelMessage]",
    agent: Any = None,
    summary_window: int | None = None,
    limiter: "LLMLimiter | None" = None,
    conversational_token_threshold: int | None = None,
) -> "list[ModelMessage]":
    """
    Summarizes the history, keeping the last `summary_window` messages intact.
    Handles very large histories by summarizing in chunks.
    Returns a new list of messages where older messages are replaced by a summary.
    """
    try:
        # 1. Setup Configs
        llm_limiter = limiter or default_llm_limiter
        if conversational_token_threshold is None:
            conversational_token_threshold = (
                CFG.LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD
            )
        # Check for early exit ONLY if tokens are safe
        current_tokens = llm_limiter.count_tokens(messages)
        is_safe_length = len(messages) <= summary_window
        is_safe_tokens = current_tokens <= conversational_token_threshold
        if is_safe_length and is_safe_tokens:
            return messages
        to_summarize, to_keep = split_history(
            messages, summary_window, llm_limiter, conversational_token_threshold
        )
        if not to_summarize:
            return messages
        # 2. Iterative Summarization of Historical turns
        summarizer_agent = agent or create_conversational_summarizer_agent()
        summary_text = await chunk_and_summarize_impl(
            to_summarize, summarizer_agent, llm_limiter, conversational_token_threshold
        )
        # 3. Final Aggregation and potential re-summarization
        final_summary_tokens = llm_limiter.count_tokens(summary_text)
        # Check if we have multiple snapshots or if we are still near the threshold
        has_multiple_snapshots = summary_text.count("<state_snapshot>") > 1
        is_near_threshold = final_summary_tokens > (
            conversational_token_threshold * 0.8
        )
        if is_near_threshold or has_multiple_snapshots:
            summary_text = await consolidate_summaries_impl(
                summary_text,
                summarizer_agent,
                conversational_token_threshold,
                has_multiple_snapshots,
            )
        # 4. Create Result
        summary_message = _create_summary_model_request(summary_text)
        if summary_message is None:
            return messages
        return [summary_message] + to_keep
    except Exception as e:
        zrb_print(stylize_error(f"  Error in summarize_history: {e}"), plain=True)
        return messages


def _create_summary_model_request(summary_text: str) -> Any:
    """Construct a ModelRequest message from summary text."""
    from pydantic_ai.messages import ModelRequest, UserPromptPart

    try:
        return ModelRequest(
            parts=[
                UserPromptPart(
                    content=make_markdown_section(
                        "SYSTEM: Automated Context Restoration",
                        "This is an automated summary of the preceding conversation history to "
                        "preserve context within the token limit. Continue the conversation "
                        "based on the state snapshot below.\n\n"
                        f"{summary_text}",
                    )
                )
            ]
        )
    except Exception as e:
        zrb_print(stylize_error(f"  Failed to create summary message: {e}"), plain=True)
        return None


# Re-export public functions from submodules
message_to_text = message_to_text_impl

# Note: Private functions are no longer re-exported.
# Tests should import from zrb.llm.summarizer module instead.
# is_turn_start is available from zrb.llm.config.limiter
