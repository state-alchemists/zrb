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

A target must also stay inside the checkout. A link that climbs out of it —
`../../../../etc/passwd`, or a path that leaves only through a symlink — names a
file this repository does not keep current, and a reader who cloned only this
repository cannot follow it, however the filesystem the check happens to run on
is laid out.

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
# Both sides of the containment check are resolved, so the comparison is between
# real paths and a link cannot slip outside through a symlink in the checkout.
_RESOLVED_ROOT = REPO_ROOT.resolve()

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

# A markdown inline link's opening, `](`. What follows is scanned rather than
# matched by one regex: a destination may carry an optional title
# (`[Architecture](README.md "The overview")`) and may be written `<a page.md>`,
# and neither a `[^)]+` nor a `[^ ]+` reads those correctly — the first swallows
# the title into the path, the second cannot hold a space.
_MD_LINK_OPEN = re.compile(r"\]\(")
# A target that is not a path in this repository: an external URL under any
# scheme, a jump within the page, or a placeholder a reader is meant to fill in.
# The scheme is read generally rather than as `https?://` — `ftp://`, `ssh://` and
# `file://` are no more this repository's to resolve — and the length floor after
# the first letter keeps a Windows drive (`C:\page.md`) looking like the path it is.
_NOT_A_PATH = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]+:|^#|[{*]")

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


# A fence opens with three or more backticks or tildes; the run that opens it sets
# the marker a matching run has to repeat. Toggling on `startswith("```")` reads a
# four-backtick fence that contains a three-backtick example as two fences, so the
# rest of the document counts as fenced and its links are never checked.
_FENCE_OPEN = re.compile(r"^\s*(`{3,}|~{3,})")
# A closing fence is its marker alone on the line, with no info string.
_FENCE_CLOSE = re.compile(r"^\s*(`{3,}|~{3,})\s*$")


def _outside_fences(text: str) -> str:
    """The doc with every fenced block dropped — see the module docstring."""
    kept: list[str] = []
    opening = ""
    for line in text.splitlines():
        if opening:
            closing = _FENCE_CLOSE.match(line)
            if closing and closing.group(1)[0] == opening[0]:
                if len(closing.group(1)) >= len(opening):
                    opening = ""
            continue
        fence = _FENCE_OPEN.match(line)
        if fence:
            opening = fence.group(1)
            continue
        kept.append(line)
    return "\n".join(kept)


def _link_targets(doc: Path) -> list[str]:
    """Every link target in the doc that claims to be a path in this repository."""
    return _link_targets_in(_outside_fences(doc.read_text(encoding="utf-8")))


def _link_targets_in(text: str) -> list[str]:
    """Every link target in a block of markdown that claims to be a repo path."""
    return [
        target
        for target in _link_destinations(text)
        if not _NOT_A_PATH.search(target)
    ]


def _link_destinations(text: str) -> list[str]:
    """Every inline link destination in `text`, its title dropped.

    `[Architecture](README.md "The overview")` points at `README.md`; taking the
    parenthesized text whole would look for a file named `README.md "The
    overview"`, and report a live link as a dead one.
    """
    destinations = []
    for opening in _MD_LINK_OPEN.finditer(text):
        inner = _parenthesized(text, opening.end())
        if inner is None:
            continue
        destination = _destination(inner)
        if destination:
            destinations.append(destination)
    return destinations


def _parenthesized(text: str, start: int) -> str | None:
    """The text inside the parentheses opening at `start`, or None if unclosed.

    Destinations may nest balanced parentheses, and neither an angle-bracket
    destination nor a quoted title may confuse the count — a title is free to
    contain a `)` of its own.
    """
    depth = 0
    in_angle = False
    quote = ""
    for index in range(start, len(text)):
        char = text[index]
        if in_angle:
            in_angle = char != ">"
        elif quote:
            quote = "" if char == quote else quote
        elif char in "\"'" and index > start and text[index - 1].isspace():
            quote = char
        elif char == "<":
            in_angle = True
        elif char == "(":
            depth += 1
        elif char == ")":
            if depth == 0:
                return text[start:index]
            depth -= 1
    return None


def _destination(inner: str) -> str:
    """A link's destination, with its optional title and angle brackets removed."""
    inner = inner.strip()
    if inner.startswith("<"):
        end = inner.find(">")
        if end != -1:
            return inner[1:end]
    return inner.split(maxsplit=1)[0] if inner.split() else ""


def _target_path(doc: Path, target: str) -> Path:
    """The absolute path a target names, with any `#fragment` dropped.

    Resolved, so a target that only leaves the checkout through a symlink is
    seen for what it is rather than followed.
    """
    return (doc.parent / target.split("#")[0]).resolve()


