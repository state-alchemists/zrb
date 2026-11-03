"""Move a journal store into the memory store, once.

The journal kept one note per finding under five category directories, one
activity file per day, and a handover paragraph at the foot of a day. Memory keeps
one fact per subject, one diary entry per day, and one log line per event.

The migration is *additive*: it reads the notes directory (`LLM_NOTES_DIR`,
`~/.zrb/llm-notes` by default), writes the store inside it (`memory-v1`), and
never touches or deletes the notes. That is deliberate — the old store is the
evidence for the new one, and a migration that destroys its input cannot be
re-run after a bug.

Four rules:

* **The claim is the journal's own headline.** A note's `hud_line`, else the first
  sentence of its `**Finding:**`, else the note's title. Where a hud_line is over
  the limit it is cut at a word boundary rather than rejected: losing the tail of
  a sentence is better than losing the note.
* **A retired note stays retired.** A superseded note becomes a retired fact with
  `reason: stale`, so "what did I believe" survives.
* **The handover is the diary.** A day whose file carries a handover becomes a
  diary entry with that text as the handover and its first sentence as the claim.
  A day with no handover gets no entry: deriving a claim from the log would be a
  guess wearing a date.
* **Run it twice, get the same store.** Ids are derived from slugs, dates from
  filenames, and a second run revises rather than appends.
* **What gets injected is sanitized; evidence is not.** A claim and a handover are
  read back inside a future prompt, so a journal note whose headline or handover
  carries a prompt-injection marker gets a neutral line instead of that text: the
  entry survives, the words do not. A body is never injected, so it is bounded and
  kept as it was — the alternative was discarding three hundred notes because one
  of them quoted an injection.
"""

from __future__ import annotations

import argparse
import os
import re
from datetime import date

from zrb.config.config import CFG
from zrb.llm.memory import paths, render, store
from zrb.llm.memory.model import (
    KIND_FACT,
    KIND_LOOP,
    MAX_CLAIM_CHARS,
    MAX_FACT_BODY_CHARS,
    MAX_HANDOVER_CHARS,
    MAX_ID_CHARS,
    STATUS_ACTIVE,
    STATUS_RETIRED,
    Diary,
    Fact,
    id_error,
    injection_reason,
    is_date_shaped,
    split_document,
)

NOTE_CATEGORIES = ("user", "agent", "preferences", "projects", "technical")

# A journal note's own headline, then its Finding's first sentence.
_HUD_LINE = re.compile(r"^hud_line:\s*(.+)$", re.MULTILINE)
_FINDING = re.compile(r"\*\*Finding:\*\*\s*(.+?)(?:\n\n|\Z)", re.DOTALL)
_TITLE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_LOG_LINE = re.compile(r"^- (\d{2}:\d{2}) — (.*)$")
_PROJECT = re.compile(r"·\s*project:\s*([A-Za-z0-9_.-]+)")
# The journal's own line metadata: a file list and an importance rank. Both are
# about the journal, not about what happened.
_FILES_METADATA = re.compile(r"\s+(?:·\s*)?Files:\s*.*?(?=·|$)")
_IMPORTANCE = re.compile(r"·\s*imp\s*\d+\.?\s*$")
_SUPERSEDED = "superseded"
_NOT_STATED = "not stated"

# Stand-ins for injected text that could not be carried over verbatim. The entry
# keeps its id and its body, so a human can still read what the journal said.
_WITHHELD_CLAIM = (
    "A migrated headline was withheld: its text reads as an instruction. "
    "Read the body."
)
_WITHHELD_HANDOVER = "A migrated handover was withheld: its text reads as an instruction."


def migrate(journal_dir: str | None = None, dry_run: bool = False) -> dict[str, int]:
    """Copy *journal_dir* into the memory store. Returns what it wrote."""
    source = os.path.abspath(
        os.path.expanduser(journal_dir or paths.notes_dir())
    )
    if not os.path.isdir(source):
        return {"facts": 0, "retired": 0, "diary": 0, "log_lines": 0}
    if dry_run:
        return _migrate_all(source, dry_run=True)
    paths.ensure_store()
    # One critical section for the whole copy: a reviewer running in another
    # session must not interleave with it, and the log merge below reads what it
    # is about to write.
    with store.locked():
        counts = _migrate_all(source, dry_run=False)
        unpinned, converted = _fit_core()
        counts["unpinned"] = unpinned
        counts["converted"] = converted
        store.write_core()
        store.git_commit("migrate: notes")
    return counts


