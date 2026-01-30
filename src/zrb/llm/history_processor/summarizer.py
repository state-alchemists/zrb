import sys
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from zrb.config.config import CFG
from zrb.context.any_context import zrb_print
from zrb.llm.agent.summarizer import create_summarizer_agent
from zrb.llm.config.limiter import LLMLimiter, is_turn_start
from zrb.llm.config.limiter import llm_limiter as default_llm_limiter
from zrb.util.cli.style import stylize_error, stylize_yellow
from zrb.util.markdown import make_markdown_section

if TYPE_CHECKING:
    from pydantic_ai.messages import ModelMessage
else:
    ModelMessage = Any


def message_to_text(msg: Any) -> str:
    """Convert a pydantic_ai message to a readable text representation for summarization."""
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        TextPart,
        ToolCallPart,
        ToolReturnPart,
        UserPromptPart,
    )

    if isinstance(msg, ModelRequest):
        parts = []
        for p in msg.parts:
            if isinstance(p, UserPromptPart):
                parts.append(f"User: {p.content}")
            elif isinstance(p, ToolReturnPart):
                parts.append(f"Tool Result ({p.tool_name}): {p.content}")
        return "\n".join(parts)
    if isinstance(msg, ModelResponse):
        parts = []
        for p in msg.parts:
            if isinstance(p, TextPart):
                parts.append(f"AI: {p.content}")
            elif isinstance(p, ToolCallPart):
                parts.append(f"AI Tool Call: {p.tool_name}({p.args})")
        return "\n".join(parts)
    return str(msg)


async def summarize_history(
    messages: "list[ModelMessage]",
    agent: Any = None,
    summary_window: int | None = None,
    limiter: "LLMLimiter | None" = None,
    token_threshold: int | None = None,
) -> "list[ModelMessage]":
    """
    Summarizes the history, keeping the last `summary_window` messages intact.
    Handles very large histories by summarizing in chunks.
    Returns a new list of messages where older messages are replaced by a summary.
    """
    # 1. Setup Configs
    if summary_window is None:
        summary_window = CFG.LLM_HISTORY_SUMMARIZATION_WINDOW
    llm_limiter = limiter or default_llm_limiter
    if token_threshold is None:
        token_threshold = CFG.LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD

    # Check for early exit ONLY if tokens are safe
    current_tokens = llm_limiter.count_tokens(messages)
    if len(messages) <= summary_window and current_tokens <= token_threshold:
        return messages

    # 2. Strict Splitting
    if len(messages) <= summary_window and current_tokens > token_threshold:
        # Emergency: Window is small but tokens are huge. Summarize everything.
        split_idx = len(
            messages
        )  # Initially assume we keep everything, but logic below will fix it
        to_summarize = messages
        to_keep = []
        zrb_print(
            stylize_yellow(
                "  Recent history is too large. Aggressively summarizing..."
            ),
            plain=True,
        )
    else:
        split_idx = _get_split_index(messages, summary_window)
        if split_idx > 0:
            to_summarize = messages[:split_idx]
            to_keep = messages[split_idx:]
        else:
            zrb_print(
                stylize_yellow(
                    "  No clean split point found, summarizing entire history..."
                ),
                plain=True,
            )
            to_summarize = messages
            to_keep = []

    # 3. Safety Check: Is the "kept" part still too big?
    if to_keep and llm_limiter.count_tokens(to_keep) > token_threshold:
        zrb_print(
            stylize_yellow(
                "  Protected window is too large. Summarizing everything..."
            ),
            plain=True,
        )
        to_summarize = messages
        to_keep = []

    if not to_summarize:
        # This should rarely happen given the checks above, but as a fallback
        zrb_print(stylize_error("  Cannot find anything to summarize..."), plain=True)
        return messages

    # 4. Iterative Summarization
    summarizer_agent = agent or create_summarizer_agent()
    summary_text = await _chunk_and_summarize(
        to_summarize, summarizer_agent, llm_limiter, token_threshold
    )

    # 4. Final Aggregation and potential re-summarization
    final_summary_tokens = llm_limiter.count_tokens(summary_text)
    if final_summary_tokens > token_threshold:
        zrb_print(stylize_yellow("  Re-compressing summaries..."), plain=True)
        summary_text = await _summarize_text(
            "Summarize the following conversation summaries into a cohesive overview:\n"
            f"{summary_text}",
            summarizer_agent,
        )

    # 5. Create Result
    summary_message = _create_summary_model_request(summary_text)
    if summary_message is None:
        return messages

    return [summary_message] + to_keep


