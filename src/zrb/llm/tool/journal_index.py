"""The journal's indexes, rendered from its notes.

`index.md` (the injected HUD sections, the `## Recent Insights` catalog, the
`## Directories` links) and every category index are a *view*: each line a note
accounts for is derived from that note's frontmatter (`journal_note.Note`), and
a write, supersede, delete or refile changes the note and then renders again.
Rendering the same notes twice yields the same bytes.

**Foreign lines.** A line in a generated region that no note accounts for is a
hand edit. It is carried through unchanged and in place, is never evicted by the
section cap, and does not count toward it. Ownership is decided by the note link
a line already carries, which adds nothing to the injected text:

- a HUD line (`- 📌 text ([note](category/slug.md))`) belongs to the note its
  trailing `([note](…))` names, provided that note has a `hud_line`;
- a `## Recent Insights` or category-index line (`- [title](path)`) belongs to the
  note whose file it links.

Every other line is foreign. The failure modes are the other side of that rule:
a hand edit to the *text* of an owned line is reverted at the next render (the
line's text is the note's `hud_line`, so edit that), a hand-written line that
ends in a link to a note that has a line is claimed by that note, and a note's
file edited so that its link no longer matches orphans the old line as a foreign
one. No state outside the notes and the index is needed.

Pure: strings in, strings out. No `CFG`, no I/O, so a caller owns both.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from zrb.llm.tool.journal_note import NOTE_CATEGORIES, Note

ACTIVITY_DIR = "activity-log"
# What makes a HUD line survive the section's cap. It is a visible marker in the
# rendered line because the line is all the model sees of the pin.
PIN_MARKER = "📌 "
CONSTRAINTS_SECTION = "Constraints"
# Which HUD section a note's one-line summary lands in. Two sections are split
# by owner — what the user is like, and who the agent is — so a preference the
# agent holds for itself is not filed beside the user's own. The other two are
# split by firmness: a constraint holds every turn, a headline may age out.
_HUD_SECTION = {
    "user": "User",
    "preferences": "User",
    "agent": "Agent",
    "projects": "Recent",
    "technical": "Recent",
}
# Their order in the index. The snapshot is capped and overflows from the end, so
# the durable sections come first; a journal written before a section existed is
# migrated into this order rather than appended after the unbounded one.
HUD_ORDER = ("User", CONSTRAINTS_SECTION, "Agent", "Recent")
DIRECTORIES_HEADING = "## Directories"
CATALOG_HEADING = "## Recent Insights"

_NOTE_LINK_RE = re.compile(r"\(\[note\]\(([^)]*)\)\)\s*$")
_BARE_LINK_RE = re.compile(r"^- \[.*\]\(([^)]+)\)\s*$")
_OLDER_NOTES_RE = re.compile(r"^- _\d+ older notes?: see each category's index_\s*$")
# A HUD line longer than this is still written; the tool result asks the model to
# shorten it, because the injected snapshot spends its budget on these lines.
HUD_LINE_SOFT_LIMIT = 160


@dataclass(frozen=True)
class HudSection:
    """What one HUD section shows and what its cap left out.

    *kept* is newest first, the order the section renders in, so the injected
    snapshot, which is cut from the end, loses the oldest lines. *evicted* is
    oldest first, the order the cap dropped them in."""

    kept: list[str]
    evicted: list[str]


def hud_section_for(category: str, pinned: bool) -> str:
    """Which HUD section this note's line belongs in.

    The category decides, and firmness refines it: a pinned line on a
    `projects` or `technical` note is a constraint that has to keep holding, so
    it goes to `## Constraints` rather than the rotating `## Recent`. Pinning a
    `user`, `preferences` or `agent` line keeps it in its own section, because a
    pinned identity is still an identity, not a constraint."""
    if pinned and category in ("projects", "technical"):
        return CONSTRAINTS_SECTION
    return _HUD_SECTION[category]


def hud_line_of(note: Note) -> str:
    """The HUD line this note renders: bullet, pin marker, text, link to itself."""
    pin = PIN_MARKER if note.pinned else ""
    return f"- {pin}{note.hud_line} ([note]({note.rel}))"


def plan_hud(notes: list[Note], cap: int) -> dict[str, HudSection]:
    """Each HUD section's lines from the active notes that have a `hud_line`.

    *notes* is oldest first, which is the order eviction follows. The cap is
    `<= 0` for none. A section keeps its newest *cap* lines, sparing a pinned line
    until every line in the section is pinned, and lists them newest first."""
    entries: dict[str, list[Note]] = {name: [] for name in HUD_ORDER}
    for note in notes:
        if note.is_active and note.hud_line:
            entries[hud_section_for(note.category, note.pinned)].append(note)
    return {name: _cap_entries(group, cap) for name, group in entries.items()}


def _cap_entries(entries: list[Note], cap: int) -> HudSection:
    """Drop the oldest unpinned entries down to *cap*, returning kept and dropped.

    A pinned entry goes only when every entry in the section is pinned, so a
    section of pinned constraints may stay over the cap rather than lose one."""
    over = len(entries) - cap
    if cap <= 0 or over <= 0:
        return HudSection([hud_line_of(note) for note in reversed(entries)], [])
    if all(note.pinned for note in entries):
        dropped = set(range(over))
    else:
        evictable = [index for index, note in enumerate(entries) if not note.pinned]
        dropped = set(evictable[:over])
    return HudSection(
        [
            hud_line_of(n)
            for i, n in reversed(list(enumerate(entries)))
            if i not in dropped
        ],
        [hud_line_of(n) for i, n in enumerate(entries) if i in dropped],
    )


def render_root_index(
    text: str, notes: list[Note], cap: int, index_name: str, catalog_cap: int
) -> str:
    """The root index with every generated region rendered from *notes*.

    *cap* is the per-section HUD cap and *catalog_cap* the number of notes the
    `## Recent Insights` catalog lists (`<= 0` for all of them).

    Missing HUD sections and category links are added where they belong; the
    HUD sections and the catalog take their owned lines from the notes; anything
    else — the title, other headings, foreign lines — passes through."""
    text = ensure_directory_links(ensure_hud_sections(text), index_name)
    preamble, sections = split_index_sections(text)
    plan = plan_hud(notes, cap)
    hud_rels = {note.rel for note in notes if note.hud_line}
    note_rels = {note.rel for note in notes}
    catalog = plan_catalog(notes, catalog_cap)
    seen: set[str] = set()
    rendered: list[tuple[str, list[str]]] = []
    for name, body in sections:
        first = name not in seen
        seen.add(name)
        if name in plan:
            generated = plan[name].kept if first else []
            body = _splice(body, lambda line: hud_owner(line) in hud_rels, generated)
        elif f"## {name}" == CATALOG_HEADING:
            generated = catalog if first else []
            body = _splice(
                body, lambda line: is_catalog_line(line, note_rels), generated
            )
        rendered.append((name, body))
    return join_index_sections(preamble, rendered)


def plan_catalog(notes: list[Note], cap: int) -> list[str]:
    """The `## Recent Insights` lines: the newest *cap* active notes, newest
    first, then one line counting the older ones the category indexes still list.
    *notes* is oldest first; `cap <= 0` lists every active note."""
    active = [note for note in reversed(notes) if note.is_active]
    shown = active if cap <= 0 else active[:cap]
    lines = [catalog_line(note) for note in shown]
    older = len(active) - len(shown)
    if older:
        noun = "note" if older == 1 else "notes"
        lines.append(f"- _{older} older {noun}: see each category's index_")
    return lines


def is_catalog_line(line: str, note_rels: set[str]) -> bool:
    """Whether the renderer owns this `## Recent Insights` line."""
    return bare_target(line) in note_rels or bool(_OLDER_NOTES_RE.match(line))


def render_category_index(text: str, notes: list[Note], category: str) -> str:
    """A category's index with a link to each of its notes, superseded ones
    included: the note still exists, and the index is how it is found."""
    mine = [note for note in notes if note.category == category]
    targets = {f"{note.slug}.md" for note in mine}
    lines = _splice(
        text.splitlines(),
        lambda line: bare_target(line) in targets,
        [category_line(note) for note in mine],
    )
    return "\n".join(lines).rstrip("\n") + "\n" if lines else text


def catalog_line(note: Note) -> str:
    """The `## Recent Insights` line of a note: a label and a root-relative link."""
    return f"- [{note.title}]({note.rel})"


def category_line(note: Note) -> str:
    return f"- [{note.title}]({note.slug}.md)"


def hud_owner(line: str) -> str | None:
    """The path a HUD line's trailing `([note](…))` names, if it has one."""
    match = _NOTE_LINK_RE.search(line)
    return match.group(1) if match else None