def convert_if_needed() -> None:
    """Read unconverted notes into the store, once.

    Called on first use rather than by a command the user has to know about: an
    upgrade that silently starts an empty memory looks exactly like a memory that
    was lost.

    The pass is additive — it never edits or deletes a note — and it skips an id
    the store already holds, so a run interrupted by a crash continues on the
    next start rather than duplicating. The marker is written inside the same
    critical section and only after the pass, so a half-converted directory never
    claims to be converted.
    """
    if not paths.should_convert():
        return
    with store.locked():
        if paths.is_converted():
            return
        counts = _migrate_all(paths.notes_dir(), dry_run=False)
        unpinned, converted = _fit_core()
        counts["unpinned"] = unpinned
        counts["converted"] = converted
        store.write_core()
        paths.mark_converted()
        store.git_commit("memory: convert the notes on first use")


def _fit_core() -> tuple[int, int]:
    """Make the core fit the cap; return `(unpinned, converted)`.

    `remember` refuses an over-cap pin, but a migration cannot refuse: dropping
    the note would lose the knowledge it exists to carry. It shrinks the core
    instead, in two steps, from the highest id down so two runs agree:

    1. a pinned fact is unpinned — it stays searchable and out of the block;
    2. if only loops are left, the highest-id loop becomes a fact. A loop always
       renders, so there is no third step, and the claim itself is unchanged: a
       loop's text already says what is owed.
    """
    cap = CFG.LLM_MEMORY_CORE_MAX_CHARS
    unpinned = 0
    converted = 0
    while True:
        facts = store.load_facts()
        if len(render.render_core(facts)) <= cap:
            return unpinned, converted
        pinned = sorted((fact for fact in facts if fact.pin), key=lambda f: f.id)
        if pinned:
            victim = pinned[-1]
            victim.pin = False
            store.save_fact(victim)
            unpinned += 1
            continue
        loops = sorted(
            (fact for fact in facts if fact.kind == KIND_LOOP), key=lambda f: f.id
        )
        if not loops:
            return unpinned, converted
        victim = loops[-1]
        victim.kind = KIND_FACT
        store.save_fact(victim)
        converted += 1


def _migrate_all(source: str, dry_run: bool) -> dict[str, int]:
    counts = {"facts": 0, "retired": 0, "diary": 0, "log_lines": 0}
    # Two different sets, for two different reasons. `existing` is what the store
    # already holds — its claim is newer than the journal's, so the note is
    # skipped. `taken` is what this run has written, so two journal notes that
    # slugify alike still both arrive, the second under its category's prefix.
    existing = {fact.id for fact in store.load_facts(include_retired=True)}
    taken: set[str] = set()
    for category in NOTE_CATEGORIES:
        written = _migrate_category(source, category, taken, existing, dry_run)
        counts["facts"] += written["facts"]
        counts["retired"] += written["retired"]
    counts.update(_migrate_log(source, dry_run))
    counts.update(_migrate_handovers(source, dry_run))
    return counts


def _migrate_category(
    source: str,
    category: str,
    taken: set[str],
    existing: set[str],
    dry_run: bool,
) -> dict[str, int]:
    """One category's notes as facts. *taken* spans every category: an id is a
    subject, and two categories may hold one."""
    written = {"facts": 0, "retired": 0}
    directory = os.path.join(source, category)
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return written
    for name in names:
        if not name.endswith(".md") or name == "index.md":
            continue
        text = store.read_document(os.path.join(directory, name))
        fact = _fact_from_note(text, category, taken, existing)
        if fact is None:
            continue
        taken.add(fact.id)
        written["retired" if fact.status == STATUS_RETIRED else "facts"] += 1
        if not dry_run:
            store.save_fact(fact)
    return written


def _fact_from_note(
    text: str, category: str, taken: set[str], existing: set[str]
) -> Fact | None:
    front, body = split_document(text)
    slug = front.get("slug", "").strip()
    if not slug:
        return None
    # The store's own subject wins: its claim is newer than the journal's.
    if _base_id(slug) in existing:
        return None
    claim = _claim_of(front, body)
    if not claim:
        return None
    return Fact(
        id=_unique_id(slug, category, taken),
        claim=claim,
        kind=KIND_FACT,
        status=STATUS_RETIRED if front.get("status") == _SUPERSEDED else STATUS_ACTIVE,
        pin=front.get("pinned", "").strip().lower() == "true",
        tags=_tags_of(front, category),
        applies_when=_condition_of(front),
        source="migrated",
        updated=front.get("updated", "").strip() or store.now(),
        reason="stale" if front.get("status") == _SUPERSEDED else "",
        retired_on=store.today() if front.get("status") == _SUPERSEDED else "",
        body=_body_of(body),
    )


