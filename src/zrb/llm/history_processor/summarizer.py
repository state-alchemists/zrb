import re
from dataclasses import replace
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
        FilePart,
        ImagePart,
        ModelRequest,
        ModelResponse,
        SystemPromptPart,
        TextPart,
        ToolCallPart,
        ToolReturnPart,
        UserPromptPart,
    )

    if isinstance(msg, ModelRequest):
        parts = []
        # Safely get parts with default
        msg_parts = getattr(msg, "parts", [])
        for p in msg_parts:
            if isinstance(p, UserPromptPart):
                content = getattr(p, "content", "")
                if content is not None:
                    parts.append(f"User: {content}")
            elif isinstance(p, ToolReturnPart):
                tool_name = getattr(p, "tool_name", "unknown_tool")
                content = getattr(p, "content", None)
                if content is not None:
                    content_str = (
                        str(content) if not isinstance(content, str) else content
                    )
                    parts.append(f"Tool Result ({tool_name}): {content_str}")
                else:
                    parts.append(f"Tool Result ({tool_name}): [No content]")
            elif isinstance(p, SystemPromptPart):
                content = getattr(p, "content", "")
                if content is not None:
                    parts.append(f"System: {content}")
            elif isinstance(p, ImagePart):
                description = getattr(p, "description", "No description")
                parts.append(f"[Image: {description}]")
            elif isinstance(p, FilePart):
                filename = getattr(p, "filename", "Unknown file")
                parts.append(f"[File: {filename}]")
            else:
                # Fallback for unknown part types
                parts.append(f"[Unknown part type: {type(p).__name__}]")
        return "\n".join(parts) if parts else "[Empty ModelRequest]"

    if isinstance(msg, ModelResponse):
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
            elif isinstance(p, ImagePart):
                parts.append(f"[AI Generated Image]")
            elif isinstance(p, ToolReturnPart):
                # Tool returns can also appear in ModelResponse in some cases
                tool_name = getattr(p, "tool_name", "unknown_tool")
                content = getattr(p, "content", None)
                if content is not None:
                    content_str = (
                        str(content) if not isinstance(content, str) else content
                    )
                    parts.append(f"AI Tool Result ({tool_name}): {content_str}")
            else:
                parts.append(f"[Unknown response part: {type(p).__name__}]")
        return "\n".join(parts) if parts else "[Empty ModelResponse]"

    # Fallback for unknown message types
    try:
        return str(msg)
    except:
        return f"[Unconvertible message of type: {type(msg).__name__}]"


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
                # Safely get parts with default
                msg_parts = getattr(msg, "parts", [])
                for p in msg_parts:
                    if isinstance(p, ToolReturnPart):
                        # Safely get content with default
                        content = getattr(p, "content", None)

                        # Skip if content is not a string (e.g., dict)
                        if not isinstance(content, str):
                            new_parts.append(p)
                            continue

                        # Skip if already summarized or truncated
                        if content.startswith(
                            "SUMMARY of tool result:"
                        ) or content.startswith("TRUNCATED tool result:"):
                            new_parts.append(p)
                            continue

                        content_tokens = llm_limiter.count_tokens(content)
                        if content_tokens > message_token_threshold:
                            zrb_print(
                                stylize_yellow(
                                    f"  Summarizing fat tool result ({content_tokens} tokens)..."
                                ),
                                plain=True,
                            )

                            # Calculate available tokens for summary (accounting for prefix)
                            prefix = "SUMMARY of tool result:\n"
                            prefix_tokens = llm_limiter.count_tokens(prefix)
                            available_tokens = message_token_threshold - prefix_tokens

                            # Ensure we have positive available tokens
                            if available_tokens <= 0:
                                zrb_print(
                                    stylize_error(
                                        f"  Warning: Token threshold ({message_token_threshold}) too low for summary prefix ({prefix_tokens} tokens)"
                                    ),
                                    plain=True,
                                )
                                # Keep original but truncated
                                truncated = llm_limiter.truncate_text(
                                    content, message_token_threshold
                                )
                                new_parts.append(
                                    replace(
                                        p,
                                        content=f"TRUNCATED tool result:\n{truncated}",
                                    )
                                )
                            else:
                                try:
                                    summary = await _summarize_text_plain(
                                        content,
                                        summarizer_agent,
                                        llm_limiter,
                                        available_tokens,
                                    )
                                    new_parts.append(
                                        replace(
                                            p,
                                            content=f"SUMMARY of tool result:\n{summary}",
                                        )
                                    )
                                except Exception as e:
                                    zrb_print(
                                        stylize_error(
                                            f"  Error summarizing tool result: {e}"
                                        ),
                                        plain=True,
                                    )
                                    new_parts.append(p)
                            msg_modified = True
                            continue
                    new_parts.append(p)
                if msg_modified:
                    new_messages.append(replace(msg, parts=new_parts))
                    continue
            new_messages.append(msg)
        return new_messages
    except Exception as e:
        zrb_print(stylize_error(f"  Error in summarize_messages: {e}"), plain=True)
        return messages