def bare_target(line: str) -> str | None:
    """The link target of a `- [label](target)` line, if that is all it is."""
    match = _BARE_LINK_RE.match(line)
    return match.group(1) if match else None


def hud_lines_of(text: str, rel: str) -> list[str]:
    """The lines under the HUD headings of *text* that name *rel* as their note."""
    _, sections = split_index_sections(text)
    return [
        line
        for name, body in sections
        if name in HUD_ORDER
        for line in body
        if hud_owner(line) == rel
    ]


def _splice(
    body: list[str], is_owned: Callable[[str], bool], generated: list[str]
) -> list[str]:
    """*body* with its owned lines replaced by *generated*.

    Each owned line is a slot that the next generated line fills, so a foreign
    line keeps its exact place between its neighbours; generated lines beyond
    the slots follow the last one (or the end of the body when there was none),
    and a slot with nothing left to fill disappears."""
    pending = list(generated)
    result: list[str] = []
    after_last_slot: int | None = None
    for line in _trim_blank_edges(body):
        if not is_owned(line):
            result.append(line)
        elif pending:
            result.append(pending.pop(0))
            after_last_slot = len(result)
    if pending and after_last_slot is not None:
        result[after_last_slot:after_last_slot] = pending
    elif pending:
        if result and result[-1].strip() and not result[-1].startswith("- "):
            result.append("")
        result.extend(pending)
    return _collapse_blank_runs(result)


