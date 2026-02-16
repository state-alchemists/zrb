from typing import Any

from zrb.context.any_context import zrb_print
from zrb.llm.config.limiter import LLMLimiter
from zrb.util.cli.style import stylize_error, stylize_yellow


async def summarize_text_plain(
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
        return await summarize_short_text(text, agent, limiter, threshold)
    return await summarize_long_text(text, agent, limiter, threshold)


async def summarize_short_text(
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


async def summarize_long_text(
    text: str, agent: Any, limiter: LLMLimiter, threshold: int, depth: int = 0
) -> str:
    # Chunking logic for extremely large text
    if depth > 5:
        return limiter.truncate_text(text, threshold)

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
            # If the concatenated summaries still exceed the threshold,
            # we need to recursively summarize them to avoid crashing the consolidation agent.
            summaries_tokens = limiter.count_tokens(summaries_text)
            text_tokens = limiter.count_tokens(text)
            if summaries_tokens > threshold * 0.9 and summaries_tokens < text_tokens:
                final_summary = await summarize_long_text(
                    summaries_text, agent, limiter, threshold, depth + 1
                )
            else:
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


async def summarize_text(text: str, agent: Any, partial: bool = False) -> str:
    """Helper to run the summarizer agent on a block of text."""
    import re

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
