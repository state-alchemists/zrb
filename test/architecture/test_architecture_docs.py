"""Guards the architecture section: its shape, and that what it names is real.

THE SHAPE. Every page below `README.md` declares one tier in a header line:

    > **Tier 2 · Extension surface** · Code: `src/zrb/llm/tool/` · Read first: [The LLM Turn](llm-turn.md)

- **Tier 0 — System.** The parts, the objects that own state, the invariants.
- **Tier 1 — Spine.** The two runtimes: deterministic work, and the agentic turn.
- **Tier 2 — Extension surface.** Where maintenance happens: tools, UI, prompts,
  hooks, config, sub-agents.
- **Tier 3 — Peripheral flow.** On demand, off the reading path.

Within a tier, a page earns its place by how often its code changes.

Every page has two halves. `## Design` is the stable half: the problem, the
principles (each linking the ADR that records it), and the invariants (each
naming the test that pins it). It never names a private symbol, because a
private symbol is free to change. `## Realization` is the volatile half: the
parts, the flow, and where to make a change.

THE TRUTH CHECK. Every backticked `src/` or `test/` path must exist, a
`file.py::name` reference must name something defined in that file, and every
backticked identifier must still appear somewhere under `src/` or `test/`. A
rename that leaves a page stale fails here, so the cost of updating the page
falls on whoever made the rename.

`README.md` and `change-map.md` are navigation and are exempt from the shape
rules, but not from the truth check.
"""

import re
from pathlib import Path

from termaid import render

REPO_ROOT = Path(__file__).parents[2]
ARCHITECTURE = REPO_ROOT / "docs" / "architecture"
INDEX = ARCHITECTURE / "README.md"
# Navigation, not content: how you find a page, rather than a page about a
# subsystem. `README.md` is the tier index; `change-map.md` routes an intent to
# the file that decides it. Neither owns a flow, so neither declares a tier.
NAVIGATION = {"README.md", "change-map.md"}

# How much depth each tier may carry. Measured, not estimated: past 120 columns
# zrb's own renderer compacts a diagram and then word-wraps it, which corrupts
# the box-drawing art, so a diagram past the budget renders broken rather than
# merely wide. 3 lifelines with short labels is 78 columns, 4 is 104, 6 is 152.
MAX_WIDTH = 120
MAX_PARTICIPANTS = 4
TIER_DIAGRAM_BUDGET = {0: 1, 1: 6, 2: 6, 3: 8}

_FENCE = re.compile(r"^\s*```mermaid\n(.*?)^\s*```", re.DOTALL | re.MULTILINE)
_PARTICIPANT = re.compile(r"^\s*participant \w+ as (.+?)\s*$", re.MULTILINE)
_WORD = re.compile(r"[^\w.]")
TIER_HEADER = re.compile(r"^> \*\*Tier ([0-3]) ·", re.MULTILINE)
REQUIRED_SECTIONS = (
    "## Design",
    "### Principles",
    "### Invariants",
    "## Realization",
    "### The parts",
    "### Change it here",
)
_TICK = re.compile(r"`([^`\n]+)`")
_IDENT = re.compile(r"[A-Za-z_][\w.]*(?:\(\))?")
_ADR_LINK = re.compile(r"\(\.\./adr/adr-\d{4}\.md\)")

# The only labels allowed to name no symbol: the boundary of the system, where
# the reader is outside the codebase entirely.
_BOUNDARY = {"Caller", "User", "browser", "shell", "terminal", "client"}


def _pages() -> list[Path]:
    """The tiered content pages — everything except the two navigation files."""
    return sorted(
        p for p in ARCHITECTURE.glob("*.md") if p.name not in NAVIGATION
    )


def _files() -> list[Path]:
    """Every markdown file in the section, navigation included."""
    return sorted(ARCHITECTURE.glob("*.md"))


def _blocks(path: Path) -> list[tuple[int, str]]:
    """Every mermaid block as (line of first content, source)."""
    text = path.read_text(encoding="utf-8")
    return [
        (text[: match.start(1)].count("\n") + 1, match.group(1))
        for match in _FENCE.finditer(text)
    ]


