"""Guards the architecture section's shape.

THE SHAPE. Each tier is a directory under `docs/architecture/`, and every page
in it declares its tier in a header line:

    > **Tier 2 · Extension surface** · Code: `src/zrb/llm/tool/` · Read first: [The LLM Turn](../1-spine/llm-turn.md)

- **`0-system/`** — the parts, the objects that own state, the invariants.
- **`1-spine/`** — the two runtimes: deterministic work, and the agentic turn.
- **`2-extension-surface/`** — where maintenance happens: tools, UI, prompts,
  hooks, config, sub-agents.
- **`3-peripheral-flow/`** — on demand, off the reading path.

Within a tier, a page earns its place by how often its code changes.

The header is the page's own map, so all three of its fields are required *and
their values are checked*: the tier says how deep the page goes, `Code:` names at
least one backticked path the page covers, and `Read first:` names a relative
link — except on the entry page, which says there is no page before it. A header
reading `Code: nothing · Read first: unknown` has both labels and neither answer,
and a page missing the last two strands the reader who arrived from the change
map holding a file and no page that explains it.

Every page then opens with one line naming the single idea to take away — the
sentence a reader keeps if they read nothing else. It sits directly under the
header, so a page cannot bury its point in a later paragraph.

After that, two halves. `## Design` is the stable half: the problem, the
principles (each linking the ADR that records it), and the invariants (each
naming the test that pins it). It never names a private symbol, because a
private symbol is free to change. `## Realization` is the volatile half, and it
is pinned at both ends rather than throughout: it opens with `### The parts` and
closes with `### Change it here`. A page may put one section of its own between
them — [Voice on Pipecat](../3-peripheral-flow/voice-on-pipecat.md) closes its
flow with *What zrb keeps, and why* — but nothing may follow `### Change it here`
inside the half. The page then closes with `## See Also`, the one section allowed
after Realization, so the reader can count on where a page ends. `### Change it
here` rows all name a test, because a row that names only a file sends the reader
to the code with no way to check their change.

`README.md` and `change-map.md` sit at the section root. They are navigation,
exempt from the shape rules here but not from the truth check, which lives in
`test_architecture_doc_symbols.py`.
"""

import re

from termaid import render

from architecture_docs import (
    INDEX,
    NAVIGATION,
    REPO_ROOT,
    TIER_DIRS,
    blocks,
    files,
    has_heading,
    lifelines,
    name_of,
    pages,
    position,
    rows_in,
    section,
    ticks_in,
)

# How much depth each tier may carry. Measured, not estimated: past 120 columns
# zrb's own renderer compacts a diagram and then word-wraps it, which corrupts
# the box-drawing art, so a diagram past the budget renders broken rather than
# merely wide. 3 lifelines with short labels is 78 columns, 4 is 104, 6 is 152.
MAX_WIDTH = 120
MAX_PARTICIPANTS = 4
TIER_DIAGRAM_BUDGET = {0: 1, 1: 6, 2: 6, 3: 8}

TIER_HEADER = re.compile(r"^> \*\*Tier ([0-3]) · (.+)$", re.MULTILINE)
TAKEAWAY = "The one idea to take away:"
HEADER_FIELDS = ("Code:", "Read first:")
ADR_LINK = re.compile(r"\(\.\./\.\./adr/adr-\d{4}\.md\)")

# The two header values, checked as well as the labels: `Code:` takes at least one
# backticked path *that resolves*, and `Read first:` a relative link — or, on the
# entry page, the sentence saying there is nothing before it. `Code:` is resolved
# here rather than left to the symbol guard, which only recognizes the
# `src/zrb|zrb|llm` prefixes it knows: a page could name `does/not-exist/` and pass
# both guards.
TICKED_PATH = re.compile(r"`([^`]+)`")
READ_FIRST_LINK = re.compile(r"\[[^\]]+\]\((?!https?://)[^)]+\)")
FIRST_PAGE = "this is the first page"

# The headings every page carries, in this order. `### Variations` is absent on
# purpose: a page whose content does not split into variations closes the flow
# with a section of its own instead. That freedom is bounded by the two ends —
# Realization's first child heading is `OPENING_SECTION`, its last is
# `FINAL_SECTION` — so a section of the page's own may sit between them and
# nowhere else. `### Change it here` also ends Realization itself: the only
# section a page may carry after the half is `AFTER_SECTION`, whose list of links
# — and then the breadcrumb that closes the file — is the last thing on the page.
OPENING_SECTION = "### The parts"
FINAL_SECTION = "### Change it here"
AFTER_SECTION = "## See Also"
BREADCRUMB = "🔖"
REQUIRED_SECTIONS = (
    "## Design",
    "### The problem",
    "### Principles",
    "### Invariants",
    "## Realization",
    OPENING_SECTION,
    "### How it runs",
)
# A runnable test target in a table cell: a backticked `test/...` path, naming
# either a directory (`test/llm/ui/`) or one test (`test/x.py::test_y`).
TEST_PATH = re.compile(r"`test/")


