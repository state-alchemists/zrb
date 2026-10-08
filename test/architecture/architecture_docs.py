"""The architecture section, as its guards see it.

Three guards read `docs/architecture/`: `test_architecture_docs.py` holds the
shape, `test_architecture_doc_symbols.py` holds the truth check, and
`test_doc_code_references.py` holds the paths and links a page cites. They must
agree on what a page is, where a tier lives and what counts as a diagram block —
two copies of the fence regex would eventually disagree about what a diagram is —
so that shared reading lives here once.

Nothing here asserts. These are the accessors; the rules and their reasons are
in the guard that applies them.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
ARCHITECTURE = REPO_ROOT / "docs" / "architecture"
INDEX = ARCHITECTURE / "README.md"

# Navigation, not content: how you find a page, rather than a page about a
# subsystem. `README.md` is the tier index; `change-map.md` routes an intent to
# the file that decides it. Neither owns a flow, so neither declares a tier.
NAVIGATION = {"README.md", "change-map.md"}

# Each tier is a directory, numbered so a listing reads in tier order.
TIER_DIRS = {
    "0-system": 0,
    "1-spine": 1,
    "2-extension-surface": 2,
    "3-peripheral-flow": 3,
}

_FENCE = re.compile(r"^\s*```mermaid\n(.*?)^\s*```", re.DOTALL | re.MULTILINE)
_PARTICIPANT = re.compile(r"^\s*participant \w+ as (.+?)\s*$", re.MULTILINE)
_TICK = re.compile(r"`([^`\n]+)`")


def pages() -> list[Path]:
    """The tiered content pages — everything except the two navigation files."""
    return sorted(p for d in TIER_DIRS for p in (ARCHITECTURE / d).glob("*.md"))


def files() -> list[Path]:
    """Every markdown file in the section, navigation included."""
    return sorted(ARCHITECTURE.rglob("*.md"))


def name_of(path: Path) -> str:
    """A page's name as a reader would write it, relative to the section root."""
    return path.relative_to(ARCHITECTURE).as_posix()


def ticks_in(text: str) -> list[str]:
    """Every backticked token in a block of markdown."""
    return _TICK.findall(text)


def ticked(path: Path) -> list[str]:
    """Every backticked token in the page."""
    return ticks_in(path.read_text(encoding="utf-8"))


def has_heading(text: str, heading: str) -> bool:
    """Whether `heading` appears as a heading line, not as a link in the TOC."""
    return re.search(rf"^{re.escape(heading)}\s*$", text, re.MULTILINE) is not None


def position(text: str, heading: str) -> int:
    """Where `heading`'s line starts, or -1 when the page has no such heading."""
    match = re.search(rf"^{re.escape(heading)}\s*$", text, re.MULTILINE)
    return match.start() if match else -1


def section(text: str, heading: str) -> str:
    """The body under `heading`, up to the next heading of the same or higher level."""
    level = heading.split()[0]
    match = re.search(rf"^{re.escape(heading)}\s*$", text, re.MULTILINE)
    if not match:
        return ""
    rest = text[match.end() :]
    stop = re.search(rf"^#{{1,{len(level)}}} ", rest, re.MULTILINE)
    return rest[: stop.start()] if stop else rest


def rows_in(body: str) -> list[list[str]]:
    """The data rows of a markdown table body, header and separator dropped."""
    lines = [line for line in body.splitlines() if line.startswith("|")]
    return [
        [cell.strip() for cell in line.strip("|").split("|")] for line in lines[2:]
    ]


def blocks(path: Path) -> list[tuple[int, str]]:
    """Every mermaid block as (line of first content, source)."""
    text = path.read_text(encoding="utf-8")
    return [
        (text[: match.start(1)].count("\n") + 1, match.group(1))
        for match in _FENCE.finditer(text)
    ]


def lifelines(source: str) -> list[str]:
    """The participant labels of a sequence diagram, in the order they appear."""
    return [label.strip() for label in _PARTICIPANT.findall(source)]