def _inside_repo(path: Path) -> bool:
    """Whether a path is the checkout itself or lives within it."""
    return path == _RESOLVED_ROOT or path.is_relative_to(_RESOLVED_ROOT)


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
            candidate = _target_path(doc, target)
            if not _inside_repo(candidate):
                offenders.append(f"{rel}: {target} (outside the repository)")
            elif not candidate.exists():
                offenders.append(f"{rel}: {target}")
    assert not offenders, (
        "Live doc(s) link to a file that does not exist — a moved or renamed "
        "page, swept in the code but not in the prose pointing at it — or to a "
        "path outside the repository, which a reader who cloned it cannot "
        f"follow: {offenders}"
    )


def test_a_link_that_leaves_the_checkout_is_drift(tmp_path):
    """A target outside the repo is drift, not a destination.

    The check resolves the target and requires it to stay inside the checkout, so
    an escaping link is caught even on a machine where that target happens to
    exist — otherwise `../../../../etc/passwd`, or a path through a symlink out
    of the tree, would pass wherever the filesystem could resolve it.
    """
    doc = REPO_ROOT / "docs" / "architecture" / "README.md"
    # A relative climb out of the checkout.
    assert not _inside_repo(_target_path(doc, "../../../../etc/passwd"))
    # An existing file outside the checkout is still not a repo link.
    outside = tmp_path / "outside.md"
    outside.write_text("not ours\n", encoding="utf-8")
    assert not _inside_repo(_target_path(doc, str(outside)))
    # And an ordinary relative link still resolves inside the checkout.
    assert _inside_repo(_target_path(doc, "../adr/adr-0041.md"))


def test_a_link_title_is_not_read_as_part_of_the_path():
    """A destination is read up to its optional title.

    `[Architecture](README.md "The overview")` points at `README.md`. Taking the
    parenthesized text whole looks for a file named `README.md "The overview"`,
    which never exists, so a valid link would be reported as a dead one — a false
    positive that costs more than the miss.
    """
    assert _link_targets_in('[Architecture](README.md "The overview")') == ["README.md"]
    assert _link_targets_in("[Architecture](README.md 'The overview')") == ["README.md"]


def test_a_link_written_in_angle_brackets_is_still_checked():
    """`[x](<a page.md>)` is a repository path spelled to hold a space.

    Angle brackets used to exempt the target from the check, so a dead link
    written this way was not resolved at all and passed silently.
    """
    assert _link_targets_in("[x](<missing page.md>)") == ["missing page.md"]
    assert _link_targets_in("[x](<../adr/adr-0041.md>)") == ["../adr/adr-0041.md"]


def test_a_link_under_any_scheme_is_not_read_as_a_repository_path():
    """`ftp://`, `ssh://` and `file://` are no more ours to resolve than `https://`.

    Exempting only `https?://` and `mailto:` left every other scheme to be treated
    as a path relative to the document, so an external link was reported as a
    missing repository file — a false positive on a link this guard has no business
    resolving. A relative path is still a path, and a Windows drive is a path too.
    """
    for target in ("ftp://example.com/x.md", "ssh://host/x.md", "file:///x.md"):
        assert _link_targets_in(f"[x]({target})") == []
    assert _link_targets_in("[x](../adr/adr-0041.md)") == ["../adr/adr-0041.md"]
    assert _link_targets_in(r"[x](C:\page.md)") == [r"C:\page.md"]


def test_a_fence_is_closed_by_its_own_marker_only():
    """A fence ends at its own marker, not at any line that starts with ```.

    Counting every ``` line as a toggle loses the thread as soon as the content
    uses another fence character, or an odd number of ``` lines — the rest of the
    document then reads as fenced and its links are never checked, which is how a
    dead link after an example passes silently.
    """
    tildes = "~~~\n```\n~~~\n[dead](missing.md)\n"
    assert "[dead](missing.md)" in _outside_fences(tildes)
    odd = "````text\n```bash\necho hi\n````\n[dead](missing.md)\n"
    assert "[dead](missing.md)" in _outside_fences(odd)
    # A four-backtick fence still drops its own content, inner example and all.
    nested = _outside_fences("````text\n```\ninside\n```\n````\n[dead](missing.md)\n")
    assert "inside" not in nested and "[dead](missing.md)" in nested
    # And the ordinary case is still dropped.
    assert "[dead](missing.md)" not in _outside_fences("```\n[dead](missing.md)\n```\n")
