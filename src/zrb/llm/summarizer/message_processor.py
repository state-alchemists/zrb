import re
from dataclasses import replace
from typing import TYPE_CHECKING, Any, Sequence

from zrb.context.any_context import zrb_print
from zrb.llm.config.limiter import LLMLimiter
from zrb.util.cli.style import stylize_error, stylize_yellow

if TYPE_CHECKING:
    from pydantic_ai.messages import ModelMessage
else:
    ModelMessage = Any


async def process_message_for_summarization(
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
        new_part, modified = await process_tool_return_part(
            p, agent, limiter, threshold
        )
        new_parts.append(new_part)
        if modified:
            msg_modified = True
    if msg_modified:
        return replace(msg, parts=new_parts)
    return msg


async def process_tool_return_part(
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
        from zrb.llm.summarizer.text_summarizer import summarize_text_plain

        summary = await summarize_text_plain(content, agent, limiter, available_tokens)
        new_part = replace(part, content=f"SUMMARY of tool result:\n{summary}")
        return new_part, True
    except Exception as e:
        zrb_print(stylize_error(f"  Error summarizing tool result: {e}"), plain=True)
        return part, False