def _trim_blank_edges(lines: list[str]) -> list[str]:
    start, end = 0, len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return lines[start:end]


def _collapse_blank_runs(lines: list[str]) -> list[str]:
    result: list[str] = []
    for line in lines:
        if not line.strip() and result and not result[-1].strip():
            continue
        result.append(line)
    return _trim_blank_edges(result)


def split_index_sections(text: str) -> "tuple[list[str], list[tuple[str, list[str]]]]":
    """The lines before the first `## ` heading, then each heading and its body."""
    preamble: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        if line.startswith("## "):
            sections.append((line[3:].strip(), []))
        elif sections:
            sections[-1][1].append(line)
        else:
            preamble.append(line)
    return preamble, sections


def join_index_sections(
    preamble: list[str], sections: "list[tuple[str, list[str]]]"
) -> str:
    """Render an index in the shape `root_index_skeleton` writes."""
    parts = ["\n".join(preamble).rstrip("\n"), "\n"]
    for name, body in sections:
        content = "\n".join(body).strip("\n")
        parts.append(f"\n## {name}\n")
        if content:
            parts.append(f"\n{content}\n")
    return "".join(parts)


def root_index_skeleton(index_name: str) -> str:
    directories = " · ".join(
        f"[{name}]({name}/{index_name})" for name in (*NOTE_CATEGORIES, ACTIVITY_DIR)
    )
    # Order is load-bearing: the injected snapshot is capped and overflows from
    # the end, so the unbounded section goes last and evicts only itself.
    sections = "".join(f"## {name}\n\n" for name in HUD_ORDER)
    return (
        "# Journal\n\n"
        f"{sections}"
        f"{DIRECTORIES_HEADING}\n\n- {directories}\n\n"
        f"{CATALOG_HEADING}\n"
    )


def ensure_hud_sections(text: str) -> str:
    """Add any HUD section this index predates, at its place in `HUD_ORDER`.

    A journal created before a category existed keeps its old skeleton, and
    appending the new heading at the end would put it after `## Recent Insights`,
    where the capped snapshot evicts it first.
    """
    for name in HUD_ORDER:
        if f"## {name}" not in text.splitlines():
            text = _insert_section_in_order(text, name)
    return text


def _insert_section_in_order(text: str, name: str) -> str:
    """Insert an empty ``## name`` before the next heading that must follow it."""
    heading = f"## {name}"
    later = [f"## {other}" for other in HUD_ORDER]
    later += [DIRECTORIES_HEADING, CATALOG_HEADING]
    stop = later[later.index(heading) + 1 :] if heading in later else later
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line in stop:
            head = lines[:index]
            if head and head[-1].strip():
                head = [*head, ""]
            return "\n".join([*head, heading, "", *lines[index:]])
    return f"{text.rstrip()}\n\n{heading}\n"


