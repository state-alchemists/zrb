"""A journal note as data: its frontmatter is the one source of truth.

Everything the injected index shows about a note is a field here — whether it is
active (`status`, `applies_when`), the one line that represents it (`hud_line`),
whether it is pinned (`pinned`), where it ranks (`updated`), how it is found
again (`keywords`), and what replaced it (`superseded_by`). The indexes are
rendered from these fields by `journal_index`, never edited as text, so a note
and its index entries cannot disagree.

The three fields the index cannot do without are never absent, and none of them
is guessed here: a note with no `applies_when` is refused (a claim nobody can
check cannot be retired), a note with no `finding` is refused (there is nothing
to remember), and a note with no `hud_line` is refused too — the line is the
claim the note will be read by, so the caller writes it rather than this module
deriving it from the first sentence of the Finding.

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
# `applies_when` is the condition under which a note still holds. A finding whose
# expiry nobody wrote down is one nobody can check, so nobody can retire it.
# `NO_APPLIES_WHEN` is the placeholder older notes store in its place: it is read,
# so those notes still load, and refused, so it is never written again.
NO_APPLIES_WHEN = "not stated"
# The index spends one line per note; a longer claim is a paragraph, and the note
# already has one. The line is the caller's, so this is a refusal with a number,
# not a cut — a silent trim would store a claim nobody wrote.
HUD_LINE_MAX_CHARS = 160
# A keyword is something to search for, so a word this short (`the`, `and`, `for`)
# matches most notes and ranks none of them.
KEYWORDS_MIN_WORD_LENGTH = 4
_SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
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
    # The `keywords:` line, comma-separated, as the note stores it. Ranking reads
    # it, and it is the only field a search can match that the prose does not.
    keywords: str = ""

    @property
    def rel(self) -> str:
        """Journal-root-relative path, with `/` separators."""
        return f"{self.category}/{self.slug}.md"

    @property
    def is_active(self) -> bool:
        return self.status != STATUS_SUPERSEDED

    @property
    def is_migrated(self) -> bool:
        """Whether this note's frontmatter owns its pin and HUD line.

        Only such a note carries an `updated:` stamp; one without it predates
        the derived index, when `index.md` was the only place a pin lived."""
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
    if not _SLUG_RE.fullmatch(slug):
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


def check_applies_when(applies_when: str | None) -> str:
    """The condition a note holds under, or a refusal the model can act on.

    A finding with no expiry can only be re-read: nothing says when it stopped
    being true, so nothing retires it. `not stated` is a placeholder, not a
    condition either.
    """
    text = one_line(applies_when or "")
    if not text:
        raise ValueError(
            "[SYSTEM SUGGESTION]: applies_when was empty, so nothing was written. "
            "Say the condition under which the finding still holds, in words a "
            "later session can check — a version (`while zrb 3.29 is the released "
            "line`), a file (`while src/zrb/retry.py is unchanged`), a setting, or "
            "a stated preference. Without it the note can never be retired, only "
            "re-read."
        )
    if text.lower() == NO_APPLIES_WHEN:
        raise ValueError(
            "[SYSTEM SUGGESTION]: applies_when was `not stated`, which is a "
            "placeholder rather than a condition, so nothing was written. Name "
            "what a later session can check: a version, a file, a setting, or a "
            "preference the user stated. A note that cannot say when it stops "
            "applying can only be re-read, never retired."
        )
    return text


def check_finding(finding: str | None) -> str:
    """The finding a note records, or a refusal the model can act on.

    A note with no finding has nothing to remember and nothing to derive a
    claim from: its `hud_line` would be empty, the frontmatter would carry no
    line, and `plan_hud` would leave the note out of the injected index — the
    one place a note has to reach to be read again.
    """
    text = one_line(finding or "")
    if not text:
        raise ValueError(
            "[SYSTEM SUGGESTION]: finding was empty, so nothing was written. "
            "State what was found, in the one or two sentences a later session "
            "should be able to act on, then write the note again."
        )
    return text


def check_hud_line(hud_line: str | None, prior_line: str = "") -> str:
    """The one line a note is read by, or a refusal the model can act on.

    This line is the caller's sentence, not this module's guess. The always
    injected index spends one line per note, so the line is what a later session
    decides with: `retries happen once per prompt` says something, a first
    sentence of a Finding only sometimes does.

    A write without one is refused, and so is one longer than a headline. The
    over-long case is a refusal rather than a cut because a trimmed claim is a
    claim nobody wrote, and the index would then show a sentence that stops
    mid-thought while reading as finished.

    *prior_line* is the line the note already carries, when it has one: a
    rewrite that forgets to restate it is told which line it was about to lose,
    so the omission costs a correction instead of a wrong claim in the index.
    """
    text = one_line(hud_line or "")
    if not text:
        if prior_line:
            raise ValueError(
                "[SYSTEM SUGGESTION]: hud_line was empty, so nothing was "
                f"written. This note's line is {prior_line!r} — pass it back "
                "unchanged if the claim still holds, or write a new one that "
                "says what the note now claims."
            )
        raise ValueError(
            "[SYSTEM SUGGESTION]: hud_line was empty, so nothing was written. "
            "Write the one line a later session reads this note by — the claim "
            "or preference itself, not the title — in 160 characters or fewer; "
            "the injected index shows that line and links the note."
        )
    if len(text) > HUD_LINE_MAX_CHARS:
        raise ValueError(
            f"[SYSTEM SUGGESTION]: hud_line is {len(text)} characters, over the "
            f"{HUD_LINE_MAX_CHARS} a headline is allowed, so nothing was "
            "written. Shorten it to the claim itself and write the note again."
        )
    return text


def normalize_keywords(values: list[str]) -> str:
    """The `keywords:` value: lower-case, comma-separated, one line, no repeats.

    A value may itself arrive comma-separated — that is the field's own storage
    shape, and what a caller reads back from a note — so each is split before it
    is cleaned."""
    keywords: list[str] = []
    for value in values:
        for part in value.split(","):
            keyword = _keyword(part)
            if keyword and keyword not in keywords:
                keywords.append(keyword)
    return ", ".join(keywords)


def derive_keywords(slug: str, title: str) -> str:
    """Keywords from the note's own name: the slug's words, then the title's.

    A note nobody gave keywords to is still one a later session has to find, and
    the slug and title are the words its author already chose for it. A word under
    four characters is left out: it is `the`, `and`, `for`, and it matches most
    notes while ranking none of them.
    """
    words = [*slug.replace("-", " ").split(), *title.split()]
    return normalize_keywords(
        [word for word in words if len(_keyword(word)) >= KEYWORDS_MIN_WORD_LENGTH]
    )


def effective_keywords(slug: str, title: str, given: str, prior: str) -> str:
    """The `keywords:` value a write actually stores: given, else the file's, else ours.

    The fallback is why anything reading a note's subject must come through here
    rather than use the words the caller happened to pass. A revision that omits
    `keywords` keeps the ones already on disk, and a brand-new note derives them
    from its own slug and title, so what the caller supplied is not what the note
    says — and two callers computing "what is this note about" two different ways
    is how a note ends up with a neighbour it cannot see.
    """
    return (
        normalize_keywords(given.split(","))
        or normalize_keywords(prior.split(","))
        or derive_keywords(slug, title)
    )


def _keyword(value: str) -> str:
    """One keyword: lower-case, no surrounding punctuation a sentence brought."""
    return one_line(value).strip().lower().strip(",.`'\"()[]:;!?")


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
        keywords=front.get("keywords", ""),
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
    `updated`, plus the optional `keywords`. The `hud_line` is the caller's and
    is written as given; a missing `keywords` is filled from the note's own name
    (see `claim_frontmatter`), and `pinned` is omitted from the file when false.
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
        *claim_frontmatter(fields, existing),
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


def claim_frontmatter(fields: "dict[str, str]", existing: str) -> list[str]:
    """The frontmatter lines that say when a note holds and where it shows.

    `hud_line` is mandatory and arrives already checked, so it is written as
    given — nothing here invents or replaces one. `keywords` is the only field a
    caller may omit, and it has a fallback rather than an absence (see
    `effective_keywords`), so a note nobody chose keywords for is still one a
    later session finds.
    """
    prior = parse_frontmatter(existing)
    keywords = effective_keywords(
        fields["slug"],
        fields["title"],
        fields.get("keywords", ""),
        prior.get("keywords", ""),
    )
    lines = [
        f"slug: {fields['slug']}",
        f"applies_when: {one_line(fields['applies_when'])}",
        f"status: {fields['status']}",
        f"hud_line: {one_line(fields['hud_line'])}",
    ]
    if fields["pinned"] == "true":
        lines.append("pinned: true")
    if keywords:
        lines.append(f"keywords: {keywords}")
    lines.append(f"updated: {fields['updated']}")
    return lines


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
