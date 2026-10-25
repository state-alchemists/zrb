"""A journal note as data: its frontmatter is the one source of truth.

Everything the injected index shows about a note is a field here — whether it is
active (`status`, `applies_when`), the one line that represents it (`hud_line`),
whether that line is pinned (`pinned`), and where it ranks (`updated`). The
indexes are rendered from these fields by `journal_index`, never edited as text,
so a note and its index entries cannot disagree.

This module is pure: it reads files but never writes one. A caller that has to
write (`journal_write`) does so itself, because only it knows the open
transaction's snapshot.
"""

import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from zrb.util.markdown import get_first_heading

NOTE_CATEGORIES = ("user", "agent", "preferences", "projects", "technical")
HISTORY_HEADING = "## History"
BACKLINKS_HEADING = "## Backlinks"
HISTORY_MAX_ENTRIES = 3
STATUS_ACTIVE = "active"
STATUS_SUPERSEDED = "superseded"
# A note's frontmatter says when it stops applying, and whether it already has.
# The condition is the half of a finding that lets a later session retire it
# instead of re-reading it: "safe to delete" is a claim somebody has to be able
# to check, and a finding whose expiry nobody wrote down is a finding nobody can
# retire.
NO_APPLIES_WHEN = "not stated"
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_FRONTMATTER_FENCE = "---"


@dataclass(frozen=True)
class Note:
    """One note, as its frontmatter and heading describe it."""

    category: str
    slug: str
    title: str
    status: str
    hud_line: str
    pinned: bool
    updated: datetime
    has_stamp: bool

    @property
    def rel(self) -> str:
        """Journal-root-relative path, with `/` separators."""
        return f"{self.category}/{self.slug}.md"

    @property
    def is_active(self) -> bool:
        return self.status != STATUS_SUPERSEDED

    @property
    def is_migrated(self) -> bool:
        """Whether a version that keeps the index derived has written this note.

        Only such a note carries an `updated:` stamp; one that lacks it was
        written when the index was the only place a pin lived."""
        return self.has_stamp


def check_category(category: str) -> None:
    if category not in NOTE_CATEGORIES:
        raise ValueError(
            f"[SYSTEM SUGGESTION]: unknown category {category!r}. "
            f"Use one of: {', '.join(NOTE_CATEGORIES)}."
        )


def check_slug(slug: str) -> None:
    """Refuse anything that is not kebab-case.

    A slug is interpolated into a path, so `../index` is not a name this journal
    has: joining it lands on the root index, and the tool would then write
    frontmatter into a file it never meant to touch. Categories are a fixed list
    but a slug is free text, so this is the boundary that has to hold.
    """
    if not _SLUG_RE.match(slug):
        raise ValueError(
            f"[SYSTEM SUGGESTION]: slug {slug!r} must be kebab-case "
            "(lowercase letters, digits, single hyphens)."
        )


def read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def one_line(text: str) -> str:
    """*text* on one line, so a value can never open a second frontmatter key."""
    return " ".join(text.split())


def parse_frontmatter(text: str) -> dict[str, str]:
    """The `key: value` pairs of the leading `---` block, or `{}` without one."""
    lines = text.splitlines()
    end = _frontmatter_end(lines)
    if end is None:
        return {}
    values: dict[str, str] = {}
    for line in lines[1:end]:
        key, separator, value = line.partition(":")
        if separator:
            values[key.strip()] = value.strip()
    return values


def set_frontmatter(text: str, updates: dict[str, str | None]) -> str:
    """*text* with each key in *updates* set (replaced in place, else appended)
    in its frontmatter; a `None` value removes the key. Creates the block when
    the text has none."""
    lines = text.splitlines()
    end = _frontmatter_end(lines)
    if end is None:
        block = [f"{key}: {value}" for key, value in updates.items() if value]
        return "\n".join([_FRONTMATTER_FENCE, *block, _FRONTMATTER_FENCE, *lines]) + (
            "\n"
        )
    pending = dict(updates)
    head: list[str] = []
    for line in lines[1:end]:
        key = line.partition(":")[0].strip()
        if key not in pending:
            head.append(line)
            continue
        value = pending.pop(key)
        if value is not None:
            head.append(f"{key}: {value}")
    head += [f"{key}: {value}" for key, value in pending.items() if value is not None]
    rebuilt = [_FRONTMATTER_FENCE, *head, _FRONTMATTER_FENCE, *lines[end + 1 :]]
    return "\n".join(rebuilt) + "\n"


