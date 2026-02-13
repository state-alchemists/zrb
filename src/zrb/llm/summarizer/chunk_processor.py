from typing import Any

from zrb.context.any_context import zrb_print
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.summarizer.message_converter import message_to_text
from zrb.llm.summarizer.text_summarizer import summarize_text
from zrb.util.cli.style import stylize_error, stylize_yellow


async def chunk_and_summarize(
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
            summary = await summarize_text("\n".join(current_chunk), agent)
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


async def consolidate_summaries(
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

    return await summarize_text(
        "Consolidate the following conversation state snapshots into a single, cohesive "
        "<state_snapshot>.\n"
        "IMPORTANT: Be extremely concise and dense. Your goal is to fit all critical "
        f"knowledge into less than {conversational_token_threshold // 2} tokens.\n"
        f"{summary_text}",
        agent,
    )
