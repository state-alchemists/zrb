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
arrive. A catalog title whose note already shows as a claim is tried last and
dropped once the claim is in — the block would otherwise state one fact twice,
the second time in the weaker form, for a quarter of the budget.

Two structural rules keep the result honest, because the failure this module
exists to fix was a rule stated in prose and implemented three times:

* **The cap is measured, never predicted.** A line is kept only when the text
  re-rendered with it still fits, so there is no second copy of the layout
  arithmetic to drift from the emitter.
* **The document is parsed by its writer.** `journal_index` owns what a heading,
  a claim and a catalog entry are; this module imports them rather than reading
  the rendered text a second time with regular expressions of its own.

Pure: strings in, strings out. No `CFG`, no I/O, so the caller owns both.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

# Ranks, best first. A claim outranks a pointer: the block's own header already
# says that each category's own index lists every note ever written in it, so the
# `## Directories` line is the cheaper thing to lose. `DUPLICATE` is a catalog
# title whose note also has a claim in the file: it is a duplicate *if that claim
# was kept*, so it is tried last and dropped once the claim is in — a claim too
# long to fit leaves the short title as the note's only trace.
PINNED, CLAIM, POINTER, REST, DUPLICATE = range(5)
_BEST_FIRST = (PINNED, CLAIM, POINTER, REST)

# The newline between the kept text and the note that stands in for the rest.
_JOIN = "\n"
# The blank line between two rendered blocks, which is layout rather than cost:
# nothing is measured from it, so it cannot fall out of step with `_render`.
_BLOCK_GAP = "\n\n"

# How many hidden sections the overflow note names before it counts the rest,
# and how many characters of the cap the note may spend at most.
_NAMED_SECTIONS = 3
_MAX_NOTE = 200
_MARKER = "(...more)"


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


@dataclass(frozen=True)
class _Roles:
    """What this reader takes from the writer's vocabulary: which two sections are
    the directory pointer and the catalog.

    Read from `journal_index` rather than spelled again here, so a rename reaches
    both sides. The catalog is named rather than inferred because a duplicate
    title is dropped: suppressing a hand-written line that happens to link a
    claimed note would lose content that exists nowhere else. The pin marker is
    not here: `journal_index.is_pinned_line` reads it, next to the function that
    writes it."""

    pointer: str
    catalog: str


