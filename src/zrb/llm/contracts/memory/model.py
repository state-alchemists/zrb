"""The shapes a memory entry takes: a fact, a diary entry and a week note.

A fact is one claim about the world, identified by its subject. A diary entry is
one day, identified by its date, and a week note is one ISO week, identified by
its week — the rung between a day and the month nobody writes down. All three
carry a ``claim`` — the single sentence that is rendered into the core or the
recent block, matched by search, and compared on revision — and an optional body
that holds the evidence and is never injected.

Three rules are enforced here rather than by the tools, so the reader, the writer
and the migration agree:

* **The field is bounded, the sentence is not parsed.** ``claim`` is limited to
  160 characters and one line. Splitting a paragraph into "its first sentence"
  was tried three times on the journal and produced three different answers, so
  the one-sentence rule stays a rule for the writer and never becomes a parser.
* **An id is a subject, not a path.** Kebab-case, 64 characters, no separator:
  a model-supplied id can never name a file outside ``facts/``.
* **A claim is data.** Text carrying a prompt-injection marker is refused at
  write time, because every pinned claim is read back inside a future prompt.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from zrb.config.config import CFG

FENCE = "---"

MAX_ID_CHARS = 64
MAX_CLAIM_CHARS = 160
# A fact's body is evidence about one subject, written once, so its bound is a
# constant. A diary's body is a page that grows through the day, and both diary
# limits are settings: how long a page is belongs to whoever keeps the day.
MAX_FACT_BODY_CHARS = 8_000

KIND_FACT = "fact"
KIND_LOOP = "loop"
KIND_DIARY = "diary"
KIND_WEEK = "week"
KINDS = (KIND_FACT, KIND_LOOP, KIND_DIARY)

# `body_mode`: whether a body replaces the stored one or is added after it. A
# day grows as it goes on, so adding a paragraph must not mean reading the whole
# day back and sending it again just to keep what it already said.
BODY_REPLACE = "w"
BODY_APPEND = "a"
BODY_MODES = (BODY_REPLACE, BODY_APPEND)

STATUS_ACTIVE = "active"
STATUS_RETIRED = "retired"

REASON_WRONG = "wrong"
REASON_STALE = "stale"
REASON_DONE = "done"
REASONS = (REASON_WRONG, REASON_STALE, REASON_DONE)

# A diary day does not go stale and is never "done": it happened.
DIARY_REASONS = (REASON_WRONG,)

_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_WEEK = re.compile(r"^\d{4}-W\d{2}$")

# The hour a paragraph names, `HH:MM` on the 24-hour clock. A diary paragraph
# opens on the hour it happened at, so the earliest one a body carries is when
# its day began — the one property of a day's shape a rewrite can be held to.
_HOUR = re.compile(r"\b(?:[01]\d|2[0-3]):[0-5]\d\b")

# Markers that only make sense as instructions to a model. A memory is read back
# inside a later prompt, so a line holding one is a poisoned fact, not a claim.
#
# This is a tripwire, not a proof. A blocklist of phrasings cannot be complete,
# and a claim may legitimately quote an imperative ("Go said: retry, don't read
# the code"), so the list holds only text that cannot appear in a claim about the
# world: prompt syntax, an override of earlier instructions, and the assignment of
# a role. The rest of the defence is structural — the injected block says its
# lines are data, and `render` drops any line that trips this check.
# Containers the prompt uses. Both an opening and a closing tag are refused: a
# closing one is the dangerous half, because it terminates the block and leaves
# whatever follows reading as ordinary text rather than as data. The two journal
# tags stay listed after the journal itself is gone: an older conversation still
# in a history carries blocks wearing them, and a claim quoting one of those is
# the same escape as a claim quoting `<memory>`.
_CONTAINER_TAGS = ("memory", "journal-index", "journal-claims", "live-context")

_INSTRUCTION_MARKERS = (
    "<|",
    "<system",
    "</system",
    "[system",
    "[system suggestion]",
    "ignore previous instructions",
    "ignore all previous instructions",
    "ignore the previous instructions",
    "you are now",
    "you are no longer",
    "your new role",
    "your new instructions",
    "new system prompt",
    "from now on you",
) + tuple(tag_form for tag in _CONTAINER_TAGS for tag_form in (f"<{tag}", f"</{tag}"))

# Field order in the file is fixed: a diff stays readable when a claim is revised.
_FACT_FIELDS = (
    "id",
    "claim",
    "kind",
    "status",
    "pin",
    "tags",
    "applies_when",
    "source",
    "updated",
    "reason",
    "retired_on",
    "retired_by",
)
_DIARY_FIELDS = (
    "id",
    "kind",
    "claim",
    "handover",
    "status",
    "source",
    "updated",
    "reason",
    "retired_on",
)


@dataclass
class Fact:
    """One claim about the world, under a subject id."""

    id: str
    claim: str
    kind: str = KIND_FACT
    status: str = STATUS_ACTIVE
    pin: bool = False
    tags: tuple[str, ...] = ()
    applies_when: str = ""
    source: str = ""
    updated: str = ""
    reason: str = ""
    retired_on: str = ""
    # The component that called `forget` (`main_agent`, `hook_agent`, ...), read
    # from the running component rather than passed in: a writer must not be able
    # to say it was somebody else, and the count it makes possible is "how many
    # did the reviewer close, against how many did a conversation close". Empty on
    # an active claim, and on one retired before the field existed — the retired
    # files from before it are not wrong, just unstamped.
    retired_by: str = ""
    body: str = ""

    @property
    def is_active(self) -> bool:
        return self.status == STATUS_ACTIVE

    def to_markdown(self) -> str:
        values = {
            "id": self.id,
            "claim": self.claim,
            "kind": self.kind,
            "status": self.status,
            "pin": "true" if self.pin else "false",
            "tags": ", ".join(self.tags),
            "applies_when": self.applies_when,
            "source": self.source,
            "updated": self.updated,
            "reason": self.reason,
            "retired_on": self.retired_on,
            "retired_by": self.retired_by,
        }
        return _document(_FACT_FIELDS, values, self.body)

    @classmethod
    def from_markdown(cls, text: str) -> "Fact | None":
        front, body = split_document(text)
        fact_id = front.get("id", "").strip()
        claim = front.get("claim", "").strip()
        if not fact_id or not claim:
            return None
        kind = front.get("kind", KIND_FACT).strip() or KIND_FACT
        return cls(
            id=fact_id,
            claim=claim,
            kind=kind if kind in KINDS else KIND_FACT,
            status=front.get("status", STATUS_ACTIVE).strip() or STATUS_ACTIVE,
            pin=front.get("pin", "").strip().lower() == "true",
            tags=_split_tags(front.get("tags", "")),
            applies_when=front.get("applies_when", "").strip(),
            source=front.get("source", "").strip(),
            updated=front.get("updated", "").strip(),
            reason=front.get("reason", "").strip(),
            retired_on=front.get("retired_on", "").strip(),
            retired_by=front.get("retired_by", "").strip(),
            body=body,
        )


@dataclass
class Diary:
    """One day, written in the first person. ``claim`` is what the day was."""

    id: str
    claim: str
    handover: str = ""
    status: str = STATUS_ACTIVE
    source: str = ""
    updated: str = ""
    reason: str = ""
    retired_on: str = ""
    body: str = ""

    kind: str = field(default=KIND_DIARY, init=False)

    @property
    def is_active(self) -> bool:
        return self.status == STATUS_ACTIVE

    def to_markdown(self) -> str:
        values = {
            "id": self.id,
            "kind": KIND_DIARY,
            "claim": self.claim,
            "handover": self.handover,
            "status": self.status,
            "source": self.source,
            "updated": self.updated,
            "reason": self.reason,
            "retired_on": self.retired_on,
        }
        return _document(_DIARY_FIELDS, values, self.body)

    @classmethod
    def from_markdown(cls, text: str) -> "Diary | None":
        front, body = split_document(text)
        day = front.get("id", "").strip()
        claim = front.get("claim", "").strip()
        if not day or not claim:
            return None
        return cls(
            id=day,
            claim=claim,
            handover=front.get("handover", "").strip(),
            status=front.get("status", STATUS_ACTIVE).strip() or STATUS_ACTIVE,
            source=front.get("source", "").strip(),
            updated=front.get("updated", "").strip(),
            reason=front.get("reason", "").strip(),
            retired_on=front.get("retired_on", "").strip(),
            body=body,
        )


_WEEK_FIELDS = (
    "id",
    "kind",
    "claim",
    "status",
    "source",
    "updated",
)


@dataclass
class WeekNote:
    """One ISO week, in the first person. ``claim`` is what the week was.

    A week is the rung between a day and a month: too long for a diary entry,
    too short to be a standing belief. It carries no handover — the state of play
    is the last day's business — and no body of its own, because the day claims it
    was written from stay the evidence.
    """

    id: str
    claim: str
    status: str = STATUS_ACTIVE
    source: str = ""
    updated: str = ""

    kind: str = field(default=KIND_WEEK, init=False)

    @property
    def is_active(self) -> bool:
        return self.status == STATUS_ACTIVE

    def to_markdown(self) -> str:
        values = {
            "id": self.id,
            "kind": KIND_WEEK,
            "claim": self.claim,
            "status": self.status,
            "source": self.source,
            "updated": self.updated,
        }
        return _document(_WEEK_FIELDS, values, "")

    @classmethod
    def from_markdown(cls, text: str) -> "WeekNote | None":
        front, _ = split_document(text)
        week = front.get("id", "").strip()
        claim = front.get("claim", "").strip()
        if not week or not claim:
            return None
        return cls(
            id=week,
            claim=claim,
            status=front.get("status", STATUS_ACTIVE).strip() or STATUS_ACTIVE,
            source=front.get("source", "").strip(),
            updated=front.get("updated", "").strip(),
        )


def claim_error(claim: str) -> str | None:
    """Why *claim* cannot be stored, or ``None`` when it can."""
    text = claim.strip()
    if not text:
        return (
            "A claim is required: one sentence saying what is true. "
            "[SYSTEM SUGGESTION]: re-send with the sentence itself, not a title."
        )
    if "\n" in claim or "\r" in claim:
        return (
            "A claim is one line; this one wraps. Put the detail in `body` — it "
            "is evidence and is never injected. [SYSTEM SUGGESTION]: re-send with "
            "the sentence alone."
        )
    if len(text) > MAX_CLAIM_CHARS:
        return (
            f"A claim is at most {MAX_CLAIM_CHARS} characters and this one is "
            f"{len(text)}. Shorten it to the part a later session must see; the "
            "rest belongs in `body`."
        )
    reason = injection_reason(text)
    if reason:
        return (
            f"A claim cannot carry {reason}: it assigns a role or overrides "
            "instructions, and a claim states what is true. Every pinned claim is "
            "read back inside a future prompt. Put the wording in `body`, which "
            "is evidence and is never injected."
        )
    return None


def id_error(fact_id: str) -> str | None:
    """Why *fact_id* cannot name a fact, or ``None`` when it can."""
    text = fact_id.strip()
    if not text:
        return (
            "`id` is required and is the subject: e.g. `staging-ssh-port`. "
            "[SYSTEM SUGGESTION]: search first, then re-use the existing id when "
            "the subject is already known."
        )
    if len(text) > MAX_ID_CHARS:
        return f"`id` is at most {MAX_ID_CHARS} characters and this one is {len(text)}."
    if not _ID.match(text):
        return (
            f"`id` must be kebab-case ({text!r} is not): lowercase letters, "
            "digits and single hyphens, no path separator and no dot."
        )
    return None


def date_error(day: str) -> str | None:
    if not _DATE.match(day.strip()):
        return f"A diary entry's id is its date, `YYYY-MM-DD` ({day!r} is not)."
    try:
        datetime.strptime(day.strip(), "%Y-%m-%d")
    except ValueError:
        return f"{day!r} is not a real date."
    return None


def week_error(week: str) -> str | None:
    """Why *week* cannot name a week note, or ``None`` when it can.

    The shape is checked before the calendar: `2026-W54` is week-shaped and does
    not exist, and only `fromisocalendar` knows which years carry a week 53.
    """
    text = week.strip()
    if not _WEEK.match(text):
        return f"A week note's id is its ISO week, `YYYY-Www` ({week!r} is not)."
    try:
        date.fromisocalendar(int(text[:4]), int(text[6:]), 1)
    except ValueError:
        return f"{week!r} is not a real ISO week."
    return None


def iso_week(day: str) -> str:
    """The ISO week a `YYYY-MM-DD` day belongs to, as `YYYY-Www`.

    Taken from `isocalendar` rather than arithmetic on the date, because the
    first days of January can belong to the previous year's last week.
    """
    year, week, _ = date.fromisoformat(day.strip()).isocalendar()
    return f"{year}-W{week:02d}"


def week_span(week: str) -> tuple[str, str]:
    """``(monday, sunday)`` of *week*, as `YYYY-MM-DD` strings."""
    monday = date.fromisocalendar(int(week[:4]), int(week[6:]), 1)
    return monday.isoformat(), (monday + timedelta(days=6)).isoformat()


def is_date_shaped(value: str) -> bool:
    """Whether *value* has a date's shape, valid or not.

    A malformed date (`2024-02-30`) must not fall through to the fact path just
    because it is not a real one: a date names a diary entry, and one that is not
    a date names nothing.
    """
    return bool(_DATE.match(value.strip()))


def reason_error(reason: str, kind: str) -> str | None:
    if reason not in REASONS:
        return f"`reason` is one of {', '.join(REASONS)}; {reason!r} is not."
    allowed = DIARY_REASONS if kind == KIND_DIARY else REASONS
    if reason not in allowed:
        return (
            f"A diary entry is forgotten only as `wrong`: a day does not go "
            f"stale and is never done ({reason!r} was given)."
        )
    return None


def body_limit(kind: str) -> int:
    """The most characters a body of *kind* may hold."""
    if kind == KIND_DIARY:
        return CFG.LLM_MEMORY_DIARY_MAX_CHARS
    return MAX_FACT_BODY_CHARS


def compact_at(kind: str) -> int:
    """The length past which a body of *kind* is compacted, not grown.

    Only a diary has a threshold below its cap: a fact's body is evidence about
    one subject and is replaced rather than carried forward, so the two numbers
    are the same one. Clamped, because a threshold above the cap would ask for a
    page the cap refuses.
    """
    if kind != KIND_DIARY:
        return body_limit(kind)
    return min(CFG.LLM_MEMORY_DIARY_COMPACT_AT, CFG.LLM_MEMORY_DIARY_MAX_CHARS)


def body_error(body: str | None, kind: str) -> str | None:
    """Why *body*, as the caller wrote it, cannot be stored, or ``None``."""
    if body is None:
        return None
    limit = body_limit(kind)
    if len(body) > limit:
        return (
            f"The body is at most {limit} characters and this one is {len(body)}: "
            "a memory is a page, not a transcript."
        )
    reason = injection_reason(body)
    if reason:
        return f"The body cannot carry {reason}."
    return None


def body_overflow(merged: str, kind: str = KIND_DIARY) -> str | None:
    """Why the body a write would *become* cannot be stored, or ``None``.

    An append is measured as the whole it makes, not as the paragraph added to
    it, and only the store's lock knows what that whole is: the caller's fragment
    passed `body_error` already, so this asks the one question that needs the old
    body — whether it still fits.
    """
    limit = body_limit(kind)
    if len(merged) <= limit:
        return None
    return (
        f"The day's body would be {len(merged)} characters and the cap is "
        f"{limit}. Nothing was written. Shorten this paragraph, or replace the "
        "body as a whole; the cap is the setting `LLM_MEMORY_DIARY_MAX_CHARS`."
    )


def append_past_compaction(body: str, kind: str = KIND_DIARY) -> str | None:
    """Why a paragraph may not be added to the day this would make, or ``None``.

    Measured on the whole the append makes, like `body_overflow`: a paragraph of
    three hundred characters is one too many on a page with two hundred left
    below the threshold. The page has to be compacted before it grows, because a
    day that only ever rewrites to its own ceiling leaves the next writer no room
    — and the next writer is the one refused.
    """
    at = compact_at(kind)
    if len(body) <= at:
        return None
    return (
        f"The day's body would be {len(body)} characters, and a diary is "
        f"compacted from {at}: the paragraph is not too long, the page it joins "
        "is too full."
    )


def rewrite_not_compacted(
    before: str, after: str, kind: str = KIND_DIARY
) -> str | None:
    """Why a rewrite may not land at or over the compaction point, or ``None``.

    A rewrite is the one write that skips `body_overflow`, so it is the one that
    can carry a page to its ceiling and leave the next paragraph with nothing: a
    day rewritten to 7,980 of 8,000 every turn compacts forever and frees nothing,
    and the writer that arrives next is the one refused.

    Two shapes end there. From a page past the point a rewrite *is* a compaction
    and has to behave like one, so it has to free something. From a page under it
    a rewrite may grow, but not past the point — growth is what an append is for,
    and an append is measured against the whole it makes. Both answers are one:
    a rewrite lands under the point.
    """
    at = compact_at(kind)
    if len(after) < at:
        return None
    if len(before) < at:
        return (
            f"The rewrite is {len(after)} characters and a diary is compacted "
            f"from {at}: a page under that grows by an append, one paragraph at a "
            "time, so a rewrite may not jump it to the ceiling in one write."
        )
    return (
        f"The day it replaces is {len(before)} characters and this rewrite is "
        f"{len(after)}: a diary is compacted from {at}, so a body that lands at "
        "or over that has freed nothing and the page is as full as it was."
    )


def first_hour(body: str) -> str | None:
    """The earliest ``HH:MM`` *body* names, or ``None`` when it names none."""
    hours = _HOUR.findall(body)
    return min(hours) if hours else None


def rewrite_starts_later(before: str, after: str, kind: str = KIND_DIARY) -> str | None:
    """Why a rewrite may not open the day later than the day opened, or ``None``.

    A rewrite is the one write that can lose a paragraph, and the paragraph it
    loses first is the one it read least recently: the morning. A compaction keeps
    every moment and shortens the detail, so the hour the day began at survives it,
    and a page that opens at 17:54 in place of one that opened at 06:37 is not a
    compaction — it is a new page wearing the day's name. Measured on the earliest
    hour each body names, which is a property of the two pages rather than of the
    clock the writer was reading; a body naming no hour is passed, because a day
    made of paragraphs without hours has no opening to keep.
    """
    if kind != KIND_DIARY:
        return None
    opened = first_hour(before)
    opens = first_hour(after)
    if opened is None or opens is None or opens <= opened:
        return None
    return (
        f"The day it replaces opened at {opened} and this rewrite opens at "
        f"{opens}: a compaction keeps the hour the day began at, so a day is "
        "compressed, not restarted."
    )


def digest_body(body: str) -> str:
    """A short digest of a body: what a rewrite names as the page it read.

    Reading the day and writing it back are two moments with a model in between,
    and a day can move in that gap: two reviewers on the same day each read it,
    each compact it, and the second write replaced the first one's paragraph with
    a body that never held it. Compaction is a rewrite of the whole page, so it is
    the one write that can lose another's work — the digest is compared inside the
    lock, where the body it describes is the body being replaced.
    """
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:8]


def handover_error(handover: str | None) -> str | None:
    if handover is None:
        return None
    limit = CFG.LLM_MEMORY_HANDOVER_MAX_CHARS
    if len(handover) > limit:
        return (
            f"A handover is at most {limit} characters and this one "
            f"is {len(handover)}: it is the state of play, not the day."
        )
    return injection_reason(handover)


def injection_reason(text: str) -> str | None:
    """The instruction marker *text* carries, or ``None``.

    Case-insensitive on the whole text: a marker that only works at the start of
    a line still does its damage inside a block the model reads top to bottom.
    An invisible or reordering character is refused first: it can hide a marker
    from this scan, or reverse what the reader sees.
    """
    hidden = _invisible_char(text)
    if hidden is not None:
        return f"an invisible or reordering character ({hidden})"
    folded = text.lower()
    for marker in _INSTRUCTION_MARKERS:
        if marker in folded:
            return f"the marker {marker!r}"
    return None


# Character classes that have no place in a claim: they do not print, they
# reorder what does. A bidi override can make "ignore previous instructions" run
# right-to-left, and a zero-width space splits a marker so the substring scan
# misses it. Checked by code point, so no lookalike alphabet is needed.
_INVISIBLE_RANGES = (
    (0x0000, 0x0008),  # C0 controls; tab and newline are excluded below
    (0x000B, 0x000C),
    (0x000E, 0x001F),
    (0x007F, 0x007F),  # DEL
    (0x200B, 0x200F),  # zero-width space/joiners, bidi marks
    (0x202A, 0x202E),  # bidi embedding and override
    (0x2060, 0x2064),  # word joiner and invisible operators
    (0x2066, 0x2069),  # bidi isolates
    (0xFEFF, 0xFEFF),  # byte-order mark
)

# Whitespace a multi-line body may hold.
_ALLOWED_CONTROLS = frozenset("\n\r\t")


def _invisible_char(text: str) -> str | None:
    """The first invisible or reordering character in *text*, or ``None``."""
    for char in text:
        if char in _ALLOWED_CONTROLS:
            continue
        point = ord(char)
        if any(low <= point <= high for low, high in _INVISIBLE_RANGES):
            return f"U+{point:04X}"
    return None


def format_stamp(moment: datetime | None = None) -> str:
    """A naive local ISO stamp, seconds of precision, as the files store it."""
    return (moment or datetime.now()).replace(microsecond=0).isoformat()


def parse_stamp(value: str) -> datetime | None:
    """*value* as naive local time, or ``None`` when it is not a stamp."""
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    if moment.tzinfo is None:
        return moment
    return moment.astimezone().replace(tzinfo=None)


def split_document(text: str) -> tuple[dict[str, str], str]:
    """``(frontmatter, body)`` of *text*.

    A document with no frontmatter reads as ``({}, text)``: a hand-written page
    in the store is evidence someone may have meant to keep, not an error.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != FENCE:
        return {}, text
    for end in range(1, len(lines)):
        if lines[end].strip() == FENCE:
            return _read_fields(lines[1:end]), "\n".join(lines[end + 1 :]).strip()
    return {}, text


def _read_fields(lines: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in lines:
        key, separator, value = line.partition(":")
        if not separator:
            continue
        fields[key.strip()] = value.strip()
    return fields


def _split_tags(value: str) -> tuple[str, ...]:
    return tuple(tag.strip() for tag in value.split(",") if tag.strip())


def _document(order: tuple[str, ...], values: dict[str, str], body: str) -> str:
    """The file: frontmatter in *order*, then the body, with one trailing newline.

    Empty values are written rather than omitted, so a reader never has to tell
    "absent" from "empty" and a revision's diff shows the field that stopped
    applying as a line that changed.
    """
    lines = [FENCE]
    for key in order:
        lines.append(f"{key}: {values.get(key, '')}".rstrip())
    lines.append(FENCE)
    if body.strip():
        lines.extend(("", body.strip()))
    return "\n".join(lines) + "\n"
