"""Guards the ADR log against the drift Phase 10 reflowed away: average
paragraph length tripled from 226 chars (ADR-0001-0030) to 615
(ADR-0061-0091) before anyone measured it, and 126 paragraphs across 42
files had crossed 700 characters — a wall a reader has to stop and re-read.
This holds the line at the reflowed maximum (692), rounded up.

Also guards the two other density facts measured before Phase 10: the
non-ADR, non-changelog docs already average 154-228 chars per paragraph
(no rewrite needed there — this just stops it drifting), and 26 of 29 long
pages already carry a table of contents (the other three gained one in
Phase 10 Part B).

Changelogs are excluded from both paragraph checks on purpose: they are
append-only history, never re-read start to finish, so density there is
not the same defect it is in a lookup-table log or a guide.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
DOCS = REPO_ROOT / "docs"

MAX_ADR_PARAGRAPH_CHARS = 700
MAX_DOC_PARAGRAPH_CHARS = 900
MIN_LINES_REQUIRING_TOC = 150

# A paragraph that legitimately can't shrink further (a long quoted error
# message, a pinned config block not recognized as fenced) goes here by
# exact file path, with a reason. Empty on purpose — every real offender
# found while writing this ratchet fit one of Phase 10's three reflow moves
# instead. A growing list here means the threshold, not the paragraph, is
# wrong.
DENSITY_EXCEPTIONS: dict[str, set[int]] = {}

# Blocks that open with one of these are structure, not prose, and are
# never flagged: headings, tables, fenced code (the whole fence, tracked
# below — not just a block starting with a backtick), blockquotes, the
# breadcrumb, the ADR status line, and list items (a long bullet or
# numbered item is a list-formatting problem, not a wall-of-prose one).
_SKIP_PREFIXES = ("#", "|", "`", ">", "🔖", "-", "*")
_DIGIT_DOT = re.compile(r"^\d+\.")


def _iter_paragraphs(text: str):
    """Yield (paragraph_text, starting_line_number), splitting on blank
    lines but treating an entire ``` fenced block as one unsplittable unit
    even if it contains internal blank lines (e.g. a constructor sketch
    with comment-separated groups) — a naive blank-line split miscounts a
    fence's later chunks as bare prose paragraphs, since only the first
    chunk starts with the opening backtick."""
    lines = text.splitlines()
    para_lines: list[str] = []
    para_start = 1
    in_fence = False
    for lineno, line in enumerate(lines, start=1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
        if not line.strip() and not in_fence:
            if para_lines:
                yield "\n".join(para_lines), para_start
                para_lines = []
            continue
        if not para_lines:
            para_start = lineno
        para_lines.append(line)
    if para_lines:
        yield "\n".join(para_lines), para_start


def _offenders(paths, limit: int, exceptions: dict[str, set[int]]):
    offenders = []
    for path in paths:
        rel = str(path.relative_to(REPO_ROOT))
        exempt_lines = exceptions.get(rel, set())
        for para, lineno in _iter_paragraphs(path.read_text()):
            stripped = para.strip()
            if not stripped:
                continue
            if (
                stripped.startswith(_SKIP_PREFIXES)
                or stripped.startswith("**Status")
                or _DIGIT_DOT.match(stripped)
            ):
                continue
            if len(stripped) <= limit or lineno in exempt_lines:
                continue
            offenders.append(f"{rel}:{lineno} ({len(stripped)} chars) {stripped[:60]!r}")
    return offenders


def test_no_adr_paragraph_is_a_wall():
    """R-none (readability). No ADR paragraph exceeds
    MAX_ADR_PARAGRAPH_CHARS — the reflowed maximum is 692; this rounds up
    to the next hundred so a small addition to an existing record doesn't
    immediately trip the ratchet."""
    offenders = _offenders(
        DOCS.joinpath("adr").glob("adr-*.md"),
        MAX_ADR_PARAGRAPH_CHARS,
        DENSITY_EXCEPTIONS,
    )
    assert not offenders, (
        "ADR paragraph(s) over "
        f"{MAX_ADR_PARAGRAPH_CHARS} chars — reflow with one of the three "
        f"moves in plan/10-adr-and-docs-readability.md (numbered-list-is-"
        f"a-section, prose-is-a-table, split-the-sentence-chain): {offenders}"
    )


def test_no_doc_paragraph_is_a_wall():
    """Same check over every other doc page. Changelogs are excluded —
    append-only history, never re-read start to finish."""
    paths = [
        p
        for p in DOCS.rglob("*.md")
        if "changelog" not in str(p) and "/adr/" not in str(p)
    ]
    offenders = _offenders(paths, MAX_DOC_PARAGRAPH_CHARS, DENSITY_EXCEPTIONS)
    assert not offenders, f"Doc paragraph(s) over {MAX_DOC_PARAGRAPH_CHARS} chars: {offenders}"


def test_long_doc_pages_have_a_table_of_contents():
    """Any non-changelog, non-ADR page over MIN_LINES_REQUIRING_TOC lines
    names a "Table of Contents" section — the reader's way in without
    scrolling."""
    offenders = []
    for path in DOCS.rglob("*.md"):
        rel = str(path)
        if "changelog" in rel or "/adr/" in rel:
            continue
        text = path.read_text()
        if len(text.splitlines()) <= MIN_LINES_REQUIRING_TOC:
            continue
        if "table of contents" not in text.lower():
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, f"Long doc page(s) missing a Table of Contents: {offenders}"
