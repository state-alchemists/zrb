import re
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from zrb.config.config import CFG
from zrb.context.any_context import zrb_print
from zrb.llm.agent.summarizer import (
    create_conversational_summarizer_agent,
    create_message_summarizer_agent,
)
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


async def summarize_messages(
    messages: "list[ModelMessage]",
    agent: Any = None,
    limiter: "LLMLimiter | None" = None,
    message_token_threshold: int | None = None,
) -> "list[ModelMessage]":
    """
    Summarizes individual tool call results (and other parts) if they exceed the threshold.
    """
    from pydantic_ai.messages import (
        ModelRequest,
        ToolReturnPart,
    )

    llm_limiter = limiter or default_llm_limiter
    if message_token_threshold is None:
        message_token_threshold = CFG.LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD

    summarizer_agent = agent or create_message_summarizer_agent()
    new_messages = []
    for msg in messages:
        if isinstance(msg, ModelRequest):
            new_parts = []
            msg_modified = False
            for p in msg.parts:
                if isinstance(p, ToolReturnPart):
                    content_tokens = llm_limiter.count_tokens(p.content)
                    if content_tokens > message_token_threshold:
                        zrb_print(
                            stylize_yellow(
                                f"  Summarizing fat tool result ({content_tokens} tokens)..."
                            ),
                            plain=True,
                        )
                        summary = await _summarize_text_plain(
                            p.content,
                            summarizer_agent,
                            llm_limiter,
                            message_token_threshold,
                        )
                        new_parts.append(
                            p.model_copy(
                                update={
                                    "content": f"SUMMARY of tool result:\n{summary}"
                                }
                            )
                        )
                        msg_modified = True
                        continue
                new_parts.append(p)
            if msg_modified:
                new_messages.append(msg.model_copy(update={"parts": new_parts}))
                continue
        new_messages.append(msg)
    return new_messages


async def _summarize_text_plain(
    text: str, agent: Any, limiter: "LLMLimiter", threshold: int
) -> str:
    """Summarizes a long text into a plain summary, handling chunks if necessary."""
    if limiter.count_tokens(text) <= threshold:
        result = await agent.run(text)
        return result.output

    # Chunking logic for extremely large text
    remaining_text = text
    summaries = []
    internal_limit = int(threshold * 0.8)

    while remaining_text:
        chunk = limiter.truncate_text(remaining_text, internal_limit)
        result = await agent.run(f"Summarize this part of a document:\n\n{chunk}")
        summaries.append(result.output)
        chunk_len = len(chunk)
        remaining_text = remaining_text[chunk_len:]
        if not remaining_text.strip():
            break

    if len(summaries) == 1:
        return summaries[0]

    consolidated = await agent.run(
        "Consolidate these partial summaries into a single, cohesive summary:\n\n"
        + "\n".join(summaries)
    )
    return consolidated.output


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
    # 1. Setup Configs
    if summary_window is None:
        summary_window = CFG.LLM_HISTORY_SUMMARIZATION_WINDOW
    llm_limiter = limiter or default_llm_limiter
    if conversational_token_threshold is None:
        conversational_token_threshold = (
            CFG.LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD
        )

    # Check for early exit ONLY if tokens are safe
    current_tokens = llm_limiter.count_tokens(messages)
    if (
        len(messages) <= summary_window
        and current_tokens <= conversational_token_threshold
    ):
        return messages

    # 2. Split history into 'to_summarize' and 'to_keep'
    # We always protect the last 2 messages (the active turn) as a bare minimum
    # to prevent the agent from losing its immediate context/data.
    split_idx = _get_split_index(messages, summary_window)
    if split_idx <= 0:
        # Fallback: If no clean turn start found, protect the last 2 messages
        split_idx = max(0, len(messages) - 2)

    to_summarize = messages[:split_idx]
    to_keep = messages[split_idx:]

    # 3. Handle 'to_summarize'
    if not to_summarize:
        # If nothing to summarize (short history), return as-is.
        # We let the LLM's context window handle 'fat' recent messages.
        return messages

    # 4. Iterative Summarization of Historical turns
    summarizer_agent = agent or create_conversational_summarizer_agent()
    summary_text = await _chunk_and_summarize(
        to_summarize, summarizer_agent, llm_limiter, conversational_token_threshold
    )

    # 4. Final Aggregation and potential re-summarization
    final_summary_tokens = llm_limiter.count_tokens(summary_text)

    # Check if we have multiple snapshots or if we are still near the threshold
    has_multiple_snapshots = summary_text.count("<state_snapshot>") > 1
    is_near_threshold = final_summary_tokens > (conversational_token_threshold * 0.8)

    if is_near_threshold or has_multiple_snapshots:
        if has_multiple_snapshots:
            zrb_print(
                stylize_yellow("  Consolidating multiple snapshots..."), plain=True
            )
        else:
            zrb_print(
                stylize_yellow("  Aggressively re-compressing summary..."), plain=True
            )

        summary_text = await _summarize_text(
            "Consolidate the following conversation state snapshots into a single, cohesive <state_snapshot>.\n"
            f"IMPORTANT: Be extremely concise and dense. Your goal is to fit all critical knowledge into less than {conversational_token_threshold // 2} tokens.\n"
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

    # CHUNK LIMIT: For normal messages, group them up to 90% of threshold.
    chunk_token_limit = int(token_threshold * 0.9)

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
    output = result.output
    # Ensure output is a valid state snapshot (only if we didn't override prompt)
    if "<state_snapshot>" in output and "</state_snapshot>" in output:
        match = re.search(
            r"(<state_snapshot>.*</state_snapshot>)", output, re.DOTALL | re.MULTILINE
        )
        if match:
            return match.group(1)
    return output


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
                        "preserve context within the token limit. Continue the conversation based on the state snapshot below.\n\n"
                        f"{summary_text}",
                    )
                )
            ]
        )
    except Exception as e:
        zrb_print(stylize_error(f"  Failed to create summary message: {e}"), plain=True)
        return None


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

    async def process_history(messages: "list[ModelMessage]") -> "list[ModelMessage]":
        # 1. Summarize individual fat messages first
        messages = await summarize_messages(
            messages,
            agent=message_agent,
            limiter=llm_limiter,
            message_token_threshold=message_token_threshold,
        )

        # 2. Check if total history exceeds threshold
        current_tokens = llm_limiter.count_tokens(messages)
        if current_tokens <= conversational_token_threshold:
            return messages

        zrb_print(
            stylize_yellow(
                (
                    f"\n  Token threshold exceeded ({current_tokens}/{conversational_token_threshold}). "
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
                    f"  Conversation compressed ({new_tokens}/{conversational_token_threshold})"
                ),
                plain=True,
            )
        else:
            zrb_print(stylize_error("  Cannot compress conversation..."), plain=True)
        return result

    return process_history
