import asyncio
from typing import Any

from zrb.config.config import CFG
from zrb.context.any_context import zrb_print
from zrb.llm.agent.run.error_classifier import (
    get_retry_wait,
    is_retryable_error,
)
from zrb.llm.config.limiter import LLMLimiter
from zrb.util.cli.style import stylize_error


async def _run_agent_with_retry(agent: Any, text: str) -> Any:
    """Run ``agent.run(text)`` with retry for transient API errors (5xx, 429)."""
    max_retries = CFG.LLM_API_MAX_RETRIES
    max_wait = CFG.LLM_API_MAX_WAIT
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return await agent.run(text)
        except Exception as e:
            last_error = e
            if attempt < max_retries and is_retryable_error(e):
                wait = get_retry_wait(e, attempt + 1, max_wait)
                zrb_print(
                    stylize_error(
                        f"  Retrying summarization after {wait:.0f}s"
                        f" (attempt {attempt + 1}/{max_retries})..."
                    ),
                    plain=True,
                )
                await asyncio.sleep(wait)
            else:
                raise
    # Only reachable if the loop never ran (max_retries < 0); last_error is then
    # None, so raise a concrete error rather than `raise None`.
    raise last_error or RuntimeError("Summarization failed without an error")


async def summarize_text_plain(
    text: str, agent: Any, limiter: "LLMLimiter", threshold: int
) -> str:
    """Summarizes a long text into a plain summary, handling chunks if necessary."""
    if not isinstance(text, str):
        try:
            return str(text)
        except Exception:
            return "[Unconvertible content]"
    if threshold <= 0:
        return "[Threshold too low for summarization]"
    text_tokens = limiter.count_tokens(text)
    if text_tokens <= threshold:
        return await summarize_short_text(text, agent, limiter, threshold)
    return await summarize_long_text(text, agent, limiter, threshold)


async def summarize_short_text(
    text: str, agent: Any, limiter: LLMLimiter, threshold: int
) -> str:
    try:
        result = await _run_agent_with_retry(agent, text)
        summary = _as_text(getattr(result, "output", ""))
        if limiter.count_tokens(summary) > threshold:
            summary = limiter.truncate_text(summary, threshold)
        return summary
    except Exception as e:
        zrb_print(stylize_error(f"  Error during summarization: {e}"), plain=True)
        raise


async def summarize_long_text(
    text: str, agent: Any, limiter: LLMLimiter, threshold: int, depth: int = 0
) -> str:
    if depth > 5:
        return limiter.truncate_text(text, threshold)
    # Use 70% of threshold for chunks to leave room for consolidation
    chunk_limit = max(1, int(threshold * 0.7))
    summaries = await _summarize_chunks(text, agent, limiter, chunk_limit)
    if not summaries:
        return "[No summary generated]"
    if len(summaries) == 1:
        final_summary = summaries[0]
    else:
        final_summary = await _consolidate(
            summaries, text, agent, limiter, threshold, depth
        )
    if limiter.count_tokens(final_summary) > threshold:
        return limiter.truncate_text(final_summary, threshold)
    return final_summary


async def _summarize_chunks(
    text: str, agent: Any, limiter: LLMLimiter, chunk_limit: int
) -> list[str]:
    """Summarize `text` one `chunk_limit`-sized piece at a time."""
    remaining_text = text
    summaries: list[str] = []
    while remaining_text:
        chunk = limiter.truncate_text(remaining_text, chunk_limit)
        try:
            result = await _run_agent_with_retry(
                agent, f"Summarize this part of a document:\n\n{chunk}"
            )
        except Exception as e:
            zrb_print(
                stylize_error(f"  Error during chunk summarization: {e}"), plain=True
            )
            raise
        summaries.append(
            limiter.truncate_text(_as_text(getattr(result, "output", "")), chunk_limit)
        )
        remaining_text = remaining_text[len(chunk) :]
        if not remaining_text.strip():
            break
    return summaries


async def _consolidate(
    summaries: list[str],
    text: str,
    agent: Any,
    limiter: LLMLimiter,
    threshold: int,
    depth: int,
) -> str:
    """Fold the per-chunk summaries into one.

    Recurses when the concatenated summaries would still overflow the
    consolidation agent's own context — but only while they are shorter than
    the original text, so the recursion always makes progress.
    """
    summaries_text = "\n".join(summaries)
    summaries_tokens = limiter.count_tokens(summaries_text)
    if summaries_tokens > threshold * 0.9 and summaries_tokens < limiter.count_tokens(
        text
    ):
        return await summarize_long_text(
            summaries_text, agent, limiter, threshold, depth + 1
        )
    try:
        consolidated = await _run_agent_with_retry(
            agent,
            "Consolidate these partial summaries into a single, cohesive "
            f"summary:\n\n{summaries_text}",
        )
    except Exception as e:
        zrb_print(stylize_error(f"  Error during consolidation: {e}"), plain=True)
        raise
    return _as_text(getattr(consolidated, "output", ""))


def _as_text(output: Any) -> str:
    """An agent's `output` as a string, with `None` flattened to empty."""
    if isinstance(output, str):
        return output
    return str(output) if output is not None else ""