def ensure_directory_links(text: str, index_name: str) -> str:
    """Add any category link the `## Directories` line predates, in its order.

    The link is what makes a category reachable from the injected root index, so
    a migrated journal that gains `## Agent` but not the `agent` link in `##
    Directories` hides every agent note behind an index nobody links to. A
    missing link is inserted where `NOTE_CATEGORIES` puts it; every line is
    otherwise left untouched, so a hand-written label (`[My notes](user/…)`) or a
    link to something zrb does not own survives, where rebuilding the line from
    the canonical names would have dropped both.
    """
    expected = [*NOTE_CATEGORIES, ACTIVITY_DIR]
    link_re = _directory_link_re(index_name)
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() != DIRECTORIES_HEADING:
            continue
        bullet_at = next(
            (at for at in range(index + 1, len(lines)) if lines[at].startswith("- ")),
            None,
        )
        if bullet_at is None:
            # A heading with no list under it is not a shape this writer makes;
            # leave it rather than inventing a line above someone's own text.
            return text
        linked = [match.group(2) for match in link_re.finditer(lines[bullet_at])]
        missing = [name for name in expected if name not in linked]
        if not missing:
            return text
        rewritten = lines[bullet_at]
        for name in missing:
            rewritten = _insert_directory_link(rewritten, name, expected, index_name)
        lines[bullet_at] = rewritten
        rebuilt = "\n".join(lines)
        return rebuilt + "\n" if text.endswith("\n") else rebuilt
    return text


def _insert_directory_link(
    line: str, name: str, expected: list[str], index_name: str
) -> str:
    """Add the category's index link before the first link that must follow it."""
    token = f"[{name}]({name}/{index_name})"
    for match in _directory_link_re(index_name).finditer(line):
        target = match.group(2)
        if target not in expected:
            continue
        if expected.index(target) > expected.index(name):
            return f"{line[: match.start()]}{token} · {line[match.start() :]}"
    if line.strip() == "-":
        return f"- {token}"
    return f"{line} · {token}"


def _directory_link_re(index_name: str) -> re.Pattern[str]:
    """`[label](<category>/<index file>)`, the links `## Directories` carries."""
    return re.compile(rf"\[([^\]]*)\]\(([^)]*)/{re.escape(index_name)}\)")


def with_link(text: str, rel_target: str, label: str) -> str:
    """*text* with `- [label](rel_target)` appended to a plain list index.

    For the activity log's year/month indexes, which list directories and day
    files rather than notes. An existing entry for the target is relabelled in
    place; duplicates are dropped.
    """
    entry = f"- [{label}]({rel_target})"
    same_target = re.compile(rf"- \[.*\]\({re.escape(rel_target)}\)")
    kept: list[str] = []
    found = False
    for line in text.splitlines():
        if same_target.fullmatch(line):
            if not found:
                kept.append(entry)
                found = True
            continue
        kept.append(line)
    if found:
        return "\n".join(kept) + "\n"
    body = text.rstrip()
    gap = "\n" if body.rsplit("\n", 1)[-1].startswith("- ") else "\n\n"
    return f"{body}{gap}{entry}\n"


def normalize_hud_line(line: str, note_rel: str, notes: list[Note]) -> str:
    """The `hud_line` to store for what a caller passed, on one line.

    No bullet, no pin marker (whether it is pinned is the caller's `pinned`, not
    text it may have echoed back from the index), and no link to this note: the
    index adds that. A link to *another* note is kept when the caller wrote it
    ("See also …"); it is dropped only when the text is an echo, which the notes
    decide — text that reproduces another note's line, link included, is a line
    read back from the index, and keeping its link would point this note at that
    one."""
    text = line.strip().removeprefix("- ").strip()
    text = text.removeprefix(PIN_MARKER).strip()
    own = f"([note]({note_rel}))"
    while text.endswith(own):
        text = text.removesuffix(own).rstrip()
    if _is_echo(text, notes):
        text = strip_note_links(text)
    return " ".join(text.split())


def strip_note_links(text: str) -> str:
    """*text* without any trailing `([note](…))` links."""
    while True:
        match = _NOTE_LINK_RE.search(text)
        if not match:
            return text.rstrip()
        text = text[: match.start()].rstrip()


def _is_echo(text: str, notes: list[Note]) -> bool:
    match = _NOTE_LINK_RE.search(text)
    if not match:
        return False
    prose = text[: match.start()].rstrip()
    return any(
        note.rel == match.group(1) and strip_note_links(note.hud_line) == prose
        for note in notes
    )