async def _summarize_text_plain(
    text: str, agent: Any, limiter: "LLMLimiter", threshold: int
) -> str:
    """Summarizes a long text into a plain summary, handling chunks if necessary."""
    # Ensure text is a string
    if not isinstance(text, str):
        try:
            return str(text)
        except:
            return "[Unconvertible content]"

    # Ensure threshold is positive
    if threshold <= 0:
        return "[Threshold too low for summarization]"

    text_tokens = limiter.count_tokens(text)
    if text_tokens <= threshold:
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
            consolidated = await agent.run(
                "Consolidate these partial summaries into a single, cohesive summary:\n\n"
                + "\n".join(summaries)
            )
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
            # If nothing to summarize (short history) but token count is high,
            # we need to find a safe split point that doesn't break tool call/return pairs.
            split_idx = _find_safe_split_index(
                messages, llm_limiter, conversational_token_threshold
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

            # If still nothing to summarize (shouldn't happen), return as-is
            if not to_summarize:
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
        is_near_threshold = final_summary_tokens > (
            conversational_token_threshold * 0.8
        )

        if is_near_threshold or has_multiple_snapshots:
            if has_multiple_snapshots:
                zrb_print(
                    stylize_yellow("  Consolidating multiple snapshots..."), plain=True
                )
            else:
                zrb_print(
                    stylize_yellow("  Aggressively re-compressing summary..."),
                    plain=True,
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
    except Exception as e:
        zrb_print(stylize_error(f"  Error in summarize_history: {e}"), plain=True)
        return messages


def _get_split_index(messages: list[Any], summary_window: int) -> int:
    """Find the last clean turn start before the summary window."""
    start_search_idx = max(0, len(messages) - summary_window)
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
    # Start from the end and work backwards
    # We want to keep as much recent context as possible
    for split_idx in range(len(messages) - 1, 0, -1):
        to_keep = messages[split_idx:]
        tokens_to_keep = limiter.count_tokens(to_keep)

        # Check if this split is safe (doesn't break tool pairs)
        is_safe = _is_split_safe(messages, split_idx)

        # Check if we're at a conversation turn boundary (better place to split)
        at_turn_boundary = split_idx < len(messages) and is_turn_start(
            messages[split_idx]
        )

        # Accept the split if:
        # 1. It's safe (doesn't break tool pairs)
        # 2. We're keeping a reasonable amount of tokens (not too many)
        # 3. Prefer turn boundaries when possible
        if is_safe and tokens_to_keep <= token_threshold * 0.7:  # Leave 30% room
            # If we're at a turn boundary, this is a good split
            if at_turn_boundary:
                return split_idx

            # Otherwise, continue looking for a better split (turn boundary)
            # But return this one if we don't find better

    # If we didn't find a split in the loop above, try from the beginning
    # (keeping fewer messages)
    for split_idx in range(1, len(messages)):
        to_keep = messages[split_idx:]
        tokens_to_keep = limiter.count_tokens(to_keep)

        is_safe = _is_split_safe(messages, split_idx)
        at_turn_boundary = split_idx < len(messages) and is_turn_start(
            messages[split_idx]
        )

        if is_safe and tokens_to_keep <= token_threshold * 0.7:
            # Accept any safe split at this point
            return split_idx

    # No safe split found
    return -1


def _is_split_safe(messages: list[Any], split_idx: int) -> bool:
    """
    Check if splitting at the given index would break tool call/return pairs.
    Returns True if the split is safe.

    A split is unsafe if a tool call and its return would be separated:
    - Tool call in [:split_idx] (summarized) and return in [split_idx:] (kept) OR
    - Tool call in [split_idx:] (kept) and return in [:split_idx] (summarized)

    Tool calls and returns must stay together - either both summarized or both kept.
    """
    from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart

    # Map tool_call_id -> (call_index, return_index)
    tool_pairs = {}

    # First pass: find all tool calls and their returns
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
                        # Tool return without a preceding call (shouldn't happen)
                        tool_pairs[tool_call_id] = {"call_idx": None, "return_idx": i}

    # Check each tool pair
    for tool_call_id, indices in tool_pairs.items():
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
            # Actually, this might be OK if the tool is still executing
            # But safer to consider it unsafe
            if call_idx < split_idx:
                return False

        # If we have only a return (no call) - shouldn't happen
        elif call_idx is None and return_idx is not None:
            # Orphaned return - always problematic
            return False

    return True


async def _chunk_and_summarize(
    messages: list[Any], agent: Any, limiter: "LLMLimiter", token_threshold: int
) -> str:
    """Break history into chunks and summarize them iteratively."""
    history_texts = []
    for m in messages:
        try:
            text = message_to_text(m)
            history_texts.append(text)
        except Exception as e:
            zrb_print(
                stylize_error(f"  Error converting message to text: {e}"), plain=True
            )
            history_texts.append(str(m))

    summaries = []
    current_chunk_texts = []
    current_chunk_tokens = 0

    # CHUNK LIMIT: For normal messages, group them up to 90% of threshold.
    chunk_token_limit = max(1, int(token_threshold * 0.9))

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
            try:
                chunk_summary = await _summarize_text(
                    "\n".join(current_chunk_texts), agent
                )
                summaries.append(chunk_summary)
            except Exception as e:
                zrb_print(stylize_error(f"  Error summarizing chunk: {e}"), plain=True)
                raise e
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
        try:
            final_summary = await _summarize_text("\n".join(current_chunk_texts), agent)
            summaries.append(final_summary)
        except Exception as e:
            zrb_print(
                stylize_error(f"  Error summarizing final chunk: {e}"), plain=True
            )
            raise e

    return "\n\n".join(summaries) if summaries else "[No summaries generated]"


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