def _symbols() -> set[str]:
    """Every name zrb itself uses for something a reader can go and open.

    Three sources, because a lifeline may legitimately be any of them:

    - a class or function defined under `src/`;
    - a name a module under `src/` re-exports from a third-party package — this
      is how `Tool`, `ToolApproved` and `ToolDenied` exist in zrb at all (see
      `src/zrb/llm/agent/types.py`);
    - a name a tool is registered under, which is how `DelegateToAgent` and
      `DelegateToAgentBackground` exist — real callables, named by assignment.

    A name that is none of these is a role invented for the drawing, and the
    whole point of the check is that the reader cannot go and open it.
    """
    names: set[str] = set()
    for path in (REPO_ROOT / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        names |= set(re.findall(r"^\s*class (\w+)", text, re.MULTILINE))
        names |= set(re.findall(r"^\s*(?:async )?def (\w+)", text, re.MULTILINE))
        # Re-exports: a whole import clause, split into identifiers below.
        clauses = re.findall(
            r"^\s*from [\w.]+ import \(?([^)\n]+)", text, re.MULTILINE
        )
        names |= set(part for clause in clauses for part in clause.split(","))
        # Tool registration: only the tool package names things this way, and
        # scoping it there keeps a stray quoted word from blessing a role-noun.
        if "llm/tool" in path.as_posix():
            names |= set(re.findall(r'"(\w+)"', text))
    return set(re.findall(r"[A-Za-z_]\w*", " ".join(names)))


def _lifelines(source: str) -> list[str]:
    return [label.strip() for label in _PARTICIPANT.findall(source)]


def test_every_architecture_page_is_linked_from_the_index():
    """A flow page the section index does not name is unreachable."""
    index = INDEX.read_text(encoding="utf-8")
    orphans = [path.name for path in _pages() if f"({path.name})" not in index]
    assert not orphans, (
        "Architecture page(s) not linked from docs/architecture/README.md — "
        f"add each to its tier list: {orphans}"
    )


def test_every_page_declares_its_tier():
    """A page with no tier is a page with no place in the reading order."""
    offenders = [
        path.name
        for path in _pages()
        if not TIER_HEADER.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, (
        "Page(s) with no `> **Tier N · …**` header. The tier is what makes the "
        "section general-to-specific instead of a flat pile; add the header "
        f"line naming the tier, the owning directory, and the page to read "
        f"first: {offenders}"
    )


def _has_heading(text: str, heading: str) -> bool:
    return re.search(rf"^{re.escape(heading)}\s*$", text, re.MULTILINE) is not None


def _section(text: str, heading: str) -> str:
    """The body under `heading`, up to the next heading of the same or higher level."""
    level = heading.split()[0]
    match = re.search(rf"^{re.escape(heading)}\s*$", text, re.MULTILINE)
    if not match:
        return ""
    rest = text[match.end() :]
    stop = re.search(rf"^#{{1,{len(level)}}} ", rest, re.MULTILINE)
    return rest[: stop.start()] if stop else rest


def test_every_page_has_a_design_and_a_realization():
    """Design is the stable half, Realization the volatile one; both must be there."""
    offenders = []
    for path in _pages():
        text = path.read_text(encoding="utf-8")
        missing = [s for s in REQUIRED_SECTIONS if not _has_heading(text, s)]
        if missing:
            offenders.append(f"{path.name} missing {missing}")
        elif text.index("\n## Design") > text.index("\n## Realization"):
            offenders.append(f"{path.name} puts Realization before Design")
    assert not offenders, (
        "Page(s) without the required shape. `## Design` holds `### Principles` "
        "and `### Invariants`; `## Realization` holds `### The parts` and "
        f"`### Change it here`, in that order: {offenders}"
    )


def test_every_principle_links_its_adr():
    """A principle with no ADR is an opinion; the ADR is where it was decided."""
    offenders = []
    for path in _pages():
        body = _section(path.read_text(encoding="utf-8"), "### Principles")
        for line in body.splitlines():
            if re.match(r"^\d+\. ", line) and not _ADR_LINK.search(line):
                offenders.append(f"{path.name}: {line[:60]}")
    assert not offenders, (
        "Principle(s) with no ADR link. End each numbered principle with "
        f"`→ [ADR-NNNN](../adr/adr-NNNN.md)`: {offenders}"
    )


def test_every_invariant_names_the_test_that_pins_it():
    """An invariant nobody tests is a hope; say which test holds it, or say it is unpinned."""
    offenders = []
    for path in _pages():
        body = _section(path.read_text(encoding="utf-8"), "### Invariants")
        rows = [r for r in body.splitlines() if r.startswith("|")][2:]
        if not rows:
            offenders.append(f"{path.name}: no invariants table")
        for row in rows:
            if "`test/" not in row and "unpinned" not in row:
                offenders.append(f"{path.name}: {row[:60]}")
    assert not offenders, (
        "Invariant row(s) with no pinning test. Put a "
        "`test/...::test_name` in the last column, or write **unpinned** so the "
        f"gap is visible: {offenders}"
    )


def test_design_names_no_private_symbol():
    """The design half must survive a refactor; a private name will not."""
    offenders = []
    for path in _pages():
        text = path.read_text(encoding="utf-8")
        design = _section(text, "## Design")
        for token in _TICK.findall(design):
            if token.startswith("test/"):
                continue
            if re.search(r"(?:^|[.\s])_[a-z]", token):
                offenders.append(f"{path.name}: `{token}`")
    assert not offenders, (
        "Private symbol(s) in a Design section. Name the public owner instead, "
        f"or move the detail to Realization: {offenders}"
    )


def _corpus() -> tuple[set[str], dict[Path, str]]:
    """Every word under `src/` and `test/`, and the text of each file by path."""
    texts = {
        path: path.read_text(encoding="utf-8", errors="ignore")
        for root in ("src", "test")
        for path in (REPO_ROOT / root).rglob("*.py")
    }
    words = set(re.findall(r"\w+", " ".join(texts.values())))
    return words, texts


def _references(path: Path) -> list[str]:
    return _TICK.findall(path.read_text(encoding="utf-8"))


def test_every_named_path_exists():
    """A path the reader cannot open is a broken promise."""
    _, texts = _corpus()
    offenders = []
    for path in _files():
        for token in _references(path):
            if not token.startswith(("src/", "test/")) or re.search(r"[{*<\s]", token):
                continue
            file_part, _, name = token.partition("::")
            target = REPO_ROOT / file_part.rstrip("/")
            if not target.exists():
                offenders.append(f"{path.name}: `{token}` (no such path)")
                continue
            if name:
                leaf = name.split("::")[-1]
                defined = re.search(
                    rf"^\s*(?:async )?(?:def|class) {re.escape(leaf)}\b",
                    texts.get(target, ""),
                    re.MULTILINE,
                )
                if not defined:
                    offenders.append(f"{path.name}: `{token}` (no {leaf} there)")
    assert not offenders, (
        "Page(s) naming a path or test that does not exist. Update the page "
        f"to the new location: {offenders}"
    )


def test_every_named_identifier_still_exists():
    """A renamed symbol leaves its old name nowhere in the code; the page must follow."""
    words, _ = _corpus()
    offenders = []
    for path in _files():
        for token in set(_references(path)):
            if not _IDENT.fullmatch(token):
                continue
            name = token.removesuffix("()")
            # Plain words (`Shell`, `READ`) cannot be told apart from English;
            # only names shaped like code are checked.
            if "_" not in name and "." not in name and not re.search(r"[a-z][A-Z]", name):
                continue
            missing = [part for part in name.split(".") if part and part not in words]
            if missing:
                offenders.append(f"{path.name}: `{token}`")
    assert not offenders, (
        "Page(s) naming an identifier that no longer appears under src/ or "
        f"test/. It was renamed or removed; update the page: {offenders}"
    )


def test_depth_follows_tier():
    """A page may not carry more diagrams than its tier allows."""
    offenders = []
    for path in _pages():
        text = path.read_text(encoding="utf-8")
        match = TIER_HEADER.search(text)
        assert match, f"{path.name} has no tier header"
        tier = int(match.group(1))
        count = len(_blocks(path))
        if count > TIER_DIAGRAM_BUDGET[tier]:
            offenders.append(
                f"{path.name} is Tier {tier} with {count} diagrams "
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
    for path in _pages():
        match = TIER_HEADER.search(path.read_text(encoding="utf-8"))
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
    for path in _files():
        for line, source in _blocks(path):
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
    for path in _files():
        for line, source in _blocks(path):
            count = len(_lifelines(source))
            if count > MAX_PARTICIPANTS:
                offenders.append(
                    f"{path.relative_to(REPO_ROOT).as_posix()}:{line} "
                    f"({count} lifelines)"
                )
    assert not offenders, (
        f"Sequence diagram(s) with more than {MAX_PARTICIPANTS} lifelines — draw "
        f"only the objects that exchange messages, and split the flow: {offenders}"
    )


def test_every_lifeline_names_a_real_symbol():
    """A lifeline is an object or callable, not a role-noun or a value type."""
    symbols = _symbols()
    words, _ = _corpus()
    offenders = []
    for path in _files():
        for line, source in _blocks(path):
            for label in _lifelines(source):
                if label in _BOUNDARY:
                    continue
                # A qualified third-party symbol (`pydantic_ai.Agent`) is fine
                # when zrb's code uses every part of it; a bare `Agent` is not,
                # because the reader cannot tell whose.
                if "." in label:
                    if all(part in words for part in label.split(".")):
                        continue
                    offenders.append(
                        f"{path.relative_to(REPO_ROOT).as_posix()}:{line} {label!r}"
                    )
                    continue
                # The label leads with the symbol; a trailing qualifier names
                # which instance it is (`BaseTask root`). Leading with a role
                # word is what makes a lifeline unopenable, so only the first
                # word is checked — otherwise `child UI` passes on `UI`.
                head = _WORD.sub("", label.split()[0])
                if head in symbols:
                    continue
                offenders.append(
                    f"{path.relative_to(REPO_ROOT).as_posix()}:{line} {label!r}"
                )
    assert not offenders, (
        "Lifeline(s) that name no real symbol. A participant must be a class or "
        "callable defined under src/ (a trailing instance qualifier is fine, so "
        "`BaseTask root` passes), or a third-party symbol qualified with its "
        f"module (`pydantic_ai.Agent`): {offenders}"
    )