def _frontmatter_end(lines: list[str]) -> int | None:
    """Index of the closing fence of a leading frontmatter block, if any."""
    if not lines or lines[0].strip() != _FRONTMATTER_FENCE:
        return None
    for index in range(1, len(lines)):
        if lines[index].strip() == _FRONTMATTER_FENCE:
            return index
    return None


def format_stamp(moment: datetime) -> str:
    return moment.isoformat(timespec="microseconds")


def next_stamp(notes: list[Note], now: datetime) -> datetime:
    """A moment later than every note's, so the newest write ranks newest even
    when the clock is coarse or the machine's time went backwards."""
    latest = max((note.updated for note in notes if note.has_stamp), default=None)
    if latest is None or now > latest:
        return now
    return latest + timedelta(microseconds=1)


def read_note(root: str, category: str, filename: str) -> Note | None:
    """The note at `<category>/<filename>`, or `None` when it is not one.

    A file without a `slug:` key is somebody's own page in a category directory,
    not a note this module wrote; it is never indexed or touched."""
    path = os.path.join(root, category, filename)
    text = read_text(path)
    front = parse_frontmatter(text)
    if "slug" not in front:
        return None
    slug = filename.removesuffix(".md")
    stamp = _parse_stamp(front.get("updated"))
    return Note(
        category=category,
        slug=slug,
        title=get_first_heading(text) or slug,
        status=front.get("status") or STATUS_ACTIVE,
        hud_line=front.get("hud_line", ""),
        pinned=front.get("pinned", "").lower() == "true",
        updated=stamp or _modified_at(path),
        has_stamp=stamp is not None,
    )


def list_notes(root: str, index_names: tuple[str, ...]) -> list[Note]:
    """Every note under *root*, oldest `updated` first, ties by path."""
    notes: list[Note] = []
    for category in NOTE_CATEGORIES:
        try:
            filenames = sorted(os.listdir(os.path.join(root, category)))
        except OSError:
            continue
        for filename in filenames:
            if not filename.endswith(".md") or filename in index_names:
                continue
            note = read_note(root, category, filename)
            if note is not None:
                notes.append(note)
    return sorted(notes, key=lambda note: (note.updated, note.rel))


def _parse_stamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _modified_at(path: str) -> datetime:
    try:
        return datetime.fromtimestamp(os.path.getmtime(path))
    except OSError:
        return datetime.min


def compose_note(
    existing: str,
    note_path: str,
    index_name: str,
    fields: "dict[str, str]",
    targets: list[str],
) -> str:
    """The note file's text: *fields* as frontmatter and body, with the existing
    `## Backlinks` and `## Related` links merged in (never dropped) and the
    superseded Context/Finding appended to `## History` (capped at
    `HISTORY_MAX_ENTRIES`).

    *fields* carries `slug`, `title`, `context`, `finding`, `source` and the
    frontmatter values `applies_when`, `status`, `hud_line`, `pinned`,
    `updated`; the last two optional keys are omitted from the file when empty.
    """
    history = merge_entries(
        entries_under(existing, HISTORY_HEADING), prior_revision_entry(existing)
    )[-HISTORY_MAX_ENTRIES:]
    related = merge_entries(
        entries_under(existing, "## Related"),
        [
            f"- [{title_of(target)}]({relative(target, os.path.dirname(note_path))})"
            for target in targets
        ],
    )
    # The directory index is always the first backlink.
    backlinks = merge_entries(
        entries_under(existing, BACKLINKS_HEADING), [f"- [index]({index_name})"]
    )
    lines = [
        _FRONTMATTER_FENCE,
        f"slug: {fields['slug']}",
        f"applies_when: {one_line(fields['applies_when']) or NO_APPLIES_WHEN}",
        f"status: {fields['status']}",
    ]
    if fields["hud_line"]:
        lines.append(f"hud_line: {one_line(fields['hud_line'])}")
    if fields["pinned"] == "true":
        lines.append("pinned: true")
    lines += [
        f"updated: {fields['updated']}",
        _FRONTMATTER_FENCE,
        f"# {fields['title']}",
        "",
        f"**Context:** {fields['context']}",
        f"**Finding:** {fields['finding']}",
        f"**Source:** {fields['source']}",
        "",
    ]
    for heading, entries in (
        (HISTORY_HEADING, history),
        ("## Related", related),
        (BACKLINKS_HEADING, backlinks),
    ):
        if entries or heading == BACKLINKS_HEADING:
            lines += [heading, "", *entries, ""]
    return "\n".join(lines)