def _header(path) -> re.Match | None:
    """The page's tier header line, or None when it has none."""
    return TIER_HEADER.search(path.read_text(encoding="utf-8"))


def _header_field(body: str, field: str) -> str | None:
    """A header field's value, up to the next ` · `; None when the field is absent.

    The tier name holds a ` · ` of its own (`**Tier 2 · Extension surface**`), so
    the fields are read by their labels rather than by splitting the line.
    """
    match = re.search(rf"{re.escape(field)}\s*(.*?)(?=\s+·\s+|$)", body)
    return match.group(1).strip() if match else None


def test_every_architecture_page_is_linked_from_the_index():
    """A flow page the section index does not name is unreachable."""
    index = INDEX.read_text(encoding="utf-8")
    orphans = [name_of(p) for p in pages() if f"({name_of(p)})" not in index]
    assert not orphans, (
        "Architecture page(s) not linked from docs/architecture/README.md — "
        f"add each to its tier list: {orphans}"
    )


def test_every_file_lives_in_a_tier_directory():
    """A page outside the tier directories escapes every check below."""
    stray = [
        name_of(p)
        for p in files()
        if name_of(p) not in NAVIGATION and p.parent.name not in TIER_DIRS
    ]
    assert not stray, (
        "Architecture file(s) outside the tier directories. Move each into "
        f"one of {sorted(TIER_DIRS)}: {stray}"
    )


def test_every_page_declares_the_tier_of_its_directory():
    """The header tells a reader the tier; the directory must agree with it."""
    offenders = []
    for path in pages():
        match = _header(path)
        expected = TIER_DIRS[path.parent.name]
        if not match or int(match.group(1)) != expected:
            offenders.append(f"{name_of(path)} (expected Tier {expected})")
    assert not offenders, (
        "Page(s) whose `> **Tier N · …**` header is missing or names a "
        f"different tier from its directory: {offenders}"
    )


def test_every_page_header_names_its_code_and_its_prerequisite():
    """The header is the page's map: the code it covers, and what to read first.

    Checking only that the labels appear would pass a header whose values answer
    nothing — `Code: nothing · Read first: unknown`, or an empty field. The values
    are checked, and so is what `Code:` names: a path-shaped value with no file
    behind it (`Code: does/not-exist/`) answers no better than an empty one, and
    the reader it strands is the one who arrived from the Change Map holding a file.
    """
    offenders = []
    for path in pages():
        match = _header(path)
        if not match:
            offenders.append(f"{name_of(path)} (no tier header)")
            continue
        header = match.group(2)
        code = _header_field(header, "Code:")
        read_first = _header_field(header, "Read first:")
        missing = [
            field
            for field, value in zip(HEADER_FIELDS, (code, read_first))
            if value is None
        ]
        if missing:
            offenders.append(f"{name_of(path)} header missing {missing}")
            continue
        unknown = [
            token
            for token in TICKED_PATH.findall(code or "")
            if not _names_a_repository_path(token)
        ]
        if not TICKED_PATH.search(code or ""):
            offenders.append(f"{name_of(path)} `Code:` names no path: {code!r}")
        elif unknown:
            offenders.append(f"{name_of(path)} `Code:` names {unknown}, which is gone")
        elif read_first != FIRST_PAGE and not READ_FIRST_LINK.search(read_first or ""):
            offenders.append(
                f"{name_of(path)} `Read first:` is no relative link: {read_first!r}"
            )
    assert not offenders, (
        "Page(s) whose tier header does not say what the page covers and what to "
        "read first. The header reads `> **Tier N · <tier name>** · Code: "
        "`<paths>` · Read first: <link>`, so `Code:` takes at least one backticked "
        "repository path, each one resolving to a real file or directory, and "
        f"`Read first:` a relative link — the entry page says `{FIRST_PAGE}` "
        f"instead: {offenders}"
    )


def _names_a_repository_path(token: str) -> bool:
    """Whether a `Code:` token resolves to a file or directory inside the checkout.

    `does/not-exist/` has the shape of a path and nothing else, and the symbol guard
    cannot catch it: that guard resolves only the `src/zrb|zrb|llm` prefixes it
    recognizes, so a page naming an arbitrary directory passed both guards.
    """
    candidate = (REPO_ROOT / token).resolve()
    return candidate.is_relative_to(REPO_ROOT.resolve()) and candidate.exists()