def plan_index_core(content: str, budget: int) -> tuple[str, str]:
    """Split *content* into the text the cap keeps and a note about the rest.

    *budget* bounds the whole injection in characters — the overflow note is
    charged to it as well, because a cap that exempts what stands in for the
    dropped text is not a cap: the old one took a 2,500-char slice and then
    appended the summary on top, for a 4,049-char block. `<= 0` keeps everything,
    for a caller that has already decided what a zero or negative cap means.

    The result is `("", "")` when the cap keeps no line of the index, or cannot
    hold the note that says so: a truncated index that does not say it is
    truncated reads as the whole index, and a bare `(...more)` with nothing above
    it is not an index either. Both are the failures this module exists to
    prevent, and `render_journal_index` turns either into no block at all.
    """
    if budget <= 0 or len(content) <= budget:
        return content, ""
    blocks = _read_blocks(content)
    # A quarter of the cap, at most, explains what the rest of it left out. Fixed
    # before the fill rather than measured after it, because the note grows as
    # the body shrinks — the two would chase each other, and the line that paid
    # for the note was a claim.
    reserve = min(_MAX_NOTE, budget // 4)
    kept = _fill(blocks, budget - reserve)
    body = _render(blocks, kept)
    if not body:
        # No line of the index fitted. A marker alone says only that something was
        # cut, and there is nothing to cut it from.
        return "", ""
    note = _overflow(blocks, kept, body, budget)
    if not note:
        return "", ""
    return body, note


def join_overflow(body: str, note: str) -> str:
    """The injected text: the kept index, then the note standing in for the rest.

    `live_context` injects this, and `plan_index_core` measures the cap against
    it, so the two cannot disagree about where the newline goes. An empty body
    takes no newline: under a cap that keeps nothing there is only the note.
    """
    if not note:
        return body
    return f"{body}{_JOIN}{note}" if body else note


def _heading_name(heading: str) -> str:
    """A `## heading` constant as the writer's parser reports it: the words alone."""
    return heading.removeprefix("## ").strip()


def _read_blocks(content: str) -> list[_Block]:
    """The index as blocks of ranked lines, read with the writer's own parser.

    The preamble — the title, and any hand-written lines above the first `## `
    heading — is one more block, with no heading, rather than fixed text, so no
    part of the file can push the block past the cap on its own.

    Blank lines are dropped: a section's layout is rebuilt when it is emitted, so
    a blank one is not a candidate for the budget, and letting one compete opened
    a section whose heading then stood over no lines at all.
    """
    # Deferred: a module-level import of `zrb.llm.tool` here would close a
    # package cycle — two tool modules read `zrb.llm.prompt.prompt`.
    from zrb.llm.tool import journal_index

    roles = _Roles(
        pointer=_heading_name(journal_index.DIRECTORIES_HEADING),
        catalog=_heading_name(journal_index.CATALOG_HEADING),
    )
    preamble, sections = journal_index.split_index_sections(content)
    raw = [("", preamble), *sections]
    claims = {
        owner
        for _, body in raw
        for owner in map(journal_index.hud_owner, body)
        if owner
    }
    return [
        _Block(
            heading,
            tuple(_rank(line, heading, roles, claims) for line in body if line.strip()),
        )
        for heading, body in raw
    ]


def _rank(line: str, heading: str, roles: _Roles, claims: set[str]) -> _Line:
    """What this line is worth, and the note it names."""
    # Deferred, as in `_read_blocks`.
    from zrb.llm.tool.journal_index import bare_target, hud_owner, is_pinned_line

    owner = hud_owner(line)
    if owner:
        return _Line(line, PINNED if is_pinned_line(line) else CLAIM, owner)
    target = bare_target(line) or ""
    if heading == roles.pointer:
        return _Line(line, POINTER, target)
    if heading == roles.catalog and target in claims:
        return _Line(line, DUPLICATE, target)
    return _Line(line, REST, target)


def _fill(blocks: list[_Block], room: int) -> list[set[int]]:
    """Which line indexes each block keeps, best rank first.

    The section that comes first in the file no longer decides: a rank is spent
    across the sections in turn, and a line is kept only when the text re-rendered
    with it still fits *room*. A line that does not fit is dropped for good —
    keeping more never shortens what is already there.

    `DUPLICATE` runs last, so by then every claim's fate is settled: a title whose
    note is already in the block is the duplicate this rank exists to suppress,
    and one whose claim did not survive is the note's only remaining trace.
    """
    kept = [set() for _ in blocks]
    for rank in _BEST_FIRST:
        _admit(blocks, kept, _in_turn(blocks, rank), room)
    shown = _claimed_paths(blocks, kept)
    duplicates = (
        place
        for place in _in_turn(blocks, DUPLICATE)
        if blocks[place[0]].lines[place[1]].path not in shown
    )
    _admit(blocks, kept, duplicates, room)
    return kept


def _in_turn(blocks: list[_Block], rank: int) -> Iterator[tuple[int, int]]:
    """One rank's lines as `(block, line)`, each section taking one per round."""
    queues = [
        [index for index, line in enumerate(block.lines) if line.rank == rank]
        for block in blocks
    ]
    while any(queues):
        for position, queue in enumerate(queues):
            if queue:
                yield position, queue.pop(0)


def _admit(
    blocks: list[_Block],
    kept: list[set[int]],
    candidates: Iterator[tuple[int, int]],
    room: int,
) -> None:
    """Keep each candidate the re-rendered text still has room for."""
    for position, index in candidates:
        kept[position].add(index)
        if len(_render(blocks, kept)) > room:
            kept[position].discard(index)


def _claimed_paths(blocks: list[_Block], kept: list[set[int]]) -> set[str]:
    """The notes whose own claim is already in the block."""
    return {
        block.lines[index].path
        for block, kept_at in zip(blocks, kept)
        for index in kept_at
        if block.lines[index].rank in (PINNED, CLAIM)
    }


def _render(blocks: list[_Block], kept: list[set[int]]) -> str:
    """The kept text, still shaped like an index.

    This is the only place the size of the block is decided: `_admit` calls it and
    compares the result against the cap, so nothing can be charged for text that
    is not emitted, and nothing emitted can go uncharged."""
    parts = [
        _render_block(block, kept_at) for block, kept_at in zip(blocks, kept) if kept_at
    ]
    return _BLOCK_GAP.join(parts)


def _render_block(block: _Block, kept_at: set[int]) -> str:
    """One section: its heading over the lines it kept, or the lines alone."""
    body = [block.lines[index].text for index in sorted(kept_at)]
    if not block.heading:
        return _JOIN.join(body)
    return _BLOCK_GAP.join((f"## {block.heading}", *body))


def _overflow(
    blocks: list[_Block], kept: list[set[int]], body: str, budget: int
) -> str:
    """The overflow note, or `""` when not even the marker fits.

    Candidates run from the most informative to the least — every section the
    cap could name, then fewer, then the bare marker — and the first one that
    still fits *budget* once joined to *body* wins. A section name is what the
    model needs in order to decide whether to search, so a bare count of notes
    reads as "nothing important". The pinned count is called out because a hidden
    pin is the one loss that can change an answer rather than delay it.
    """
    lost = _lost_sections(blocks, kept)
    pins = _hidden_pins(blocks, kept)
    for named in range(min(len(lost), _NAMED_SECTIONS), 0, -1):
        note = f"{_note_line(lost[:named], len(lost) - named, pins)}{_JOIN}{_MARKER}"
        if len(join_overflow(body, note)) <= budget:
            return note
    return _MARKER if len(join_overflow(body, _MARKER)) <= budget else ""


def _lost_sections(blocks: list[_Block], kept: list[set[int]]) -> list[tuple[str, int]]:
    """Each section that held back a line worth reading, with how many.

    Ordered by the best line it lost, then by how many: a section missing a
    pinned line is a different loss from one missing twenty catalog titles, and
    counting alone would let the catalog — whose lines are the weakest in the
    index — lead the note every time it is the longest.

    A duplicate title is not counted when its claim is in the block: nothing was
    withheld, since the claim says the same thing, so calling it hidden would
    send the model looking for a fact it already has."""
    shown = _claimed_paths(blocks, kept)
    lost = []
    for block, kept_at in zip(blocks, kept):
        withheld = [
            line
            for index, line in enumerate(block.lines)
            if index not in kept_at
            and (line.rank != DUPLICATE or line.path not in shown)
        ]
        if withheld:
            best = min(line.rank for line in withheld)
            lost.append((best, block.heading, len(withheld)))
    lost.sort(key=lambda item: (item[0], -item[2]))
    return [(heading, count) for _, heading, count in lost]


def _hidden_pins(blocks: list[_Block], kept: list[set[int]]) -> int:
    """How many pinned lines the cap left out."""
    return sum(
        1
        for block, kept_at in zip(blocks, kept)
        for index, line in enumerate(block.lines)
        if index not in kept_at and line.rank == PINNED
    )


def _note_line(names: list[tuple[str, int]], rest: int, pins: int) -> str:
    """The note line: each named section, then what is left to say."""
    more = f" and {rest} more section{'s' if rest > 1 else ''}" if rest else ""
    tail = f"; {pins} pinned line{'s' if pins > 1 else ''} did not fit" if pins else ""
    listed = ", ".join(_name_loss(heading, count) for heading, count in names)
    return f"- Hidden {listed}{more} — use SearchJournal{tail}."


def _name_loss(heading: str, count: int) -> str:
    """One hidden section as a reader would name it."""
    where = f"under ## {heading}" if heading else "at the top of the file"
    return f"{count} line{'s' if count > 1 else ''} {where}"
