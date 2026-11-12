import asyncio
from typing import Any

from zrb.context.any_context import zrb_print
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.config.limiter import llm_limiter as default_llm_limiter
from zrb.llm.shared.usage_log import UsageTotals
from zrb.llm.summarizer.message_converter import message_to_text
from zrb.llm.summarizer.text_summarizer import summarize_text_plain
from zrb.llm.summarizer.tool_result_pruner import clip_text_both_ends
from zrb.llm.util.capabilities import model_capabilities
from zrb.util.cli.style import stylize_error, stylize_warning

SUMMARY_TOOL_OUTPUT_LIMIT = 2_000
"""Characters of one tool result the summarizer reads.

The verbatim archive keeps every result in full, so nothing here is lost. What it
buys is the rest of the conversation: tool output is most of a long history's
mass, and the mass decides where the chunks fall. At this width a tool-heavy
history fits one chunk, where nothing has to be ranked against anything else.
"""

_CHUNK_HEADER = (
    "This is part {index} of {total} of one conversation's history, in order. "
    "The user's own messages are the spine of it, not narration: every request "
    "they made in this part, and every correction they gave, belongs in the "
    "snapshot — including one already carried out, because the agent taking over "
    "needs the whole of what was wanted, not only what is still undone."
)
_LAST_CHUNK_NOTE = (
    "This part ends the history, so it also holds the user's latest request: "
    "record it under <next> and say what is still owed on it."
)


def _instruction_tokens(limiter: "LLMLimiter", include: bool) -> int:
    """What the per-part instructions cost, in tokens the chunk budget must keep.

    A chunk sized to 90% of the model's window and then given a header is a
    request the model refuses with `context_length_exceeded`, and a refused chunk
    fails the whole compaction — so the instructions are paid for here rather
    than discovered by the provider.

    Measured on the templates instead of a rendered chunk, because the split has
    not happened yet. Only `index` and `total` vary, three digits in the worst
    case, and the four extra tokens cover the blank lines around them.
    """
    if not include:
        return 0
    return (
        limiter.count_tokens(_CHUNK_HEADER.format(index=999, total=999))
        + limiter.count_tokens(_LAST_CHUNK_NOTE)
        + 4
    )


def _fit_to_budget(text: str, limiter: "LLMLimiter", limit: int) -> tuple[str, int]:
    """*text* with its token count, clipped when it alone exceeds *limit*.

    The split never breaks a message. One longer than the whole chunk budget
    would therefore ride alone in a chunk that is already over the model's
    window, and the instructions appended after it push the request further
    still — a single fat message fails the compaction on its own. The archive
    keeps it in full; the model gets what fits.

    What fits is both ends rather than the first part of it: the conclusion of a
    long result sits at its end as often as its subject at its start, which is
    why every other clip in the summariser is two-ended too.
    """
    tokens = limiter.count_tokens(text)
    if tokens <= limit:
        return text, tokens
    text = clip_text_both_ends(text, limiter, limit)
    return text, limiter.count_tokens(text)