def test_every_page_opens_with_its_single_idea():
    """One sentence the reader keeps if they read nothing else."""
    offenders = []
    for path in pages():
        lines = path.read_text(encoding="utf-8").splitlines()
        header_at = next(
            (i for i, line in enumerate(lines) if TIER_HEADER.match(line)), None
        )
        if header_at is None:
            continue  # reported by the tier-header test
        intro = next((line for line in lines[header_at + 1 :] if line.strip()), "")
        if TAKEAWAY not in intro:
            offenders.append(name_of(path))
    assert not offenders, (
        f"Page(s) whose opening line under the header does not carry "
        f"`{TAKEAWAY}`. State the one idea the page exists to deliver, in one "
        f"sentence, before the table of contents: {offenders}"
    )


def test_every_page_has_a_design_and_a_realization():
    """Design is the stable half, Realization the volatile one; both must be there.

    Realization is pinned at both ends, not throughout: its first child heading is
    `### The parts` and its last is `### Change it here`. Pinning the ends is what
    lets a page own a section the format did not anticipate while keeping the
    reader's map of where a page starts and stops — an extra section is allowed
    between the two and nowhere else.
    """
    offenders = []
    for path in pages():
        text = path.read_text(encoding="utf-8")
        missing = [s for s in REQUIRED_SECTIONS if not has_heading(text, s)]
        if missing:
            offenders.append(f"{name_of(path)} missing {missing}")
            continue
        where = [position(text, s) for s in REQUIRED_SECTIONS]
        if where != sorted(where):
            offenders.append(f"{name_of(path)} puts its sections out of order")
            continue
        children = _subsections(section(text, "## Realization"))
        opens_with = children[0] if children else "nothing"
        if opens_with != _heading(OPENING_SECTION):
            offenders.append(f"{name_of(path)} opens Realization with {opens_with!r}")
            continue
        if children[-1] != _heading(FINAL_SECTION):
            offenders.append(
                f"{name_of(path)} closes Realization with {children[-1]!r}"
            )
    assert not offenders, (
        "Page(s) without the required shape. `## Design` holds The problem, "
        "Principles and Invariants, in order; `## Realization` opens with "
        "`### The parts` and closes with `### Change it here`. A section of the "
        "page's own may sit between those two ends and nowhere else: "
        f"{offenders}"
    )


def _top_level_headings(text: str) -> list[str]:
    """Every `##` heading's own name, in order (`## See Also` reads `See Also`)."""
    return re.findall(r"^## (.+)$", text, re.MULTILINE)


def test_see_also_is_the_only_section_after_realization():
    """Where a page ends: `## See Also`, then its list, then nothing.

    `section(text, "## Realization")` stops at the next `##`, so the checks above
    see only the headings inside the half and would let a whole new `##` section
    follow `### Change it here` — which the README says cannot happen. Realization
    is the last half of a page, and `## See Also` the only section after it.

    Comparing heading names alone would still let a page keep writing after that
    heading — a paragraph, a table, a `###` section — while claiming See Also
    closes it. What follows is the list of pages to read next and, at most, the
    breadcrumb line that ends the file, so "where a page ends" is true as written.
    """
    offenders = []
    for path in pages():
        text = path.read_text(encoding="utf-8")
        headings = _top_level_headings(text)
        if "Realization" not in headings:
            continue  # reported by the shape check
        trailing = headings[headings.index("Realization") + 1 :]
        if trailing != [_heading(AFTER_SECTION)]:
            offenders.append(f"{name_of(path)} closes with {trailing}")
            continue
        stray = [
            line.strip()
            for line in section(text, AFTER_SECTION).splitlines()
            if line.strip()
            and not line.startswith("- ")
            and not line.startswith(BREADCRUMB)
        ]
        if stray:
            offenders.append(f"{name_of(path)} writes on after See Also: {stray[:2]}")
    assert not offenders, (
        "Page(s) that do not end with `## See Also`, or that keep writing after it. "
        "`## Realization` is the last half of a page, `## See Also` the only section "
        "allowed after it, and its list of links the last thing before the closing "
        f"breadcrumb, so a reader can count on where a page ends: {offenders}"
    )


def test_every_principle_links_its_adr():
    """A principle with no ADR is an opinion; the ADR is where it was decided."""
    offenders = []
    for path in pages():
        body = section(path.read_text(encoding="utf-8"), "### Principles")
        for line in body.splitlines():
            if re.match(r"^\d+\. ", line) and not ADR_LINK.search(line):
                offenders.append(f"{name_of(path)}: {line[:60]}")
    assert not offenders, (
        "Principle(s) with no ADR link. End each numbered principle with "
        f"`→ [ADR-NNNN](../../adr/adr-NNNN.md)`: {offenders}"
    )