def entries_under(text: str, heading: str) -> list[str]:
    """The `- ` lines under *heading* in *text*, or `[]`."""
    lines = text.splitlines()
    if heading not in lines:
        return []
    start, end = section_bounds(lines, heading)
    return [line for line in lines[start:end] if line.startswith("- ")]


def merge_entries(existing: list[str], new: list[str]) -> list[str]:
    """Existing entries in their original order, then any genuinely new ones."""
    merged = list(existing)
    for entry in new:
        if entry not in merged:
            merged.append(entry)
    return merged


def section_bounds(lines: list[str], heading: str) -> tuple[int, int]:
    """`[start, end)` of the body under *heading*, up to the next `## `."""
    start = lines.index(heading) + 1
    end = start
    while end < len(lines) and not lines[end].startswith("## "):
        end += 1
    return start, end


def prior_revision_entry(text: str) -> list[str]:
    """The current Context/Finding as a dated `## History` bullet, or `[]`."""
    if not text:
        return []
    old_context = _field(text, "**Context:**")
    old_finding = _field(text, "**Finding:**")
    if old_context is None and old_finding is None:
        return []
    date = datetime.now().strftime("%Y-%m-%d")
    return [f"- {date}: {old_context or '—'} — {old_finding or '—'}"]


def _field(text: str, prefix: str) -> str | None:
    for line in text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return None


def title_of(path: str) -> str:
    return (
        get_first_heading(read_text(path))
        or os.path.splitext(os.path.basename(path))[0]
    )


def append_under_heading(text: str, heading: str, entry: str) -> str:
    lines = text.splitlines()
    if heading not in lines:
        return f"{text.rstrip()}\n\n{heading}\n\n{entry}\n"
    start, end = section_bounds(lines, heading)
    body = [line for line in lines[start:end] if line.strip()]
    body.append(entry)
    return "\n".join([*lines[:start], "", *body, "", *lines[end:]]).rstrip() + "\n"


def insert_before_backlinks(text: str, entry: str) -> str:
    """*text* with *entry* above the trailing Backlinks block, which stays last."""
    if entry in text:
        return text
    if BACKLINKS_HEADING not in text:
        return f"{text.rstrip()}\n{entry}\n"
    head, _, tail = text.partition(BACKLINKS_HEADING)
    return f"{head.rstrip()}\n{entry}\n\n{BACKLINKS_HEADING}{tail}"


def with_backlink(text: str, entry: str) -> str:
    """*text* with a backlink *entry* under `## Backlinks`, once."""
    if entry in text:
        return text
    if BACKLINKS_HEADING not in text:
        text = f"{text.rstrip()}\n\n{BACKLINKS_HEADING}\n"
    return f"{text.rstrip()}\n{entry}\n"


def relative(path: str, start: str) -> str:
    """`os.path.relpath` with `/` separators, for portable markdown links."""
    return os.path.relpath(path, start).replace(os.sep, "/")


_LINK_LINE_RE = re.compile(r"^- (?:\[.*\]\(([^)]+)\)|.*\(\[note\]\(([^)]+)\)\))\s*$")


def scrub_links_to(root: str, target_path: str) -> dict[str, str]:
    """The new text of every `.md` file under *root* that has a line linking to
    *target_path*, with those lines dropped.

    A line is `- [title](path)` or a HUD `… ([note](path))`; the label is matched
    greedily since a title may contain `]`, and the end-anchored target always
    finds the last link on the line. A full-tree scan per delete; add an index if
    the journal grows large.
    """
    target_abs = os.path.abspath(target_path)
    changes: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            if not filename.endswith(".md") or os.path.abspath(file_path) == target_abs:
                continue
            text = read_text(file_path)
            kept = [
                line
                for line in text.splitlines()
                if not _is_link_to(line, file_path, target_abs)
            ]
            if text and len(kept) != len(text.splitlines()):
                changes[file_path] = "\n".join(kept).rstrip() + "\n"
    return changes


def _is_link_to(line: str, file_path: str, target_abs: str) -> bool:
    match = _LINK_LINE_RE.match(line)
    if not match:
        return False
    resolved = os.path.abspath(
        os.path.join(os.path.dirname(file_path), match.group(1) or match.group(2))
    )
    return resolved == target_abs
