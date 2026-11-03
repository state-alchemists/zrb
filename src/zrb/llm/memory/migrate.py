"""Move a journal store into the memory store, once.

The journal kept one note per finding under five category directories, one
activity file per day, and a handover paragraph at the foot of a day. Memory keeps
one fact per subject, one diary entry per day, and one log line per event.

The migration is *additive*: it reads `~/.zrb/llm-notes`, writes
`~/.zrb/memory/v1`, and never touches or deletes the journal. That is deliberate —
the old store is the evidence for the new one, and a migration that destroys its
input cannot be re-run after a bug.

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
"""

from __future__ import annotations

import argparse
import os
import re
from datetime import date

from zrb.config.config import CFG
from zrb.llm.memory import paths, store
from zrb.llm.memory.model import (
    KIND_FACT,
    MAX_CLAIM_CHARS,
    MAX_FACT_BODY_CHARS,
    MAX_ID_CHARS,
    STATUS_ACTIVE,
    STATUS_RETIRED,
    Diary,
    Fact,
    id_error,
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


def migrate(journal_dir: str | None = None, dry_run: bool = False) -> dict[str, int]:
    """Copy *journal_dir* into the memory store. Returns what it wrote."""
    source = os.path.abspath(
        os.path.expanduser(journal_dir or CFG.LLM_JOURNAL_DIR or "")
    )
    counts = {"facts": 0, "retired": 0, "diary": 0, "log_lines": 0}
    if not os.path.isdir(source):
        return counts
    if not dry_run:
        paths.ensure_store()
    taken: set[str] = set()
    for category in NOTE_CATEGORIES:
        written = _migrate_category(source, category, taken, dry_run)
        counts["facts"] += written["facts"]
        counts["retired"] += written["retired"]
    counts.update(_migrate_log(source, dry_run))
    counts.update(_migrate_handovers(source, dry_run))
    if not dry_run:
        with store.locked():
            store.write_core()
            store.git_commit("migrate: journal")
    return counts


def _migrate_category(
    source: str,
    category: str,
    taken: set[str],
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
        fact = _fact_from_note(text, category, taken)
        if fact is None:
            continue
        taken.add(fact.id)
        written["retired" if fact.status == STATUS_RETIRED else "facts"] += 1
        if not dry_run:
            store.save_fact(fact)
    return written


def _fact_from_note(text: str, category: str, taken: set[str]) -> Fact | None:
    front, body = split_document(text)
    slug = front.get("slug", "").strip()
    if not slug:
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
    """The note's headline, in the order the journal itself ranked them."""
    hud_line = front.get("hud_line", "").strip()
    if hud_line:
        return _cut(hud_line, MAX_CLAIM_CHARS)
    finding = _FINDING.search(body)
    if finding:
        return _cut(_first_sentence(finding.group(1)), MAX_CLAIM_CHARS)
    title = _TITLE.search(body)
    if title:
        return _cut(title.group(1).strip(), MAX_CLAIM_CHARS)
    return ""


def _unique_id(slug: str, category: str, taken: set[str]) -> str:
    """*slug* as an id, category-prefixed when two categories share one."""
    base = _slugify(slug)
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
            if not dry_run:
                _write_log(day, lines)
            written["log_lines"] += len(lines)
    return written


def _write_log(day: str, lines: list[str]) -> None:
    content = "\n".join([f"# {day}", *(_normalise_log_line(line) for line in lines)])
    store.write_document(paths.log_path(day), content + "\n")


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
