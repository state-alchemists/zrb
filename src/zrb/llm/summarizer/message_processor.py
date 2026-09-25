import json
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from zrb.context.any_context import zrb_print
from zrb.llm.agent.common import safe_copy_result
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.summarizer.text_summarizer import summarize_text_plain
from zrb.util.cli.ansi import strip_ansi
from zrb.util.cli.style import stylize_error, stylize_warning

if TYPE_CHECKING:
    from zrb.llm.agent.types import ModelMessage
else:
    ModelMessage = Any

SUMMARY_PREFIX = "SUMMARY OF TOOL RESULT:"
TRUNCATED_PREFIX = "TRUNCATED TOOL RESULT:"


async def process_message_for_summarization(
    msg: ModelMessage,
    agent: Any,
    limiter: LLMLimiter,
    message_threshold: int,
    insanity_threshold: int,
) -> ModelMessage:
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import ModelRequest, ToolReturnPart

    if not isinstance(msg, ModelRequest):
        return msg
    new_parts = []
    msg_modified = False
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
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import ToolApproved, ToolDenied

    original_content = getattr(part, "content", None)
    if original_content is None:
        return part, False

    # Skip already-processed content before the deepcopy: every history
    # message is walked on each summarizer pass, so no-op copies add up.
    if isinstance(original_content, (ToolDenied, ToolApproved)):
        return part, False
    if isinstance(original_content, str) and (
        original_content.startswith(SUMMARY_PREFIX)
        or original_content.startswith(TRUNCATED_PREFIX)
    ):
        return part, False

    content = _content_as_text(safe_copy_result(original_content))

    # Strip ANSI escapes before measuring and summarizing: terminal-styled tool
    # output (color codes, OSC) inflates the token count and pollutes the summary.
    content = strip_ansi(content)

    content_tokens = limiter.count_tokens(content)
    if content_tokens <= message_threshold:
        return part, False

    zrb_print(
        stylize_warning(f"  Summarizing fat tool result ({content_tokens} tokens)..."),
        plain=True,
    )

    prefix = f"{SUMMARY_PREFIX}\n"
    prefix_tokens = limiter.count_tokens(prefix)
    available_tokens = message_threshold - prefix_tokens

    # Cap at the conversational threshold so one message cannot dominate the
    # summarizer's time.
    if content_tokens > insanity_threshold:
        zrb_print(
            stylize_warning(
                f"  Tool result is too large for efficient summarization ({content_tokens} tokens), truncating to {insanity_threshold} tokens first..."
            ),
            plain=True,
        )
        content = limiter.truncate_text(content, insanity_threshold)

    if available_tokens <= 0:
        zrb_print(
            stylize_error(
                f"  Warning: Token threshold ({message_threshold}) too low for summary prefix ({prefix_tokens} tokens)"
            ),
            plain=True,
        )
        return _truncated_part(part, content, limiter, message_threshold), True
    try:
        summary = await summarize_text_plain(content, agent, limiter, available_tokens)
        new_part = replace(part, content=f"{SUMMARY_PREFIX}\n{summary}")
        return new_part, True
    except Exception as e:
        zrb_print(stylize_error(f"  Error summarizing tool result: {e}"), plain=True)
        # Truncate rather than keep the original, so a failing summarizer
        # cannot let history grow unbounded.
        return _truncated_part(part, content, limiter, message_threshold), True


def _content_as_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    try:
        return json.dumps(content, default=str)
    except Exception:
        return str(content)


def _truncated_part(part: Any, content: str, limiter: LLMLimiter, limit: int) -> Any:
    truncated = limiter.truncate_text(content, limit)
    return replace(part, content=f"{TRUNCATED_PREFIX}\n{truncated}")