def _get_split_index(messages: list[Any], summary_window: int) -> int:
    """Find the last clean turn start before the summary window."""
    start_search_idx = max(0, len(messages) - summary_window)
    for i in range(start_search_idx, 0, -1):
        if is_turn_start(messages[i]):
            return i
    return -1


async def _chunk_and_summarize(
    messages: list[Any], agent: Any, limiter: "LLMLimiter", token_threshold: int
) -> str:
    """Break history into chunks and summarize them iteratively."""
    history_texts = [message_to_text(m) for m in messages]
    summaries = []
    current_chunk_texts = []
    current_chunk_tokens = 0
    chunk_token_limit = token_threshold // 2

    for text in history_texts:
        text_tokens = limiter.count_tokens(text)

        if current_chunk_texts and (
            current_chunk_tokens + text_tokens > chunk_token_limit
        ):
            zrb_print(
                stylize_yellow(
                    f"  Compressing chunk of {len(current_chunk_texts)} messages..."
                ),
                plain=True,
            )
            summaries.append(
                await _summarize_text("\n".join(current_chunk_texts), agent)
            )
            current_chunk_texts = [text]
            current_chunk_tokens = text_tokens
        else:
            current_chunk_texts.append(text)
            current_chunk_tokens += text_tokens

        if text_tokens > chunk_token_limit:
            zrb_print(
                stylize_yellow("  Summarizing a very long message..."), plain=True
            )
            truncated_text = limiter.truncate_text(text, chunk_token_limit)
            summary = await _summarize_text(truncated_text, agent, partial=True)
            summaries.append(summary)
            current_chunk_texts = []
            current_chunk_tokens = 0

    if current_chunk_texts:
        zrb_print(
            stylize_yellow(
                f"  Compressing final chunk of {len(current_chunk_texts)} messages..."
            ),
            plain=True,
        )
        summaries.append(await _summarize_text("\n".join(current_chunk_texts), agent))

    return "\n\n".join(summaries)


async def _summarize_text(text: str, agent: Any, partial: bool = False) -> str:
    """Helper to run the summarizer agent on a block of text."""
    prompt_prefix = (
        "Summarize this partial conversation history:\n"
        if partial
        else "Summarize this conversation history:\n"
    )
    result = await agent.run(f"{prompt_prefix}{text}")
    return result.output


def _create_summary_model_request(summary_text: str) -> Any:
    """Construct a ModelRequest message from summary text."""
    from pydantic_ai.messages import ModelRequest, UserPromptPart

    try:
        return ModelRequest(
            parts=[
                UserPromptPart(
                    content=make_markdown_section(
                        "Summary of earlier conversation", summary_text
                    )
                )
            ]
        )
    except Exception as e:
        zrb_print(stylize_error(f"  Failed to create summary message: {e}"), plain=True)
        return None


def create_summarizer_history_processor(
    agent: Any = None,
    limiter: "LLMLimiter | None" = None,
    token_threshold: int | None = None,
    summary_window: int | None = None,
) -> "Callable[[list[ModelMessage]], Awaitable[list[ModelMessage]]]":
    """
    Creates a history processor that auto-summarizes history when it exceeds `token_threshold`.
    """
    llm_limiter = limiter or default_llm_limiter
    if token_threshold is None:
        token_threshold = CFG.LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD

    async def process_history(messages: "list[ModelMessage]") -> "list[ModelMessage]":
        current_tokens = llm_limiter.count_tokens(messages)
        if current_tokens <= token_threshold:
            return messages
        zrb_print(
            stylize_yellow(
                (
                    f"\n  Token threshold exceeded ({current_tokens}/{token_threshold}). "
                    "Compressing conversation..."
                )
            ),
            plain=True,
        )
        result = await summarize_history(
            messages,
            agent=agent,
            summary_window=summary_window,
            limiter=llm_limiter,
            token_threshold=token_threshold,
        )
        if result != messages:
            new_tokens = llm_limiter.count_tokens(result)
            zrb_print(
                stylize_yellow(
                    f"  Conversation compressed ({new_tokens}/{token_threshold})"
                ),
                plain=True,
            )
        else:
            zrb_print(stylize_error("  Cannot compress conversation..."), plain=True)
        return result

    return process_history
