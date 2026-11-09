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

import hashlib
import os
import re
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

PRUNED_PREFIX = "PRUNED TOOL RESULT (zrb):"
"""First line of every pruned result, tagged so a tool's own output cannot
impersonate one by starting with the same words."""

# The whole generated header, not just its opening words: a tool result that
# happens to begin with the marker text is still a tool result, and must be
# pruned like any other. Only the exact shape this module writes counts.
_PRUNED_HEADER = re.compile(
    r"^PRUNED TOOL RESULT \(zrb\): [\d,]+ of [\d,]+ tokens kept " r"\([\d,]+ pruned\)\."
)

SPILL_DIR_SUFFIX = TOOL_RESULTS_DIR_SUFFIX
"""Suffix of the directory holding one conversation's pruned tool results."""

HEAD_SHARE = 0.75
TAIL_SHARE = 0.125
"""Shares of the prune threshold kept at each end, head first.

The remaining eighth pays for the marker plus the tokenizer's per-line overhead.
A tail is small on purpose: its job is to keep the last line — an exit code, a
summary count, a final error — not to re-quote the body.
"""


_SPILLED_PATH = re.compile(r"Full output: `([^`]+)`")


def spilled_path_of(content: str) -> str | None:
    """The verbatim path a pruned block names, or `None`.

    Used to measure the same budget the block was built under: a genuine block
    can be larger than the configured threshold when a long path raised the
    floor, and reprocessing it would rewrite it on every pass.
    """
    match = _SPILLED_PATH.search(content)
    return match.group(1) if match is not None else None


def is_pruned_tool_result(content: str) -> bool:
    """Whether *content* looks like a block this module wrote.

    Matched on the full header shape, sizes included, rather than its opening
    words — but text is not authoritative, so a caller must not skip on this
    alone. `process_tool_return_part` also checks that the block is inside the
    pending budget; a tool that echoes a valid header before a large payload
    is then pruned like any other oversized result.
    """
    return _PRUNED_HEADER.match(content) is not None


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


def spill_filename(call_id: str) -> str:
    """The file one tool call's verbatim output is saved under.

    The readable part is only for a human listing it; the digest is what keeps
    two distinct ids that sanitize to the same segment apart, and what lets a
    replay prove the file belongs to the call it is named in.
    """
    digest = hashlib.sha1(call_id.encode("utf-8")).hexdigest()[:8]
    return f"{safe_segment(call_id)}-{digest}.txt"


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
        spill_filename(call_id),
    )
    try:
        write_text_owner_only(path, content)
        # Overwriting an existing call id rewrites the file without moving the
        # directory's timestamp; retention reads both, but a fresh directory
        # mtime keeps the intent explicit on filesystems that lag.
        os.utime(os.path.dirname(path), None)
    except OSError:
        return None
    return path


MIN_PRUNE_TOKENS = 64
"""Smallest budget a prune honours, before the pointer's own size is counted.

A configured threshold under this is raised to it. The effective budget can be
higher still: the marker and the path are measured, and the block is never
truncated below their size, because a path cut in half cannot be opened.
"""


def prune_tool_result_content(
    content: str,
    limiter: "LLMLimiter",
    threshold_tokens: int,
    *,
    spill_path: str | None = None,
) -> str:
    """Head-and-tail *content* under the budget, with a pointer.

    The model is handed three things it can act on: the start of the output,
    the end of it, and the path to the rest. It is never handed a paraphrase
    that can drift from what the tool actually printed.

    The budget is spent in this order: the marker and its pointer first, then
    the head and the tail from what is left. The effective budget is the
    larger of the configured threshold, `MIN_PRUNE_TOKENS`, and the measured
    size of the marker plus two tokens — the pointer is never truncated,
    because the file it names cannot be found from a path that was cut in
    half. The result never exceeds that effective budget.
    """
    total_tokens = limiter.count_tokens(content)
    budget = effective_prune_budget(limiter, total_tokens, threshold_tokens, spill_path)
    body_budget = budget - _framing_tokens(limiter, total_tokens, spill_path)
    for _ in range(4):
        if body_budget < 2:
            break
        head_budget = max(1, int(body_budget * HEAD_SHARE))
        tail_budget = max(0, int(body_budget * TAIL_SHARE))
        head, head_tokens = _keep_head(content, limiter, head_budget)
        tail, tail_tokens = _keep_tail(content[len(head) :], limiter, tail_budget)
        text = _compose(total_tokens, head_tokens, tail_tokens, head, tail, spill_path)
        overflow = limiter.count_tokens(text) - budget
        if overflow <= 0:
            return text
        # Re-measure rather than trust the estimate: a smaller head changes how
        # the tail tokenizes, so each retry starts from what the block still
        # overflows by.
        body_budget -= max(1, overflow)
    # Unreachable through the loop above, but the pointer must survive even
    # here: emit the header whole rather than cut the path out of it.
    return _render_header(total_tokens, 0, total_tokens, spill_path)


def effective_prune_budget(
    limiter: "LLMLimiter",
    total_tokens: int,
    threshold_tokens: int,
    spill_path: str | None,
) -> int:
    """The budget a prune is actually held to, never below its own pointer.

    The configured threshold can be smaller than the marker plus a path — a
    long history directory is enough. Cutting the path to fit would leave the
    saved file unopenable, so the effective budget grows to fit it. This is the
    only place the floor is computed, so a caller (and a test) can ask what a
    block will be held to before it is built.
    """
    framing = _framing_tokens(limiter, total_tokens, spill_path)
    return max(threshold_tokens, MIN_PRUNE_TOKENS, framing + 2)


def _framing_tokens(
    limiter: "LLMLimiter", total_tokens: int, spill_path: str | None
) -> int:
    """What the marker, separators and pointer cost before any body is kept.

    Measured with a placeholder head and tail so the middle marker is counted
    too, and with the largest numbers the header can print, so the reserve
    cannot come up short.
    """
    return limiter.count_tokens(_compose(total_tokens, 0, 0, "x", "x", spill_path))


def _compose(
    total_tokens: int,
    head_tokens: int,
    tail_tokens: int,
    head: str,
    tail: str,
    spill_path: str | None,
) -> str:
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


def clip_text_both_ends(text: str, limiter: "LLMLimiter", budget: int) -> str:
    """*text* under *budget* tokens, keeping its start and its end.

    A message's conclusion is at its end as often as its subject is at its
    start: the failing assertion is in the last lines of the run that printed
    it. So a fit that has to lose the middle loses it from the middle, and says
    how much it removed — the same shape as `prune_tool_result_content`, without
    the spill pointer, because the caller is fitting one message into a chunk
    rather than pruning a tool result, and the archive already holds it whole.
    """
    total = limiter.count_tokens(text)
    if budget < 2 or total <= budget:
        return text
    marker = f"\n[... {total:,} tokens in all; the middle is not shown ...]\n"
    body_budget = budget - limiter.count_tokens(marker)
    if body_budget < 2:
        return marker.strip()
    head_budget = max(1, body_budget // 2)
    head, head_tokens = _keep_head(text, limiter, head_budget)
    # What the head did not spend goes to the tail, so a head of whole lines
    # under its budget does not leave the other end short.
    tail_budget = max(0, body_budget - head_tokens)
    tail, _ = _keep_tail(text[len(head) :], limiter, tail_budget)
    return f"{head}{marker}{tail}"