def test_every_invariant_names_the_test_that_pins_it():
    """An invariant nobody tests is a hope; say which test holds it, or say it is unpinned."""
    offenders = []
    for path in pages():
        body = section(path.read_text(encoding="utf-8"), "### Invariants")
        rows = rows_in(body)
        if not rows:
            offenders.append(f"{name_of(path)}: no invariants table")
        for row in rows:
            if "`test/" not in "|".join(row) and "unpinned" not in "|".join(row):
                offenders.append(f"{name_of(path)}: {'|'.join(row)[:60]}")
    assert not offenders, (
        "Invariant row(s) with no pinning test. Put a "
        "`test/...::test_name` in the last column, or write **unpinned** so the "
        f"gap is visible: {offenders}"
    )


def test_design_names_no_private_symbol():
    """The design half must survive a refactor; a private name will not."""
    offenders = []
    for path in pages():
        design = section(path.read_text(encoding="utf-8"), "## Design")
        for token in ticks_in(design):
            if token.startswith("test/"):
                continue
            if re.search(r"(?:^|[.\s])_[a-z]", token):
                offenders.append(f"{name_of(path)}: `{token}`")
    assert not offenders, (
        "Private symbol(s) in a Design section. Name the public owner instead, "
        f"or move the detail to Realization: {offenders}"
    )


def test_every_change_row_names_a_test():
    """A row that names only a file sends the reader to the code with no way to check."""
    offenders = []
    for path in pages():
        body = section(path.read_text(encoding="utf-8"), FINAL_SECTION)
        rows = rows_in(body)
        if not rows:
            offenders.append(f"{name_of(path)}: no rows")
        for row in rows:
            if not TEST_PATH.search(row[-1]):
                offenders.append(f"{name_of(path)}: {row[0][:50]}")
    assert not offenders, (
        "`### Change it here` row(s) whose last column names no test path. Every "
        "row reads `To… | Open | Then run`, and the test is how the reader knows "
        f"their change landed — name a backticked `test/...` path: {offenders}"
    )


def _heading(required: str) -> str:
    """A required heading's own name, without its hashes (`### The parts`)."""
    return required.split(" ", 1)[1]


def _subsections(body: str) -> list[str]:
    """The `###` headings inside a section body, in the order they appear."""
    return re.findall(r"^### (.+)$", body, re.MULTILINE)


def test_depth_follows_tier():
    """A page may not carry more diagrams than its tier allows."""
    offenders = []
    for path in pages():
        match = _header(path)
        assert match, f"{name_of(path)} has no tier header"
        tier = int(match.group(1))
        count = len(blocks(path))
        if count > TIER_DIAGRAM_BUDGET[tier]:
            offenders.append(
                f"{name_of(path)} is Tier {tier} with {count} diagrams "
                f"(budget {TIER_DIAGRAM_BUDGET[tier]})"
            )
    assert not offenders, (
        "Page(s) past their tier's diagram budget. Depth is a tier property: a "
        "Tier 3 peripheral flow may go deeper than a Tier 1 spine page, and a "
        "Tier 0 page gets one map and no sequences. Split the page rather than "
        f"raising its tier: {offenders}"
    )


def test_every_tier_is_represented():
    """Losing a tier is how the format quietly collapses back to a flat list."""
    declared = set()
    for path in pages():
        match = _header(path)
        if match:
            declared.add(int(match.group(1)))
    missing = sorted(set(TIER_DIAGRAM_BUDGET) - declared)
    assert not missing, (
        f"No page declares Tier {missing}. Tiers 0-3 are the general-to-specific "
        "spine of the section; an empty tier means the section lost a level."
    )


def test_every_diagram_fits_the_width_budget():
    """No diagram is wider than the renderer can lay out on one line."""
    offenders = []
    for path in files():
        for line, source in blocks(path):
            art = render(source)
            width = max((len(row) for row in art.splitlines()), default=0)
            if width > MAX_WIDTH:
                offenders.append(
                    f"{path.relative_to(REPO_ROOT).as_posix()}:{line} "
                    f"({width} columns)"
                )
    assert not offenders, (
        f"Diagram(s) over {MAX_WIDTH} columns — split by phase rather than "
        f"drawing them denser, and keep message labels short: {offenders}"
    )


def test_no_sequence_diagram_has_too_many_lifelines():
    """Past four lifelines the layout runs wide before any label is added."""
    offenders = []
    for path in files():
        for line, source in blocks(path):
            count = len(lifelines(source))
            if count > MAX_PARTICIPANTS:
                offenders.append(
                    f"{path.relative_to(REPO_ROOT).as_posix()}:{line} "
                    f"({count} lifelines)"
                )
    assert not offenders, (
        f"Sequence diagram(s) with more than {MAX_PARTICIPANTS} lifelines — draw "
        f"only the objects that exchange messages, and split the flow: {offenders}"
    )