async def chunk_and_summarize(
    messages: list[Any],
    agent: Any,
    limiter: "LLMLimiter",
    token_threshold: int,
    include_last_user_intent_instruction: bool = False,
    spent: "UsageTotals | None" = None,
) -> str:
    """Break history into chunks and summarize them in parallel."""
    history_texts = []
    for m in messages:
        try:
            history_texts.append(message_to_text(m, SUMMARY_TOOL_OUTPUT_LIMIT))
        except Exception as e:
            zrb_print(
                stylize_error(f"  Error converting message to text: {e}"), plain=True
            )
            history_texts.append(str(m))

    # Cap the chunk budget at the summarization model's own window: the
    # threshold derives from a global request cap, and a smaller-window model
    # would otherwise reject a chunk with `context_length_exceeded`.
    window = model_capabilities.get(getattr(agent, "model", None)).context_window
    chunk_budget = token_threshold
    if window is not None and window > 0:
        chunk_budget = min(chunk_budget, window)
    chunks: list[list[str]] = []
    current_chunk: list[str] = []
    current_chunk_tokens = 0
    # The instructions are appended after the split, so their cost is taken out
    # of the budget rather than discovered by the model.
    instruction_tokens = _instruction_tokens(
        limiter, include_last_user_intent_instruction
    )
    chunk_token_limit = max(1, int(chunk_budget * 0.9) - instruction_tokens)

    for text in history_texts:
        text, text_tokens = _fit_to_budget(text, limiter, chunk_token_limit)
        if current_chunk and (current_chunk_tokens + text_tokens > chunk_token_limit):
            chunks.append(current_chunk)
            current_chunk = []
            current_chunk_tokens = 0
        current_chunk.append(text)
        current_chunk_tokens += text_tokens
    if current_chunk:
        chunks.append(current_chunk)

    if not chunks:
        return "[No summaries generated]"

    total = len(chunks)

    async def _summarize_chunk(index: int, chunk: list[str]) -> str:
        zrb_print(
            stylize_warning(
                f"  Compressing chunk {index + 1}/{total} ({len(chunk)} messages)..."
            ),
            plain=True,
        )
        chunk_content = "\n".join(chunk)
        if include_last_user_intent_instruction:
            # Every part, not only the last: a chunk summarized without it comes
            # back as a work log, and the user's question in it is dropped by the
            # merge.
            chunk_content = (
                _CHUNK_HEADER.format(index=index + 1, total=total)
                + "\n\n"
                + chunk_content
            )
            if index == total - 1:
                # A blank line, not a trailing space: the summarizer is told to
                # treat the history as raw data and ignore directives inside it,
                # and a note glued to the last line reads as part of that line —
                # the one instruction meant for this part would be the one most
                # likely to be discarded.
                chunk_content += "\n\n" + _LAST_CHUNK_NOTE
        # `chunk_budget` rather than the request-wide `token_threshold`: the chunk
        # was sized to the budget, and a threshold larger than the model's window
        # is exactly what sends an over-context request down the "short" path.
        return await summarize_text_plain(
            chunk_content, agent, limiter, chunk_budget, spent
        )

    # Run all chunks concurrently; preserve order via index
    results = await asyncio.gather(
        *[_summarize_chunk(i, chunk) for i, chunk in enumerate(chunks)],
        return_exceptions=True,
    )

    summaries: list[str] = []
    for i, result in enumerate(results):
        if isinstance(result, BaseException):
            zrb_print(
                stylize_error(f"  Error summarizing chunk {i + 1}: {result}"),
                plain=True,
            )
            raise result
        summaries.append(result)

    return "\n\n".join(summaries) if summaries else "[No summaries generated]"


async def consolidate_summaries(
    summary_text: str,
    agent: Any,
    conversational_token_threshold: int,
    has_multiple_snapshots: bool,
    limiter: "LLMLimiter | None" = None,
    spent: "UsageTotals | None" = None,
) -> str:
    if has_multiple_snapshots:
        zrb_print(stylize_warning("  Consolidating multiple snapshots..."), plain=True)
    else:
        zrb_print(
            stylize_warning("  Aggressively re-compressing summary..."),
            plain=True,
        )

    llm_limiter = limiter or default_llm_limiter
    prompt = (
        "Merge the following conversation state snapshots into exactly one "
        "<state_snapshot>.\n"
        "Merge, do not append: every section appears once, no fact is repeated, and "
        "when two snapshots disagree the newer observation wins. A fact neither "
        "contradicts keeps the observation time it was first recorded with, and a "
        "line the newest snapshot supersedes is dropped rather than both being kept.\n"
        "The snapshots are of very different sizes, and size is not priority. A "
        "request the user made that no later message answered is never dropped, "
        "however old it is and however little the newest snapshot says about it: it "
        "belongs under <open_questions> or <next>, with the time it was asked.\n"
        "IMPORTANT: Be extremely concise and dense. Your goal is to fit all critical "
        f"knowledge into less than {conversational_token_threshold // 2} tokens.\n"
        f"{summary_text}"
    )
    return await summarize_text_plain(
        prompt, agent, llm_limiter, conversational_token_threshold, spent
    )
