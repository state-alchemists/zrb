import copy
import json
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from zrb.context.any_context import zrb_print
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.summarizer.text_summarizer import summarize_text_plain
from zrb.util.cli.style import stylize_error, stylize_yellow

if TYPE_CHECKING:
    from pydantic_ai.messages import ModelMessage
else:
    ModelMessage = Any


async def process_message_for_summarization(
    msg: ModelMessage,
    agent: Any,
    limiter: LLMLimiter,
    message_threshold: int,
    insanity_threshold: int,
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
        new_part, modified = await process_tool_return_part(
            p, agent, limiter, message_threshold, insanity_threshold
        )
        new_parts.append(new_part)
        if modified:
            msg_modified = True
    if msg_modified:
        return replace(msg, parts=new_parts)
    return msg


def _safe_copy_for_summarization(content: Any) -> Any:
    """Create a safe copy of content for summarization to prevent mutation.

    Deep copies mutable objects but returns immutable objects as-is.
    This prevents pydantic-ai from modifying original tool results.
    """
    if content is None:
        return None
    if isinstance(content, (str, int, float, bool)):
        return content
    if isinstance(content, (list, dict, set)):
        return copy.deepcopy(content)
    # For other types, try deep copy
    try:
        return copy.deepcopy(content)
    except Exception:
        # If deepcopy fails, return as-is
        return content


async def process_tool_return_part(
    part: Any,
    agent: Any,
    limiter: LLMLimiter,
    message_threshold: int,
    insanity_threshold: int,
) -> tuple[Any, bool]:
    # Safely get content with default
    original_content = getattr(part, "content", None)
    if original_content is None:
        return part, False

    # Create a safe copy to prevent mutation during processing
    safe_content = _safe_copy_for_summarization(original_content)

    # Convert non-string content to string for summarization
    content_is_string = isinstance(safe_content, str)
    if not content_is_string:
        try:
            content = json.dumps(safe_content, default=str)
        except Exception:
            content = str(safe_content)
    else:
        content = safe_content
    # Skip if already summarized or truncated
    is_summary = content.startswith("SUMMARY of tool result:")
    is_truncated = content.startswith("TRUNCATED tool result:")
    if is_summary or is_truncated:
        return part, False

    content_tokens = limiter.count_tokens(content)
    if content_tokens <= message_threshold:
        return part, False

    zrb_print(
        stylize_yellow(f"  Summarizing fat tool result ({content_tokens} tokens)..."),
        plain=True,
    )
    # DEBUG: Show sample of content
    if content_tokens > 10000:
        original_content = getattr(part, "content", None)
        zrb_print(
            stylize_yellow(f"  DEBUG: Original content type: {type(original_content)}"),
            plain=True,
        )
        if isinstance(original_content, list):
            zrb_print(
                stylize_yellow(
                    f"  DEBUG: Original content is list with {len(original_content)} items"
                ),
                plain=True,
            )
            for i, item in enumerate(original_content[:3]):  # Show first 3 items
                zrb_print(
                    stylize_yellow(
                        f"  DEBUG: Item {i} type: {type(item)}, length: {len(str(item))}"
                    ),
                    plain=True,
                )
            # DEBUG: Show list object ID to track mutations
            zrb_print(
                stylize_yellow(f"  DEBUG: List object id: {id(original_content)}"),
                plain=True,
            )
            # DEBUG: Show actual list reference and first few chars of each item
            for i, item in enumerate(original_content[:3]):
                item_str = str(item)
                preview = item_str[:100] + "..." if len(item_str) > 100 else item_str
                zrb_print(
                    stylize_yellow(f"  DEBUG: Item {i} preview: {preview}"),
                    plain=True,
                )
        sample = str(content)[:500] if len(str(content)) > 500 else str(content)
        zrb_print(
            stylize_yellow(f"  DEBUG: Content sample (first 500 chars): {sample}"),
            plain=True,
        )
    # Calculate available tokens for summary (accounting for prefix)
    prefix = "SUMMARY of tool result:\n"
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
        new_part = replace(part, content=f"TRUNCATED tool result:\n{truncated}")
        return new_part, True
    try:
        summary = await summarize_text_plain(content, agent, limiter, available_tokens)
        new_part = replace(part, content=f"SUMMARY of tool result:\n{summary}")
        return new_part, True
    except Exception as e:
        zrb_print(stylize_error(f"  Error summarizing tool result: {e}"), plain=True)
        return part, False
