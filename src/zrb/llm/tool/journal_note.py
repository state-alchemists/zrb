"""A journal note as data: its frontmatter is the one source of truth.

Everything the injected index shows about a note is a field here — whether it is
active (`status`, `applies_when`), the one line that represents it (`hud_line`,
and whether that line was written or derived), whether it is pinned (`pinned`),
where it ranks (`updated`), how it is found again (`keywords`), and what replaced
it (`superseded_by`). The indexes are rendered from these fields by
`journal_index`, never edited as text, so a note and its index entries cannot
disagree.

The two fields the index cannot do without are never absent: a note with no
`applies_when` is refused (a claim nobody can check cannot be retired), and a note
with no `hud_line` is given one derived from its Finding, so no note exists that
the always-injected index can never show.

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
# retire. `NO_APPLIES_WHEN` is what a version before that rule stored in the
# condition's place: it is read, so an old note still loads, and refused, so it is
# never written again.
NO_APPLIES_WHEN = "not stated"
# Where a note's `hud_line` came from. A written line is the caller's words and no
# later derivation may replace it; a derived one is this module's reading of the
# note's own Finding, so it is regenerated when the Finding changes.
HUD_LINE_SOURCE_WRITTEN = "written"
HUD_LINE_SOURCE_DERIVED = "derived"
# The index spends its budget on one line per note, and a line longer than this is
# not a headline any more. A derived line is cut here; a written one is kept whole
# and the tool result asks for a shorter one.
HUD_LINE_MAX_CHARS = 160
# A keyword is something to search for, so a word this short (`the`, `and`, `for`)
# matches most notes and ranks none of them.
KEYWORDS_MIN_WORD_LENGTH = 4
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_FRONTMATTER_FENCE = "---"
# Where a sentence may end. A Finding often has no terminator at all
# (`retry_period` is read without a lock), which is the whole of it.
_TERMINATOR_RE = re.compile(r"[.!?](?=\s|$)")
# A period inside one of these never ends a sentence: the abbreviation needs the
# word after it (`e.g. enabled`) or is a title before a name (`Dr. Chen`). `e.g.`
# is the one that bit: "The value is e.g. enabled for retries" used to be cut to
# "The value is e.g.", a claim that stops mid-thought and reads as complete.
#
# `etc` is deliberately absent. It is the one abbreviation that also ends
# sentences — `Use etc. Next step is locking.` — so it cannot be decided from
# the word alone; it falls through to the next-word rule, which reads the
# capital as a new sentence and the lower-case word as a continuation
# (`backoff, etc. and nothing more`).
_NEVER_TERMINAL = frozenset(
    {
        "e.g",
        "i.e",
        "vs",
        "cf",
        "al",
        "approx",
        "fig",
        "mr",
        "mrs",
        "ms",
        "dr",
        "prof",
        "sr",
        "jr",
        "st",
    }
)
# A sentence after a terminator starts with one of these; a lower-case word is a
# continuation (`and`, `or`), which is what makes the abbreviation rule safe.
_SENTENCE_START_CHARS = "\"'([“‘"


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


def check_applies_when(applies_when: str | None) -> str:
    """The condition a note holds under, or a refusal the model can act on.

    A finding with no expiry can only be re-read: nothing says when it stopped
    being true, so nothing retires it. `not stated` is the placeholder an earlier
    version wrote in the condition's place, and it is not a condition either.
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


def derive_hud_line(finding: str) -> str:
    """The first sentence of *finding*, on one line and capped at 160 characters.

    A note with no line of its own still has to reach the injected index, and the
    first sentence of what it found is the headline it already carries. A sentence
    past the cap is cut at a word boundary and marked with `…`, so the index shows
    a shortened line rather than a claim that reads as complete.
    """
    text = one_line(finding)
    return _cap_line(_first_sentence(text), HUD_LINE_MAX_CHARS)


