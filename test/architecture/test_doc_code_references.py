"""Guards live docs against citing code, or linking to a file, that is gone.

An audit found 8 dead `.py` references across `AGENTS.md` and the ADR log,
plus one dead directory in `AGENTS.md`'s orientation table (`llm/app/`,
which had moved to `llm/ui/default/app/`). Every one of them was a rename
or a test-file split that swept the source but not the prose pointing at
it. AGENTS.md is the first file a contributor or an agent reads, and an
ADR's "Where it lives" line is the only index from a decision back to the
code implementing it — a stale path there sends the reader somewhere that
does not exist, which is worse than no pointer at all.

A markdown link is the same promise in a different notation — the reader
clicks it — so a link's target is checked too. That covers the ADR links every
architecture principle ends with, which the shape guard can only recognize by
their spelling: `(../../adr/adr-0041.md)` is the right shape whether or not
`adr-0041.md` exists, and this is what tells the two apart.

Links inside a fenced block are exempt: a fence shows what zrb or a user writes
— the generated journal index, a sample task file — so its links belong to the
example, not to this repository.

Changelogs are excluded: they are frozen history, and a path that was
correct at the time of the entry stays correct as a record of what
happened, even after the file moves.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]

# A backticked token containing a "/" and ending in ".py" — the shape both
# AGENTS.md's tables and the ADRs' "Where it lives" lines use.
_PY_REF = re.compile(r"`([\w][\w/.\-]*/[\w_\-]+\.py)`")
# A backticked path ending in "/" that names a directory inside src/zrb.
_DIR_REF = re.compile(r"`((?:src/zrb|zrb|llm)/[\w/]+/)`")

# Paths that are not this repo's to keep current: third-party module paths
# cited to explain *their* behavior (pydantic-ai's `models/openai.py`, rich's
# `markdown.py`), and the placeholder paths guides use in examples.
_NOT_OURS = re.compile(r"^(rich|parser|models)/|^(X|acme\w*|your_\w*)/|path/to|[<>*]")

# (doc, cited path) -> why this dead path is correct as written. A path a
# record cites *as history* — the location a thing used to live at, in the
# sentence explaining that it moved — is not drift; rewriting it to the new
# path would make the sentence say the opposite of what happened.
REFERENCE_EXCEPTIONS: dict[str, set[str]] = {
    "docs/adr/adr-0088.md": {
        # The Context and Decision paragraphs name both modules at their
        # pre-move locations, which is the whole subject of the record. The
        # post-move names are in "Where it lives" and are checked normally.
        "agent/run/runtime_state.py",
        "agent/tool_result.py",
    },
}

# A markdown inline link, captured by its target.
_MD_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
# A target that is not a path in this repository: an external URL, a jump within
# the page, or a placeholder a reader is meant to fill in.
_NOT_A_PATH = re.compile(r"^(?:https?://|mailto:|#)|[{*<>]")

# (doc, link target) -> why this dead target is correct as written.
LINK_EXCEPTIONS: dict[str, set[str]] = {
    "docs/adr/adr-0055.md": {
        # The sentence describes how a journal note registers itself, spelling
        # the link as ` ([note](path))`, so the target is deliberately not a
        # file — it is the format, not a destination.
        "path",
    },
}


def _live_docs() -> list[Path]:
    docs = [p for p in (REPO_ROOT / "docs").rglob("*.md") if "changelog" not in p.parts]
    return [REPO_ROOT / "AGENTS.md", *sorted(docs)]


def _known_paths() -> set[str]:
    """Every repo file, indexed by each of its path suffixes.

    A doc may cite `agent/run/runner.py` or the full
    `src/zrb/llm/agent/run/runner.py`; both should resolve.
    """
    known: set[str] = set()
    for path in REPO_ROOT.rglob("*.py"):
        rel = path.relative_to(REPO_ROOT)
        if ".venv" in rel.parts or "__pycache__" in rel.parts:
            continue
        parts = rel.parts
        for i in range(len(parts)):
            known.add("/".join(parts[i:]))
    return known


def _known_dirs() -> set[str]:
    known: set[str] = set()
    for path in (REPO_ROOT / "src").rglob("*"):
        if not path.is_dir() or "__pycache__" in path.parts:
            continue
        parts = path.relative_to(REPO_ROOT).parts
        for i in range(len(parts)):
            known.add("/".join(parts[i:]) + "/")
    return known


def test_live_docs_do_not_cite_a_module_that_no_longer_exists():
    known = _known_paths()
    dead = [
        f"{doc.relative_to(REPO_ROOT)}: {ref}"
        for doc in _live_docs()
        for ref in _PY_REF.findall(doc.read_text(encoding="utf-8"))
        if not _NOT_OURS.search(ref)
        and ref not in known
        and ref
        not in REFERENCE_EXCEPTIONS.get(doc.relative_to(REPO_ROOT).as_posix(), set())
    ]
    assert not dead, (
        "Live doc(s) cite a module that does not exist — a rename or a test "
        f"split swept the code but not the prose: {dead}"
    )


def test_live_docs_do_not_cite_a_package_that_no_longer_exists():
    known = _known_dirs()
    dead = [
        f"{doc.relative_to(REPO_ROOT)}: {ref}"
        for doc in _live_docs()
        for ref in _DIR_REF.findall(doc.read_text(encoding="utf-8"))
        if ref not in known
    ]
    assert not dead, f"Live doc(s) cite a package directory that does not exist: {dead}"


def _outside_fences(text: str) -> str:
    """The doc with every fenced block dropped — see the module docstring."""
    kept: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            kept.append(line)
    return "\n".join(kept)


def _link_targets(doc: Path) -> list[str]:
    """Every link target in the doc that claims to be a path in this repository."""
    return [
        target
        for target in _MD_LINK.findall(_outside_fences(doc.read_text(encoding="utf-8")))
        if not _NOT_A_PATH.search(target)
    ]


def test_live_docs_do_not_link_to_a_file_that_is_gone():
    """A dead link costs the reader a round trip to nowhere.

    The architecture section's cross-references, its guides and every ADR link a
    principle ends with are relative links, so a moved page leaves each page that
    pointed at it still looking correct. Only resolving the target can see that.
    """
    offenders = []
    for doc in _live_docs():
        rel = doc.relative_to(REPO_ROOT).as_posix()
        exempt = LINK_EXCEPTIONS.get(rel, set())
        for target in _link_targets(doc):
            if target in exempt:
                continue
            if not (doc.parent / target.split("#")[0]).exists():
                offenders.append(f"{rel}: {target}")
    assert not offenders, (
        "Live doc(s) link to a file that does not exist — a moved or renamed "
        f"page, swept in the code but not in the prose pointing at it: {offenders}"
    )
