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

The header is the page's own map, so all three of its fields are required: the
tier says how deep the page goes, `Code:` says what it covers, and `Read first:`
says what to read when the page assumes too much. A page missing the last two
strands the reader who arrived from the change map holding a file and no page
that explains it.

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
flow with *What zrb keeps, and why* — but nothing may follow `### Change it
here`, so the reader can always count on where a page ends. `### Change it here`
rows all name a test, because a row that names only a file sends the reader to
the code with no way to check their change.

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

# The headings every page carries, in this order. `### Variations` is absent on
# purpose: a page whose content does not split into variations closes the flow
# with a section of its own instead, so only the two ends are pinned.
REQUIRED_SECTIONS = (
    "## Design",
    "### The problem",
    "### Principles",
    "### Invariants",
    "## Realization",
    "### The parts",
    "### How it runs",
)
FINAL_SECTION = "### Change it here"


def _header(path) -> re.Match | None:
    """The page's tier header line, or None when it has none."""
    return TIER_HEADER.search(path.read_text(encoding="utf-8"))


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
    """The header is the page's map: the tier, the code, what to read first."""
    offenders = []
    for path in pages():
        match = _header(path)
        if not match:
            offenders.append(f"{name_of(path)} (no tier header)")
            continue
        missing = [field for field in HEADER_FIELDS if field not in match.group(2)]
        if missing:
            offenders.append(f"{name_of(path)} header missing {missing}")
    assert not offenders, (
        "Page(s) whose tier header omits a field. The header reads "
        "`> **Tier N · <tier name>** · Code: `<paths>` · Read first: <link>`, so "
        f"a reader knows the page's subject and its prerequisite: {offenders}"
    )


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

    Realization is pinned at both ends, not throughout: `### The parts` opens it
    and `### Change it here` closes it, and nothing may follow the close. That is
    what lets a page own a section the format did not anticipate while keeping
    the reader's map of where a page ends.
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
        realization = section(text, "## Realization")
        ends_at = position(realization, FINAL_SECTION)
        if ends_at < 0:
            offenders.append(f"{name_of(path)} has no `{FINAL_SECTION}`")
            continue
        trailing = [
            match.group(1)
            for match in re.finditer(r"^### (.+)$", realization, re.MULTILINE)
            if match.start() > ends_at
        ]
        if trailing:
            offenders.append(f"{name_of(path)} has {trailing} after the close")
    assert not offenders, (
        "Page(s) without the required shape. `## Design` holds The problem, "
        "Principles and Invariants; `## Realization` opens with `### The parts`, "
        "runs the flow, and ends with `### Change it here` as the last section: "
        f"{offenders}"
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
            if "test" not in row[-1]:
                offenders.append(f"{name_of(path)}: {row[0][:50]}")
    assert not offenders, (
        "`### Change it here` row(s) whose last column names no test. Every row "
        "reads `To… | Open | Then run`, and the test is how the reader knows "
        f"their change landed: {offenders}"
    )


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
