import re
from dataclasses import replace
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Sequence

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
                        f"\n  Token threshold exceeded "
                        f"({current_tokens}/{conversational_token_threshold}). "
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
            new_msg = await _process_message_for_summarization(
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
        if summary_window is None:
            summary_window = CFG.LLM_HISTORY_SUMMARIZATION_WINDOW
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
        to_summarize, to_keep = _split_history(
            messages, summary_window, llm_limiter, conversational_token_threshold
        )
        if not to_summarize:
            return messages
        # 2. Iterative Summarization of Historical turns
        summarizer_agent = agent or create_conversational_summarizer_agent()
        summary_text = await _chunk_and_summarize(
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
            summary_text = await _consolidate_summaries(
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


def message_to_text(msg: Any) -> str:
    """Convert a pydantic_ai message to a readable text representation for summarization."""
    from pydantic_ai.messages import ModelRequest, ModelResponse

    if isinstance(msg, ModelRequest):
        return _model_request_to_text(msg)
    if isinstance(msg, ModelResponse):
        return _model_response_to_text(msg)
    # Fallback for unknown message types
    try:
        return str(msg)
    except Exception:
        return f"[Unconvertible message of type: {type(msg).__name__}]"


async def _process_message_for_summarization(
    msg: ModelMessage, agent: Any, limiter: LLMLimiter, threshold: int
) -> ModelMessage:
    from pydantic_ai.messages import ModelRequest, ToolReturnPart

    if not isinstance(msg, ModelRequest):
        return msg
    new_parts = []
    msg_modified = False
    # Safely get parts with default
    msg_parts = getattr(msg, "parts", [])
    for p in msg_parts:
        if not isinstance(p, ToolReturnPart):
            new_parts.append(p)
            continue
        new_part, modified = await _process_tool_return_part(
            p, agent, limiter, threshold
        )
        new_parts.append(new_part)
        if modified:
            msg_modified = True
    if msg_modified:
        return replace(msg, parts=new_parts)
    return msg


async def _process_tool_return_part(
    part: Any, agent: Any, limiter: LLMLimiter, threshold: int
) -> tuple[Any, bool]:
    # Safely get content with default
    content = getattr(part, "content", None)
    # Skip if content is not a string (e.g., dict)
    if not isinstance(content, str):
        return part, False
    # Skip if already summarized or truncated
    is_summary = content.startswith("SUMMARY of tool result:")
    is_truncated = content.startswith("TRUNCATED tool result:")
    if is_summary or is_truncated:
        return part, False
    content_tokens = limiter.count_tokens(content)
    if content_tokens <= threshold:
        return part, False
    zrb_print(
        stylize_yellow(f"  Summarizing fat tool result ({content_tokens} tokens)..."),
        plain=True,
    )
    # Calculate available tokens for summary (accounting for prefix)
    prefix = "SUMMARY of tool result:\n"
    prefix_tokens = limiter.count_tokens(prefix)
    available_tokens = threshold - prefix_tokens
    # Ensure we have positive available tokens
    if available_tokens <= 0:
        zrb_print(
            stylize_error(
                f"  Warning: Token threshold ({threshold}) too low for summary prefix ({prefix_tokens} tokens)"
            ),
            plain=True,
        )
        # Keep original but truncated
        truncated = limiter.truncate_text(content, threshold)
        new_part = replace(part, content=f"TRUNCATED tool result:\n{truncated}")
        return new_part, True
    try:
        summary = await _summarize_text_plain(content, agent, limiter, available_tokens)
        new_part = replace(part, content=f"SUMMARY of tool result:\n{summary}")
        return new_part, True
    except Exception as e:
        zrb_print(stylize_error(f"  Error summarizing tool result: {e}"), plain=True)
        return part, False


async def _summarize_text_plain(
    text: str, agent: Any, limiter: "LLMLimiter", threshold: int
) -> str:
    """Summarizes a long text into a plain summary, handling chunks if necessary."""
    # Ensure text is a string
    if not isinstance(text, str):
        try:
            return str(text)
        except Exception:
            return "[Unconvertible content]"
    # Ensure threshold is positive
    if threshold <= 0:
        return "[Threshold too low for summarization]"
    text_tokens = limiter.count_tokens(text)
    if text_tokens <= threshold:
        return await _summarize_short_text(text, agent, limiter, threshold)
    return await _summarize_long_text(text, agent, limiter, threshold)


async def _summarize_short_text(
    text: str, agent: Any, limiter: LLMLimiter, threshold: int
) -> str:
    try:
        result = await agent.run(text)
        summary = getattr(result, "output", "")
        if not isinstance(summary, str):
            summary = str(summary) if summary is not None else ""
        # Ensure summary doesn't exceed threshold
        summary_tokens = limiter.count_tokens(summary)
        if summary_tokens > threshold:
            # Truncate if summary is longer than threshold
            summary = limiter.truncate_text(summary, threshold)
        return summary
    except Exception as e:
        zrb_print(stylize_error(f"  Error during summarization: {e}"), plain=True)
        raise e


async def _summarize_long_text(
    text: str, agent: Any, limiter: LLMLimiter, threshold: int
) -> str:
    # Chunking logic for extremely large text
    remaining_text = text
    summaries = []
    # Use 70% of threshold for chunks to leave room for consolidation
    chunk_limit = max(1, int(threshold * 0.7))
    while remaining_text:
        chunk = limiter.truncate_text(remaining_text, chunk_limit)
        try:
            result = await agent.run(f"Summarize this part of a document:\n\n{chunk}")
            chunk_summary = getattr(result, "output", "")
            if not isinstance(chunk_summary, str):
                chunk_summary = str(chunk_summary) if chunk_summary is not None else ""
            # Ensure chunk summary doesn't exceed chunk limit
            chunk_summary_tokens = limiter.count_tokens(chunk_summary)
            if chunk_summary_tokens > chunk_limit:
                chunk_summary = limiter.truncate_text(chunk_summary, chunk_limit)
            summaries.append(chunk_summary)
        except Exception as e:
            zrb_print(
                stylize_error(f"  Error during chunk summarization: {e}"), plain=True
            )
            raise e
        chunk_len = len(chunk)
        remaining_text = remaining_text[chunk_len:]
        if not remaining_text.strip():
            break
    if not summaries:
        return "[No summary generated]"
    if len(summaries) == 1:
        final_summary = summaries[0]
    else:
        try:
            summaries_text = "\n".join(summaries)
            prompt = (
                "Consolidate these partial summaries into a single, cohesive summary:\n\n"
                f"{summaries_text}"
            )
            consolidated = await agent.run(prompt)
            final_summary = getattr(consolidated, "output", "")
            if not isinstance(final_summary, str):
                final_summary = str(final_summary) if final_summary is not None else ""
        except Exception as e:
            zrb_print(stylize_error(f"  Error during consolidation: {e}"), plain=True)
            raise e
    # Final check: ensure consolidated summary doesn't exceed threshold
    final_tokens = limiter.count_tokens(final_summary)
    if final_tokens > threshold:
        final_summary = limiter.truncate_text(final_summary, threshold)
    return final_summary


def _split_history(
    messages: list[Any],
    summary_window: int,
    limiter: LLMLimiter,
    conversational_token_threshold: int,
) -> tuple[list[Any], list[Any]]:
    # We always protect the last 2 messages (the active turn) as a bare minimum
    # to prevent the agent from losing its immediate context/data.
    split_idx = _get_split_index(messages, summary_window)
    if split_idx <= 0:
        # Fallback: If no clean turn start found, protect the last 2 messages
        split_idx = max(0, len(messages) - 2)
    to_summarize = messages[:split_idx]
    to_keep = messages[split_idx:]
    # Handle 'to_summarize'
    if not to_summarize:
        # If nothing to summarize (short history) but token count is high,
        # we need to find a safe split point that doesn't break tool call/return pairs.
        split_idx = _find_safe_split_index(
            messages, limiter, conversational_token_threshold
        )
        if split_idx > 0:
            to_summarize = messages[:split_idx]
            to_keep = messages[split_idx:]
        else:
            # No safe split found - we have to summarize everything
            # This is risky but necessary when token count is too high
            zrb_print(
                stylize_yellow(
                    "  Warning: No safe split point found, summarizing entire history..."
                ),
                plain=True,
            )
            to_summarize = messages
            to_keep = []
    return to_summarize, to_keep


async def _chunk_and_summarize(
    messages: list[Any], agent: Any, limiter: "LLMLimiter", token_threshold: int
) -> str:
    """Break history into chunks and summarize them iteratively."""

    # Pre-calculate texts
    history_texts = []
    for m in messages:
        try:
            history_texts.append(message_to_text(m))
        except Exception as e:
            zrb_print(
                stylize_error(f"  Error converting message to text: {e}"), plain=True
            )
            history_texts.append(str(m))
    summaries = []
    current_chunk = []
    current_chunk_tokens = 0
    chunk_token_limit = max(1, int(token_threshold * 0.9))

    async def _flush_chunk():
        if not current_chunk:
            return
        zrb_print(
            stylize_yellow(f"  Compressing chunk of {len(current_chunk)} messages..."),
            plain=True,
        )
        try:
            summary = await _summarize_text("\n".join(current_chunk), agent)
            summaries.append(summary)
        except Exception as e:
            zrb_print(stylize_error(f"  Error summarizing chunk: {e}"), plain=True)
            raise e

    for text in history_texts:
        text_tokens = limiter.count_tokens(text)
        if current_chunk and (current_chunk_tokens + text_tokens > chunk_token_limit):
            await _flush_chunk()
            current_chunk = []
            current_chunk_tokens = 0
        current_chunk.append(text)
        current_chunk_tokens += text_tokens
    await _flush_chunk()

    return "\n\n".join(summaries) if summaries else "[No summaries generated]"


async def _consolidate_summaries(
    summary_text: str,
    agent: Any,
    conversational_token_threshold: int,
    has_multiple_snapshots: bool,
) -> str:
    if has_multiple_snapshots:
        zrb_print(stylize_yellow("  Consolidating multiple snapshots..."), plain=True)
    else:
        zrb_print(
            stylize_yellow("  Aggressively re-compressing summary..."),
            plain=True,
        )

    return await _summarize_text(
        "Consolidate the following conversation state snapshots into a single, cohesive "
        "<state_snapshot>.\n"
        "IMPORTANT: Be extremely concise and dense. Your goal is to fit all critical "
        f"knowledge into less than {conversational_token_threshold // 2} tokens.\n"
        f"{summary_text}",
        agent,
    )


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


def _model_request_to_text(msg: ModelRequest) -> str:
    from pydantic_ai.messages import (
        AudioUrl,
        BinaryContent,
        DocumentUrl,
        ImageUrl,
        SystemPromptPart,
        ToolReturnPart,
        UserPromptPart,
        VideoUrl,
    )

    parts = []
    # Safely get parts with default
    msg_parts = getattr(msg, "parts", [])
    for p in msg_parts:
        if isinstance(p, UserPromptPart):
            content = getattr(p, "content", "")
            if isinstance(content, str):
                parts.append(f"User: {content}")
            elif isinstance(content, Sequence):
                for item in content:
                    if isinstance(item, str):
                        parts.append(f"User: {item}")
                    elif isinstance(item, ImageUrl):
                        parts.append(f"[Image URL: {item.url}]")
                    elif isinstance(item, BinaryContent):
                        media_type = getattr(item, "media_type", "unknown")
                        parts.append(f"[Binary Content: {media_type}]")
                    elif isinstance(item, AudioUrl):
                        parts.append(f"[Audio URL: {item.url}]")
                    elif isinstance(item, VideoUrl):
                        parts.append(f"[Video URL: {item.url}]")
                    elif isinstance(item, DocumentUrl):
                        parts.append(f"[Document URL: {item.url}]")
                    else:
                        parts.append(f"[Unknown User Content: {type(item).__name__}]")
            else:
                parts.append(f"User: {str(content)}")
        elif isinstance(p, ToolReturnPart):
            tool_name = getattr(p, "tool_name", "unknown_tool")
            content = getattr(p, "content", None)
            if content is not None:
                content_str = str(content) if not isinstance(content, str) else content
                parts.append(f"Tool Result ({tool_name}): {content_str}")
            else:
                parts.append(f"Tool Result ({tool_name}): [No content]")
        elif isinstance(p, SystemPromptPart):
            content = getattr(p, "content", "")
            if content is not None:
                parts.append(f"System: {content}")
        else:
            # Fallback for unknown part types
            parts.append(f"[Unknown part type: {type(p).__name__}]")
    return "\n".join(parts) if parts else "[Empty ModelRequest]"


def _model_response_to_text(msg: ModelResponse) -> str:
    from pydantic_ai.messages import FilePart, TextPart, ToolCallPart, ToolReturnPart

    parts = []
    msg_parts = getattr(msg, "parts", [])
    for p in msg_parts:
        if isinstance(p, TextPart):
            content = getattr(p, "content", "")
            if content is not None:
                parts.append(f"AI: {content}")
        elif isinstance(p, ToolCallPart):
            tool_name = getattr(p, "tool_name", "unknown_tool")
            args = getattr(p, "args", {})
            args_str = str(args) if args is not None else "{}"
            tool_call_id = getattr(p, "tool_call_id", "unknown_id")
            parts.append(f"AI Tool Call [{tool_call_id}]: {tool_name}({args_str})")
        elif isinstance(p, FilePart):
            # FilePart has 'content' which is likely BinaryContent
            content = getattr(p, "content", None)
            media_type = "unknown"
            if content:
                media_type = getattr(content, "media_type", "unknown")
            parts.append(f"[AI Generated File: {media_type}]")
        elif isinstance(p, ToolReturnPart):
            # Tool returns can also appear in ModelResponse in some cases
            tool_name = getattr(p, "tool_name", "unknown_tool")
            content = getattr(p, "content", None)
            if content is not None:
                content_str = str(content) if not isinstance(content, str) else content
                parts.append(f"AI Tool Result ({tool_name}): {content_str}")
        else:
            parts.append(f"[Unknown response part: {type(p).__name__}]")
    return "\n".join(parts) if parts else "[Empty ModelResponse]"


def _get_split_index(messages: list[Any], summary_window: int) -> int:
    """Find the last clean turn start before the summary window."""
    start_search_idx = max(0, len(messages) - summary_window - 1)
    for i in range(start_search_idx, 0, -1):
        if is_turn_start(messages[i]):
            return i
    return -1


def _find_safe_split_index(
    messages: list[Any], limiter: "LLMLimiter", token_threshold: int
) -> int:
    """
    Find a safe split index that doesn't break tool call/return pairs.
    Returns -1 if no safe split is possible.

    Strategy:
    1. Try to keep as many recent messages as possible while staying under token limit
    2. Ensure tool call/return pairs are not separated
    3. Prefer splits at conversation turn boundaries
    """
    tool_pairs = _get_tool_pairs(messages)

    # Generate split indices to check:
    # 1. Backwards from end (prefer keeping more context)
    # 2. Forwards from start (fallback to keeping less)
    check_indices = []
    # Try to keep as much recent context as possible (backwards from end)
    check_indices.extend(range(len(messages) - 1, 0, -1))
    # If not found, try from the beginning (keeping fewer messages)
    check_indices.extend(range(1, len(messages)))

    for split_idx in check_indices:
        to_keep = messages[split_idx:]
        tokens_to_keep = limiter.count_tokens(to_keep)

        # Check if this split is safe (doesn't break tool pairs)
        is_safe = _is_split_safe(messages, split_idx, tool_pairs)
        at_turn_boundary = is_turn_start(messages[split_idx])

        if is_safe and tokens_to_keep <= token_threshold * 0.7:  # Leave 30% room
            # Prefer turn boundaries, but if we are in the "fallback" phase (forward search),
            # we accept any safe split if we haven't found a better one yet.
            # However, since we search backwards first, the first valid result we hit
            # IS the one that keeps the most context.

            # Optimization: If we find a turn boundary in the backward pass, take it immediately.
            if at_turn_boundary:
                return split_idx

            # If not a turn boundary, we could continue searching for one.
            # But we need to store this valid split as a fallback.
            # For simplicity in this refactor, if we are in the backward pass and find a safe split,
            # we might want to keep searching for a turn boundary nearby.
            # But the original logic prioritized finding *any* safe split if turn boundary search failed.

            # Let's stick to: if it's safe and small enough, it's a candidate.
            # If it's ALSO a turn boundary, it's a WINNER.
            pass

    # Re-implementing the prioritization logic more cleanly:

    # Phase 1: Search backwards for a Safe Split at a Turn Boundary
    # 2. Check if fit.
    #    - If DOES NOT fit: Stop. The previous valid split (larger index) was the best we could do.
    #      (Because any smaller index will have even more tokens).
    # 3. If fits:
    #    - Check if safe.
    #    - If safe:
    #      - If boundary: Update `best_boundary_split`.
    #      - Always Update `best_safe_split`.
    # 4. After loop (or break), return `best_boundary_split` if exists, else `best_safe_split`.

    best_boundary_split = -1
    best_safe_split = -1

    for split_idx in range(len(messages) - 1, 0, -1):
        to_keep = messages[split_idx:]
        tokens_to_keep = limiter.count_tokens(to_keep)

        if tokens_to_keep > token_threshold * 0.7:
            # We reached the point where it's too big.
            # We can't keep more context. Stop searching lower indices.
            break

        if _is_split_safe(messages, split_idx, tool_pairs):
            best_safe_split = split_idx
            if is_turn_start(messages[split_idx]):
                best_boundary_split = split_idx

    if best_boundary_split != -1:
        return best_boundary_split
    return best_safe_split


def _get_tool_pairs(messages: list[Any]) -> dict[str, dict[str, int | None]]:
    from pydantic_ai.messages import ToolCallPart, ToolReturnPart

    tool_pairs = {}
    for i, msg in enumerate(messages):
        msg_parts = getattr(msg, "parts", [])
        for part in msg_parts:
            if isinstance(part, ToolCallPart):
                tool_call_id = getattr(part, "tool_call_id", None)
                if tool_call_id is not None:
                    tool_pairs[tool_call_id] = {"call_idx": i, "return_idx": None}
            elif isinstance(part, ToolReturnPart):
                tool_call_id = getattr(part, "tool_call_id", None)
                if tool_call_id is not None:
                    if tool_call_id in tool_pairs:
                        tool_pairs[tool_call_id]["return_idx"] = i
                    else:
                        # Orphaned return or return preceding call (unlikely but handle)
                        tool_pairs[tool_call_id] = {"call_idx": None, "return_idx": i}
    return tool_pairs


def _is_split_safe(
    messages: list[Any], split_idx: int, tool_pairs: dict[str, dict[str, int | None]]
) -> bool:
    """
    Check if splitting at the given index would break tool call/return pairs.
    """
    for indices in tool_pairs.values():
        call_idx = indices["call_idx"]
        return_idx = indices["return_idx"]

        # If we have both call and return
        if call_idx is not None and return_idx is not None:
            call_before_split = call_idx < split_idx
            return_before_split = return_idx < split_idx

            # They must be on the same side of the split
            if call_before_split != return_before_split:
                return False

        # If we have only a call (no return yet)
        elif call_idx is not None and return_idx is None:
            # Tool call without return - if it's before split, we'd lose it
            if call_idx < split_idx:
                return False

        # If we have only a return (no call)
        elif call_idx is None and return_idx is not None:
            return False

    return True


async def _summarize_text(text: str, agent: Any, partial: bool = False) -> str:
    """Helper to run the summarizer agent on a block of text."""
    prompt_prefix = (
        "Summarize this partial conversation history:\n"
        if partial
        else "Summarize this conversation history:\n"
    )

    try:
        result = await agent.run(f"{prompt_prefix}{text}")
        output = getattr(result, "output", "")
        if not isinstance(output, str):
            output = str(output) if output is not None else ""

        # Ensure output is a valid state snapshot (only if we didn't override prompt)
        if "<state_snapshot>" in output and "</state_snapshot>" in output:
            match = re.search(
                r"(<state_snapshot>.*</state_snapshot>)",
                output,
                re.DOTALL | re.MULTILINE,
            )
            if match:
                return match.group(1)
        return output
    except Exception as e:
        zrb_print(stylize_error(f"  Error in _summarize_text: {e}"), plain=True)
        raise e
