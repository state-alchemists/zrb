"""The two shapes a memory entry takes: a fact and a diary entry.

A fact is one claim about the world, identified by its subject. A diary entry is
one day, identified by its date. Both carry a ``claim`` — the single sentence
that is rendered into the core, matched by search, and compared on revision — and
an optional body that holds the evidence and is never injected.

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

import re
from dataclasses import dataclass, field
from datetime import datetime

FENCE = "---"

MAX_ID_CHARS = 64
MAX_CLAIM_CHARS = 160
MAX_FACT_BODY_CHARS = 8_000
MAX_DIARY_BODY_CHARS = 2_000
MAX_HANDOVER_CHARS = 700

KIND_FACT = "fact"
KIND_LOOP = "loop"
KIND_DIARY = "diary"
KINDS = (KIND_FACT, KIND_LOOP, KIND_DIARY)

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
) + tuple(
    tag_form
    for tag in _CONTAINER_TAGS
    for tag_form in (f"<{tag}", f"</{tag}")
)

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


def body_error(body: str | None, kind: str) -> str | None:
    if body is None:
        return None
    limit = MAX_DIARY_BODY_CHARS if kind == KIND_DIARY else MAX_FACT_BODY_CHARS
    if len(body) > limit:
        return (
            f"The body is at most {limit} characters and this one is {len(body)}: "
            "a memory is a page, not a transcript."
        )
    reason = injection_reason(body)
    if reason:
        return f"The body cannot carry {reason}."
    return None


def handover_error(handover: str | None) -> str | None:
    if handover is None:
        return None
    if len(handover) > MAX_HANDOVER_CHARS:
        return (
            f"A handover is at most {MAX_HANDOVER_CHARS} characters and this one "
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
