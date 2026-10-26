"""Bringing a journal written before the index was derived up to date.

Such a journal kept a note's pin and its one-line HUD summary only in the text of
`index.md`: a line `- 📌 text ([note](category/slug.md))` under a HUD heading. The
indexes are now rendered from each note's frontmatter, so those lines are read
once into the notes they link, and the render takes it from there.

A note is migrated exactly once: only a note without an `updated:` stamp is
adopted, and adopting stamps it. Every line that no adopted note accounts for
stays in the index as a foreign line (see `journal_index`), and the first line of
a note's own is the one adopted.
"""

from dataclasses import dataclass

from zrb.llm.tool.journal_index import (
    HUD_ORDER,
    PIN_MARKER,
    hud_owner,
    join_index_sections,
    split_index_sections,
)
from zrb.llm.tool.journal_note import Note

# Sections this version renamed, and what absorbed their lines. The lines are
# moved, never dropped: a heading change must not cost a journal what it held.
_HUD_RENAMES = (("Preferences", "User"), ("Active Constraints", "Recent"))


@dataclass(frozen=True)
class Adoption:
    """The HUD state an index line held for a note, to move into its frontmatter."""

    hud_line: str
    pinned: bool


def absorb_renamed_sections(text: str) -> str:
    """Move a renamed HUD section's lines into the section that absorbed them.

    `## Preferences` is now `## User` (it mixed what the user is like with the
    agent's own standing rules, so the heading claimed one owner and held two)
    and `## Active Constraints` is now `## Recent` (a rotating queue of newest
    headlines under a name that promised constraints). The lines are moved, in
    order, after what the target already held: a renamed heading must not cost
    the journal an entry. Running it twice changes nothing.
    """
    renamed, sections = split_index_sections(text)
    names = [name for name, _body in sections]
    if not any(old in names for old, _new in _HUD_RENAMES):
        return text
    targets = dict(_HUD_RENAMES)
    bodies: dict[str, list[str]] = {}
    order: list[str] = []
    for name, body in sections:
        target = targets.get(name, name)
        if target not in bodies:
            bodies[target] = []
            order.append(target)
        bodies[target].extend(line for line in body if line.strip())
    ordered = [name for name in HUD_ORDER if name in bodies]
    ordered += [name for name in order if name not in HUD_ORDER]
    return join_index_sections(renamed, [(name, bodies[name]) for name in ordered])


def plan_adoptions(text: str, notes: list[Note]) -> dict[str, Adoption]:
    """The HUD state to adopt, by note path, in the order the index lists it.

    Only a note that has no `updated:` stamp and no `hud_line` is a candidate,
    and only a HUD line whose trailing link names it. A note linked by several
    lines adopts the first; the rest are the same note's and render away."""
    candidates = {
        note.rel for note in notes if not note.is_migrated and not note.hud_line
    }
    adoptions: dict[str, Adoption] = {}
    if not candidates:
        return adoptions
    _, sections = split_index_sections(text)
    for name, body in sections:
        if name not in HUD_ORDER:
            continue
        for line in body:
            rel = hud_owner(line)
            if rel not in candidates or rel in adoptions:
                continue
            adoption = _read_line(line, rel)
            if adoption.hud_line:
                adoptions[rel] = adoption
    return adoptions


def _read_line(line: str, rel: str) -> Adoption:
    """The text and pin of a legacy HUD line: no bullet, marker or own link.

    An earlier version could write the note's own link twice, so it comes off
    until none is left; a link to another note stays, as part of the text."""
    text = line.strip().removeprefix("- ").strip()
    pinned = text.startswith(PIN_MARKER)
    text = text.removeprefix(PIN_MARKER).strip()
    own = f"([note]({rel}))"
    while text.endswith(own):
        text = text.removesuffix(own).rstrip()
    return Adoption(text, pinned)
