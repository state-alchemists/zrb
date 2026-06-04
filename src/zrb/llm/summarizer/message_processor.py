import json
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from zrb.context.any_context import zrb_print
from zrb.llm.agent.common import safe_copy_result
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.summarizer.text_summarizer import summarize_text_plain
from zrb.util.cli.style import stylize_error, stylize_yellow

if TYPE_CHECKING:
    from pydantic_ai.messages import ModelMessage
else:
    ModelMessage = Any

# Constants for message prefixes to avoid brittle string matching
SUMMARY_PREFIX = "SUMMARY OF TOOL RESULT:"
TRUNCATED_PREFIX = "TRUNCATED TOOL RESULT:"


async def process_message_for_summarization(
    msg: ModelMessage,
    agent: Any,
    limiter: LLMLimiter,
    message_threshold: int,
    insanity_threshold: int,
) -> ModelMessage:
    # lazy: heavy third-party
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
        new_part, modified = await process_tool_return_part(
            p, agent, limiter, message_threshold, insanity_threshold
        )
        new_parts.append(new_part)
        if modified:
            msg_modified = True
    if msg_modified:
        return replace(msg, parts=new_parts)
    return msg


async def process_tool_return_part(
    part: Any,
    agent: Any,
    limiter: LLMLimiter,
    message_threshold: int,
    insanity_threshold: int,
) -> tuple[Any, bool]:
    # lazy: heavy third-party
    from pydantic_ai import ToolApproved, ToolDenied

    # Safely get content with default
    original_content = getattr(part, "content", None)
    if original_content is None:
        return part, False

    # Cheap early-return before deepcopy. The summarizer is idempotent on
    # already-summarised / truncated content and on tool denial/approval
    # markers, so re-processing them is wasted work. Avoiding the deepcopy
    # here matters because _apply_history_processors runs once per model
    # round-trip (see runner._execution_loop) — the prefix is walked many
    # times during a single user turn.
    if isinstance(original_content, (ToolDenied, ToolApproved)):
        return part, False
    if isinstance(original_content, str) and (
        original_content.startswith(SUMMARY_PREFIX)
        or original_content.startswith(TRUNCATED_PREFIX)
    ):
        return part, False

    # Create a safe copy to prevent mutation during processing
    safe_content = safe_copy_result(original_content)

    # Convert non-string content to string for summarization
    content_is_string = isinstance(safe_content, str)
    if not content_is_string:
        try:
            content = json.dumps(safe_content, default=str)
        except Exception:
            content = str(safe_content)
    else:
        content = safe_content

    content_tokens = limiter.count_tokens(content)
    if content_tokens <= message_threshold:
        return part, False

    zrb_print(
        stylize_yellow(f"  Summarizing fat tool result ({content_tokens} tokens)..."),
        plain=True,
    )

    # Calculate available tokens for summary (accounting for prefix)
    prefix = f"{SUMMARY_PREFIX}\n"
    prefix_tokens = limiter.count_tokens(prefix)
    available_tokens = message_threshold - prefix_tokens

    # By capping at the conversational-level threshold, we ensure we don't spend
    # too much time summarizing a single message, while still performing
    # chunked summarization for messages that fit within history limits.
    if content_tokens > insanity_threshold:
        zrb_print(
            stylize_yellow(
                f"  Tool result is too large for efficient summarization ({content_tokens} tokens), truncating to {insanity_threshold} tokens first..."
            ),
            plain=True,
        )
        content = limiter.truncate_text(content, insanity_threshold)

    # Ensure we have positive available tokens
    if available_tokens <= 0:
        zrb_print(
            stylize_error(
                f"  Warning: Token threshold ({message_threshold}) too low for summary prefix ({prefix_tokens} tokens)"
            ),
            plain=True,
        )
        # Keep original but truncated
        truncated = limiter.truncate_text(content, message_threshold)
        new_part = replace(part, content=f"{TRUNCATED_PREFIX}\n{truncated}")
        return new_part, True
    try:
        summary = await summarize_text_plain(content, agent, limiter, available_tokens)
        new_part = replace(part, content=f"{SUMMARY_PREFIX}\n{summary}")
        return new_part, True
    except Exception as e:
        zrb_print(stylize_error(f"  Error summarizing tool result: {e}"), plain=True)
        # Return truncated content instead of original to prevent
        # unbounded content growth in history when summarization fails
        truncated = limiter.truncate_text(content, message_threshold)
        new_part = replace(part, content=f"{TRUNCATED_PREFIX}\n{truncated}")
        return new_part, True
