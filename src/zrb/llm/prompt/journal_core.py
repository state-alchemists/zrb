"""What the first turn is given when the journal index does not fit.

One journal file is injected unprompted, and it is capped. The index is ordered
most-durable-first, so the old head-first cut spent the whole cap inside
`## User` and lost every `📌` constraint, all of `## Agent`, and the pointer to
the category indexes below them. Measured on a real journal on 2026-11-01: a
2,500-char cap on a 15,167-char index kept one section out of seven and named
none of the six it lost.

This module decides what the cap keeps instead, in four ranks:

1. a pinned line, wherever it sits — the note said it holds every turn;
2. a claim, the readable half of a note: `- text ([note](category/slug.md))`;
3. a line linking into a category index, which is how the rest is reachable;
4. anything else — a catalog title, a footer, a hand-written line.

Within one rank the sections take turns, so a section holding twice the lines
does not take twice the budget and leave a shorter one empty: identity, standing
preferences and constraints live in different sections and all three have to
arrive. A catalog title whose note already shows as a claim is dropped outright
— the block would otherwise state one fact twice, the second time in the weaker
form, for a quarter of the budget.

Pure: strings in, strings out. No `CFG`, no I/O, so the caller owns both.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# A claim ends with a link to the note it came from. That link is how an entry is
# told apart from a catalog title, and how a note's claim is matched against the
# title that would otherwise repeat it.
_CLAIM_LINK = re.compile(r"\(\[note\]\(([^)]*)\)\)[ \t]*$")
_ANY_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")

# Ranks, best first. A claim outranks a pointer: the block's own header already
# says that each category's own index lists every note ever written in it, so the
# `## Directories` line is the cheaper thing to lose. `ORPHAN` is a catalog title
# whose note also has a claim: it is a duplicate *if that claim was kept*, so it
# goes last and the fill drops it once the claim is in — a claim too long to fit
# leaves the short title as the note's only trace.
PINNED, CLAIM, POINTER, REST, ORPHAN = range(5)
_KEPT_RANKS = (PINNED, CLAIM, POINTER, REST, ORPHAN)

# How many hidden sections the overflow note names before it counts the rest,
# and how many characters of the cap the note may spend at most.
_NAMED_SECTIONS = 3
_MAX_NOTE = 200
_MARKER = "(...more)"
_MARKER_CHARS = len("\n" + _MARKER)


@dataclass(frozen=True)
class _Line:
    """One line of the index: its text, what it is worth, and the note it names
    (``""`` when it names none)."""

    text: str
    rank: int
    path: str


@dataclass(frozen=True)
class _Block:
    """One `## heading` of the index and its lines, in the file's own order."""

    heading: str
    lines: tuple[_Line, ...]