def _first_sentence(text: str) -> str:
    """*text* up to its first sentence terminator, or all of it when it has none.

    Where the line is cut is the whole point: a claim that stops at `e.g.` is
    worse than a long one, because it reads as a finished statement. So a
    terminator that `_is_sentence_end` refuses is stepped over and the search
    continues; when no terminator qualifies, the finding is its claim."""
    for match in _TERMINATOR_RE.finditer(text):
        if _is_sentence_end(text, match.start()):
            return text[: match.start() + 1]
    return text


def _is_sentence_end(text: str, index: int) -> bool:
    """Whether the terminator at *index* ends a sentence rather than a word.

    Only a period can sit inside a word, so only a period has to look around:
    at the word it follows (`e.g`, `Mr`, a single initial `J`), and at what
    comes after it — a capital, a digit, a quote or a bracket starts a
    sentence, while a lower-case word continues the one already open. An
    abbreviation that never ends a sentence stops the check there; one that can
    (`etc`) falls through and lets the next word decide."""
    if text[index] != ".":
        return True
    before = text[:index].rsplit(None, 1)[-1].lstrip(_SENTENCE_START_CHARS).lower()
    if before in _NEVER_TERMINAL or (len(before) == 1 and before.isalpha()):
        return False
    rest = text[index + 1 :].lstrip()
    if not rest:
        return True
    return (
        rest[0].isupper()
        or rest[0].isdigit()
        or rest[0] in _SENTENCE_START_CHARS
    )


def _cap_line(text: str, limit: int) -> str:
    """*text* cut to at most *limit* characters, at a word boundary, ending in `…`."""
    if len(text) <= limit:
        return text
    head = text[: limit - 1].rstrip()
    if " " in head:
        head = head.rsplit(" ", 1)[0]
    return f"{head.rstrip(' ,;:—-.')}…"


def resolve_hud_line(
    supplied: str, finding: str, prior: dict[str, str]
) -> tuple[str, str]:
    """The `hud_line` a write leaves on the note, and where it came from.

    A line the caller wrote is the note's own, and a rewrite that passes none
    keeps it — a derived line may never overwrite a written one. A derived line is
    this module's reading of the Finding, so it is regenerated when the Finding
    changes. A line the file carries with no `hud_line_source` was written before
    that field existed and counts as written: it is somebody's words, and trading
    them for a guess would lose the one thing the index needed.
    """
    if supplied.strip():
        return one_line(supplied), HUD_LINE_SOURCE_WRITTEN
    prior_line = prior.get("hud_line", "")
    if prior_line and prior.get("hud_line_source") != HUD_LINE_SOURCE_DERIVED:
        return one_line(prior_line), HUD_LINE_SOURCE_WRITTEN
    return derive_hud_line(finding), HUD_LINE_SOURCE_DERIVED


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
    `updated`, plus the optional `keywords`; a `hud_line` or `keywords` the
    caller left empty is filled from the note itself (see `claim_frontmatter`),
    and `pinned` is omitted from the file when false.
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

    `hud_line` and `keywords` are the two fields a caller may omit, and each has a
    fallback rather than an absence: the line is derived from the Finding unless
    the file already carries one a caller wrote, and the keywords come from the
    file when it has them and from the slug and title when it does not. So a
    rewrite never loses what an earlier call established, and a note nobody wrote
    either for still reaches the injected index and the search.
    """
    prior = parse_frontmatter(existing)
    line, source = resolve_hud_line(fields["hud_line"], fields["finding"], prior)
    keywords = (
        normalize_keywords(fields.get("keywords", "").split(","))
        or normalize_keywords(prior.get("keywords", "").split(","))
        or derive_keywords(fields["slug"], fields["title"])
    )
    lines = [
        f"slug: {fields['slug']}",
        f"applies_when: {one_line(fields['applies_when'])}",
        f"status: {fields['status']}",
    ]
    if line:
        lines += [f"hud_line: {line}", f"hud_line_source: {source}"]
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
