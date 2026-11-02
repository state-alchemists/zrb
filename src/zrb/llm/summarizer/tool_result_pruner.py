"""Deterministic pruning of oversized tool results, with a pointer to the text.

A tool result is evidence, not a conclusion. Asking a model to paraphrase one
turns "the test run printed X" into "the tests pass", strips the timestamp that
made it true, and then the history summary paraphrases the paraphrase. This
module never asks a model anything: it keeps a token-budgeted head and tail of
the result, marks the removed middle, and writes the verbatim text to a private
file whose path the model can open.

The numbers are token budgets resolved by the caller (`message_token_threshold`
in the history processor), so the trigger is a configuration change rather than
a code change. Head and tail shares are fixed here: the head is where a command
echoes what it did, the tail is where the summary line and the exit code land,
and the middle of a long tool result is the least useful part of it.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.history_manager.archive_layout import (
    TOOL_RESULTS_DIR_SUFFIX,
    tool_results_dir,
    verbatim_archive_path,
)
from zrb.util.owner_only import write_text_owner_only
from zrb.util.string.name import safe_segment

if TYPE_CHECKING:
    from zrb.llm.config.limiter import LLMLimiter

PRUNED_PREFIX = "PRUNED TOOL RESULT:"
"""First line of every pruned result; also how a replay recognises one."""

SPILL_DIR_SUFFIX = TOOL_RESULTS_DIR_SUFFIX
"""Suffix of the directory holding one conversation's pruned tool results."""

HEAD_SHARE = 0.75
TAIL_SHARE = 0.125
"""Shares of the prune threshold kept at each end, head first.

The remaining eighth pays for the marker plus the tokenizer's per-line overhead.
A tail is small on purpose: its job is to keep the last line — an exit code, a
summary count, a final error — not to re-quote the body.
"""


def is_pruned_tool_result(content: str) -> bool:
    """Whether *content* was already pruned, so a second pass must not redo it."""
    return content.startswith(PRUNED_PREFIX)


def tool_result_spill_dir(
    session_name: str | None, history_dir: str | None = None
) -> str:
    """Where one conversation's verbatim tool results live.

    Beside the conversation's verbatim archive, named after it, so collecting
    the archive collects its tool results too. A conversation with no name yet
    still gets one shared directory; the tool-call id keeps the names apart.
    """
    base = os.path.expanduser(history_dir or CFG.LLM_HISTORY_DIR)
    key = safe_segment(session_name) if session_name else "_unassigned"
    return tool_results_dir(verbatim_archive_path(key, history_dir=base))


def spill_tool_result(
    content: str,
    *,
    call_id: str,
    session_name: str | None = None,
    history_dir: str | None = None,
) -> str | None:
    """Write *content* verbatim to a private file; return its path, or `None`.

    Never raises: a result that cannot be saved is still pruned, and the marker
    then says the full text is unavailable rather than pointing at a missing
    file.
    """
    if not call_id:
        return None
    path = os.path.join(
        tool_result_spill_dir(session_name, history_dir),
        f"{safe_segment(call_id)}.txt",
    )
    try:
        write_text_owner_only(path, content)
    except OSError:
        return None
    return path


def prune_tool_result_content(
    content: str,
    limiter: "LLMLimiter",
    threshold_tokens: int,
    *,
    spill_path: str | None = None,
) -> str:
    """Head-and-tail *content* under *threshold_tokens*, with a pointer.

    The model is handed three things it can act on: the start of the output,
    the end of it, and the path to the rest. It is never handed a paraphrase
    that can drift from what the tool actually printed.
    """
    total_tokens = limiter.count_tokens(content)
    head_budget = max(1, int(threshold_tokens * HEAD_SHARE))
    tail_budget = max(0, int(threshold_tokens * TAIL_SHARE))
    head, head_tokens = _keep_head(content, limiter, head_budget)
    tail, tail_tokens = _keep_tail(content[len(head) :], limiter, tail_budget)
    kept_tokens = head_tokens + tail_tokens
    removed_tokens = max(0, total_tokens - kept_tokens)
    header = _render_header(total_tokens, kept_tokens, removed_tokens, spill_path)
    if not head and not tail:
        return header
    if not tail:
        return f"{header}\n\n{head}"
    return (
        f"{header}\n\n{head}\n\n"
        f"[... {removed_tokens:,} tokens pruned ...]\n\n{tail}"
    )


def _render_header(
    total_tokens: int,
    kept_tokens: int,
    removed_tokens: int,
    spill_path: str | None,
) -> str:
    """The deterministic first line: sizes, then where the full text went."""
    pointer = (
        f"Full output: `{spill_path}`"
        if spill_path
        else "The full output could not be saved."
    )
    return (
        f"{PRUNED_PREFIX} {kept_tokens:,} of {total_tokens:,} tokens kept "
        f"({removed_tokens:,} pruned). {pointer}"
    )


def _keep_head(text: str, limiter: "LLMLimiter", budget: int) -> "tuple[str, int]":
    """Whole leading lines whose measured cost fits *budget*.

    A single line longer than the budget (minified JSON, one long diff hunk) is
    cut by the limiter's own tokenizer instead of dropped: a head with nothing
    in it is worse than a head that stops mid-line.
    """
    lines = text.splitlines()
    if not lines:
        return "", 0
    kept: list[str] = []
    used = 0
    for line in lines:
        cost = limiter.count_tokens(line) + 1
        if used + cost > budget:
            if not kept:
                cut = limiter.truncate_text(line, max(1, budget))
                return cut, limiter.count_tokens(cut)
            break
        kept.append(line)
        used += cost
    return "\n".join(kept), used


def _keep_tail(text: str, limiter: "LLMLimiter", budget: int) -> "tuple[str, int]":
    """Whole trailing lines whose measured cost fits *budget*.

    Walks from the end so the last line — the one carrying an exit code or a
    final count — survives. A last line longer than the whole budget falls back
    to a token-measured suffix.
    """
    if budget <= 0 or not text:
        return "", 0
    lines = text.splitlines()
    kept: list[str] = []
    used = 0
    for line in reversed(lines):
        cost = limiter.count_tokens(line) + 1
        if used + cost > budget:
            if not kept:
                return _tail_by_search(text, limiter, budget)
            break
        kept.append(line)
        used += cost
    kept.reverse()
    return "\n".join(kept), used


def _tail_by_search(text: str, limiter: "LLMLimiter", budget: int) -> "tuple[str, int]":
    """The longest measured suffix of a single over-budget line.

    A character binary search rather than a token one: the limiter only cuts
    from the front, and the question here is where the suffix starts. Token
    counts of suffixes shrink as the start moves right, which is the monotonic
    property the search needs to a tolerance of a few tokens.
    """
    low, high = 0, len(text)
    best = ""
    while low < high:
        middle = (low + high) // 2
        candidate = text[middle:]
        if limiter.count_tokens(candidate) <= budget:
            best = candidate
            high = middle
        else:
            low = middle + 1
    return best, limiter.count_tokens(best)