def _claim_of(front: dict[str, str], body: str) -> str:
    """The note's headline, in the order the journal itself ranked them.

    A candidate whose text reads as an instruction is skipped, so a tainted
    hud_line falls through to the Finding and then to the title. When all three
    are tainted the entry keeps a stand-in rather than being dropped.
    """
    candidates: list[str] = []
    hud_line = front.get("hud_line", "").strip()
    if hud_line:
        candidates.append(hud_line)
    finding = _FINDING.search(body)
    if finding:
        candidates.append(_first_sentence(finding.group(1)))
    title = _TITLE.search(body)
    if title:
        candidates.append(title.group(1).strip())
    for candidate in candidates:
        text = _cut(candidate, MAX_CLAIM_CHARS)
        if text and injection_reason(text) is None:
            return text
    return _WITHHELD_CLAIM if candidates else ""


def _unique_id(slug: str, category: str, taken: set[str]) -> str:
    """*slug* as an id, category-prefixed when two categories share one."""
    base = _base_id(slug)
    if base not in taken and not id_error(base):
        return base
    prefixed = _slugify(f"{category}-{slug}")
    if prefixed not in taken and not id_error(prefixed):
        return prefixed
    root = prefixed[: MAX_ID_CHARS - 3].strip("-")
    suffix = 2
    while f"{root}-{suffix}" in taken:
        suffix += 1
    return f"{root}-{suffix}"


def _base_id(slug: str) -> str:
    """A fact id for *slug* — never date-shaped.

    A date names a diary entry and nothing else; a migrated note whose slug is a
    date would otherwise create `facts/<date>.md` beside that day's entry, and
    `Forget(<date>)` would reach the fact while `Remember(<date>)` reaches the
    diary. A malformed date (`2024-02-30`) has the same shape and the same
    problem, so the test is the shape rather than a real calendar day.
    """
    base = _slugify(slug)
    return _slugify(f"fact-{slug}") if is_date_shaped(base) else base


def _slugify(value: str) -> str:
    collapsed = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return collapsed[:64].strip("-") or "note"


def _tags_of(front: dict[str, str], category: str) -> tuple[str, ...]:
    keywords = [
        word.strip()
        for word in front.get("keywords", "").split(",")
        if word.strip() and len(word.strip()) > 2
    ]
    return tuple([category, *keywords[:6]])


def _condition_of(front: dict[str, str]) -> str:
    value = front.get("applies_when", "").strip()
    return "" if value == _NOT_STATED else value


def _body_of(body: str) -> str:
    """The note without its title and its derived sections, as evidence."""
    kept: list[str] = []
    for line in body.splitlines():
        if line.startswith("## "):
            break
        kept.append(line)
    text = "\n".join(kept).strip()
    if text.startswith("# "):
        text = text.split("\n", 1)[1].strip() if "\n" in text else ""
    return text[:MAX_FACT_BODY_CHARS]


def _migrate_log(source: str, dry_run: bool) -> dict[str, int]:
    """Every activity line, one log file per day."""
    written = {"log_lines": 0}
    root = os.path.join(source, "activity-log")
    for directory, _subdirs, names in os.walk(root):
        for name in names:
            day = name.removesuffix(".md")
            if name == "index.md" or not _is_date(day):
                continue
            lines = [
                line
                for line in store.read_document(os.path.join(directory, name)).splitlines()
                if _LOG_LINE.match(line)
            ]
            if not lines:
                continue
            added = len(_new_lines(day, lines)) if dry_run else _write_log(day, lines)
            written["log_lines"] += added
    return written


def _new_lines(day: str, lines: list[str]) -> list[str]:
    """The journal lines this day's log does not already hold, normalised."""
    existing = store.log_lines(day)
    seen = set(existing)
    fresh: list[str] = []
    for line in lines:
        normalised = _normalise_log_line(line)
        if normalised in seen:
            continue
        seen.add(normalised)
        fresh.append(normalised)
    return fresh