def plan_index_core(content: str, budget: int) -> tuple[str, str]:
    """Split *content* into the text the cap keeps and a note about the rest.

    *budget* bounds the kept text in characters — the overflow note is charged
    to it as well, because a cap that exempts what stands in for the dropped
    text is not a cap: the old one took a 2,500-char slice and then appended the
    summary on top, for a 4,049-char block. `<= 0` keeps everything, for a
    caller that has already decided what a zero or negative cap means.

    The returned note is `""` when nothing readable was hidden.
    """
    if budget <= 0 or len(content) <= budget:
        return content, ""
    # Deferred: a module-level import of `zrb.llm.tool` here would close a
    # package cycle — two tool modules read `zrb.llm.prompt.prompt`.
    from zrb.llm.tool.journal_index import DIRECTORIES_HEADING, PIN_MARKER

    pointer = DIRECTORIES_HEADING.removeprefix("## ").strip()
    blocks = _split_sections(content, pointer, PIN_MARKER)
    # A quarter of the cap, at most, explains what the rest of it left out. Fixed
    # before the fill rather than measured after it, because the note grows as
    # the body shrinks — the two would chase each other, and the line that paid
    # for the note was a claim.
    reserve = min(_MAX_NOTE, budget // 4)
    kept = _fill(blocks, budget - reserve - _MARKER_CHARS)
    return _emit(blocks, kept), _hidden_note(blocks, kept, reserve)


def _split_sections(
    content: str, pointer_heading: str, pin_marker: str
) -> list[_Block]:
    """Every block of the index, in file order.

    The lines above the first `## ` heading — the title, and any hand-written
    lines a journal keeps there — are a block of their own with no heading, so
    they are ranked and trimmed like any other. Charging them to the budget
    without being able to drop one returned more than the cap whenever the
    preamble was larger than it.

    Blank lines are not candidates: they carry nothing, and letting one compete
    for the budget opened a section whose heading then stood over no lines at
    all."""
    lines = content.splitlines()
    start = len(lines)
    for index, line in enumerate(lines):
        if line.startswith("## "):
            start = index
            break
    head = _without_blank_edges(lines[:start])
    raw = [("", head), *_raw_blocks(lines[start:])] if head else _raw_blocks(lines[start:])
    claimed = {path for _, body in raw for path in map(_note_path, body) if path}
    return [
        _Block(
            heading,
            tuple(
                _rank_line(line, heading == pointer_heading, pin_marker, claimed)
                for line in body
            ),
        )
        for heading, body in raw
    ]


def _raw_blocks(tail: list[str]) -> list[tuple[str, list[str]]]:
    """Split lines at `## ` headings, keeping each heading with its own lines.

    Blank lines are dropped: a section's layout is rebuilt when it is emitted, so
    a blank one is not a candidate for the budget."""
    blocks: list[tuple[str, list[str]]] = []
    for line in tail:
        if line.startswith("## "):
            blocks.append((line[3:].strip(), []))
        elif blocks and line.strip():
            blocks[-1][1].append(line)
    return blocks


def _without_blank_edges(lines: list[str]) -> list[str]:
    """*lines* without the blank lines that separate it from the next section."""
    end = len(lines)
    while end and not lines[end - 1].strip():
        end -= 1
    start = 0
    while start < end and not lines[start].strip():
        start += 1
    return lines[start:end]


def _note_path(line: str) -> str:
    """The note a claim line came from, or `""` for any other line."""
    found = _CLAIM_LINK.search(line)
    return found.group(1) if found else ""


def _rank_line(
    line: str, in_pointer_section: bool, pin_marker: str, claimed: set[str]
) -> _Line:
    """What this line is worth, and the note it names."""
    claim = _note_path(line)
    if claim:
        return _Line(line, PINNED if pin_marker in line else CLAIM, claim)
    link = _ANY_LINK.search(line)
    path = link.group(1) if link else ""
    if in_pointer_section:
        return _Line(line, POINTER, path)
    return _Line(line, ORPHAN if path in claimed else REST, path)


def _fill(blocks: list[_Block], budget: int) -> list[set[int]]:
    """Which line indexes each block keeps.

    The budget is charged as the text is built: a block pays for its heading and
    its separator the first time it is opened, and every kept line pays for
    itself. Nothing is charged for a block that keeps nothing, so a heading can
    never appear over an empty section."""
    kept = [set() for _ in blocks]
    opened = [False for _ in blocks]
    used = 0
    for rank in _KEPT_RANKS:
        used = _take_rank(blocks, kept, opened, rank, used, budget)
    return kept


def _take_rank(
    blocks: list[_Block],
    kept: list[set[int]],
    opened: list[bool],
    rank: int,
    used: int,
    budget: int,
) -> int:
    """Give one rank's lines to the blocks in turn, one line each per round.

    A round ends when no block takes a line: either every line of this rank is
    kept, or what is left is too long for the remainder — and the remainder only
    shrinks, so a line that did not fit is taken off the queue for good.

    *ORPHAN* runs last, so by then every claim's fate is settled: a title whose
    note is already in the block is the duplicate this rank exists to suppress,
    and one whose claim did not fit is the note's only remaining trace."""
    shown = _kept_claim_paths(blocks, kept)
    queues = [
        [
            index
            for index, line in enumerate(block.lines)
            if line.rank == rank
            and index not in kept_at
            and not (line.rank == ORPHAN and line.path in shown)
        ]
        for block, kept_at in zip(blocks, kept)
    ]
    while True:
        taken = False
        for position, block in enumerate(blocks):
            while queues[position]:
                index = queues[position][0]
                cost = len(block.lines[index].text) + 1
                if not opened[position]:
                    cost += _open_cost(block.heading, any(opened))
                if used + cost > budget:
                    queues[position].pop(0)
                    continue
                queues[position].pop(0)
                kept[position].add(index)
                opened[position] = True
                used += cost
                taken = True
                break
        if not taken:
            return used


def _kept_claim_paths(blocks: list[_Block], kept: list[set[int]]) -> set[str]:
    """The notes whose own claim is already in the block."""
    return {
        block.lines[index].path
        for block, kept_at in zip(blocks, kept)
        for index in kept_at
        if block.lines[index].rank in (PINNED, CLAIM)
    }


def _open_cost(heading: str, separator: bool) -> int:
    """The heading, its blank line, and the separator before the block."""
    return (len(heading) + 4 if heading else 0) + (2 if separator else 0)


def _emit(blocks: list[_Block], kept: list[set[int]]) -> str:
    """The kept text, still shaped like an index."""
    parts = []
    for block, kept_at in zip(blocks, kept):
        if not kept_at:
            continue
        body = [block.lines[index].text for index in sorted(kept_at)]
        if block.heading:
            body = [f"## {block.heading}", "", *body]
        parts.append("\n".join(body))
    return "\n\n".join(parts)


def _hidden_note(blocks: list[_Block], kept: list[set[int]], limit: int) -> str:
    """One line naming the sections the cap had to leave out, plus `(...more)`.

    A section name is what the model needs to decide whether to search: the old
    summary named note categories, so a section lost whole read as a handful of
    notes. A duplicate title is not counted — its claim is already in the block,
    so nothing was withheld. The pinned count is called out because a hidden pin
    is the one loss that can change an answer rather than delay it. Sections are
    named biggest loss first, and only while the line still fits *limit*: under a
    tight cap a bare marker beats an index with no claims in it at all."""
    hidden = [
        [index for index in range(len(block.lines)) if index not in kept_at]
        for block, kept_at in zip(blocks, kept)
    ]
    lost = _lost_sections(blocks, hidden, _kept_claim_paths(blocks, kept))
    if not lost:
        return _MARKER
    pins = _pinned_count(blocks, hidden)
    names = _fit_names(lost, pins, limit)
    if not names:
        return _MARKER
    return f"{_render_note(names, pins, len(lost) - len(names))}\n{_MARKER}"


def _lost_sections(
    blocks: list[_Block], hidden: list[list[int]], shown: set[str]
) -> list[tuple[str, int]]:
    """Each section that held back a line worth reading, with how many.

    Ordered by the best line it lost, then by how many: a section missing a
    pinned line is a different loss from one missing twenty catalog titles, and
    counting alone would let the catalog — whose lines are the weakest in the
    index — lead the note every time it is the longest."""
    lost = []
    for block, indexes in zip(blocks, hidden):
        withheld = [
            block.lines[index]
            for index in indexes
            if _is_withheld(block, index, shown)
        ]
        if withheld:
            best = min(line.rank for line in withheld)
            lost.append((best, block.heading, len(withheld)))
    lost.sort(key=lambda item: (item[0], -item[2]))
    return [(heading, count) for _, heading, count in lost]


def _is_withheld(block: _Block, index: int, shown: set[str]) -> bool:
    """Whether leaving this line out cost the reader anything.

    A catalog title is a duplicate only once its note's claim is in the block. If
    that claim did not fit either, the title was the note's only trace, and
    losing it lost the note."""
    line = block.lines[index]
    return line.rank != ORPHAN or line.path not in shown


def _pinned_count(blocks: list[_Block], hidden: list[list[int]]) -> int:
    """How many pinned lines the cap left out."""
    return sum(
        1
        for block, indexes in zip(blocks, hidden)
        for index in indexes
        if block.lines[index].rank == PINNED
    )


def _fit_names(lost: list[tuple[str, int]], pins: int, limit: int) -> list[str]:
    """As many section names as the note line still fits, biggest loss first."""
    names: list[str] = []
    for heading, count in lost[:_NAMED_SECTIONS]:
        candidate = [*names, _name_loss(heading, count)]
        if len(_render_note(candidate, pins, len(lost) - len(candidate))) > limit:
            break
        names = candidate
    return names


def _render_note(names: list[str], pins: int, rest: int) -> str:
    """The note line: each named section, then what is left to say."""
    more = f" and {rest} more section{'s' if rest > 1 else ''}" if rest else ""
    tail = f"; {pins} pinned line{'s' if pins > 1 else ''} did not fit" if pins else ""
    return f"- Hidden {', '.join(names)}{more} — use SearchJournal{tail}."


def _name_loss(heading: str, count: int) -> str:
    """One hidden section as a reader would name it."""
    where = f"under ## {heading}" if heading else "at the top of the file"
    return f"{count} line{'s' if count > 1 else ''} {where}"