def _write_log(day: str, lines: list[str]) -> int:
    """Merge the journal's lines into the day's log; return how many are new.

    The reviewer writes events into the same files. A migration that rewrote a
    day would delete everything the memory system had already logged for it, so
    the day is read first and only lines it does not already hold are added — and
    only those are counted, because a second run changes nothing.
    """
    fresh = _new_lines(day, lines)
    if not fresh:
        return 0
    merged = sorted(store.log_lines(day) + fresh, key=_clock_key)
    content = "\n".join([f"# {day}", *merged])
    store.write_document(paths.log_path(day), content + "\n")
    return len(fresh)


def _clock_key(line: str) -> tuple[int, int]:
    """Sort a log line by its clock time; an unstamped line goes last.

    A stable sort keeps the file's own order within one minute, so a re-run does
    not reshuffle what an earlier run wrote.
    """
    match = _LOG_LINE.match(line)
    if match is None:
        return (99, 99)
    hours, minutes = match.group(1).split(":")
    return (int(hours), int(minutes))


def _normalise_log_line(line: str) -> str:
    """`- HH:MM — text (project)`: the metadata the journal grew, dropped."""
    match = _LOG_LINE.match(line)
    if match is None:
        return line
    stamp, text = match.groups()
    project = _PROJECT.search(text)
    text = _FILES_METADATA.sub("", text)
    if project:
        text = _PROJECT.sub("", text)
    text = _IMPORTANCE.sub("", text)
    text = " ".join(text.split()).rstrip(".")
    if project:
        return f"- {stamp} — {text}. ({project.group(1)})"
    return f"- {stamp} — {text}."


def _migrate_handovers(source: str, dry_run: bool) -> dict[str, int]:
    """A day file's handover paragraph, as that day's diary entry."""
    written = {"diary": 0}
    root = os.path.join(source, "activity-log")
    for directory, _subdirs, names in os.walk(root):
        for name in names:
            day = name.removesuffix(".md")
            if name == "index.md" or not _is_date(day):
                continue
            text = store.read_document(os.path.join(directory, name))
            handover = _handover_of(text)
            if not handover:
                continue
            # The day may already have an entry, written by a session. Its claim
            # and body are newer than the journal's handover, so it is kept.
            if store.load_diary(day) is not None:
                continue
            handover = _cut(handover, MAX_HANDOVER_CHARS)
            if injection_reason(handover):
                handover = _WITHHELD_HANDOVER
                claim = _WITHHELD_CLAIM
            else:
                claim = _cut(_first_sentence(handover), MAX_CLAIM_CHARS)
            if not claim:
                continue
            if not dry_run:
                store.save_diary(
                    Diary(
                        id=day,
                        claim=claim,
                        handover=handover[:700],
                        source="migrated",
                        updated=store.now(),
                    )
                )
            written["diary"] += 1
    return written


def _handover_of(text: str) -> str:
    """The day's handover: its `## Handover` section, else prose after the log.

    The heading comes first because a day file's handover sits under one and is
    followed by derived sections (`## Backlinks`), so "everything after the last
    log line" would swallow the backlinks into the state of play.
    """
    lines = text.splitlines()
    for position, line in enumerate(lines):
        if line.strip().lower() != "## handover":
            continue
        kept: list[str] = []
        for following in lines[position + 1 :]:
            if following.startswith("## "):
                break
            kept.append(following)
        return " ".join(" ".join(kept).split())
    return _prose_after_last_line(lines)


def _prose_after_last_line(lines: list[str]) -> str:
    start = 0
    for position, line in enumerate(lines):
        if _LOG_LINE.match(line):
            start = position + 1
    kept: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        kept.append(line)
    return " ".join(" ".join(kept).split())


def _first_sentence(text: str) -> str:
    flat = " ".join(text.split())
    if not flat:
        return ""
    head = flat.split(". ")[0]
    return head if head.endswith(".") else f"{head}."


def _cut(text: str, limit: int) -> str:
    """*text* at most *limit* characters, cut at a word boundary."""
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    return flat[: limit - 1].rsplit(" ", 1)[0] + "…"


def _is_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Move a journal into the memory store.")
    parser.add_argument("--from", dest="source", default=None, help="journal directory")
    parser.add_argument("--dry-run", action="store_true", help="count, write nothing")
    arguments = parser.parse_args()
    counts = migrate(arguments.source, arguments.dry_run)
    state = "would write" if arguments.dry_run else "wrote"
    print(
        f"{state} {counts['facts']} facts, {counts['retired']} retired, "
        f"{counts['diary']} diary entries and {counts['log_lines']} log lines into "
        f"{paths.memory_dir()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
