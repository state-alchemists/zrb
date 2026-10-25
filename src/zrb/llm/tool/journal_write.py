"""Journal writers that own the on-disk format.

The model supplies *content*; this module derives paths, timestamps, index
entries and backlinks, which upholds these invariants by construction:

- **broken-link** — a link is only written after its target is confirmed on disk.
- **missing-backlink** — the reciprocal entry is inserted in the same call.
- **orphan** — every note is registered in its directory index, and every
  directory index is linked from the root index.
- **missing-index** — indexes are created on the way down to the leaf.
- **no lost update** — a coarse-grained lock on the root's `.lock` makes each
  writer's multi-file graph update atomic against a concurrent writer.
"""

import os
import re
import subprocess
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Annotated

from pydantic import Field

from zrb.config.config import CFG
from zrb.llm.journal_index_name import resolve_journal_index_name
from zrb.util.file_lock import FileLockTimeout, hold_file_lock
from zrb.util.markdown import get_first_heading
from zrb.util.owner_only import (
    makedirs_owner_only,
    tighten_once,
    write_text_owner_only,
)

NOTE_CATEGORIES = ("user", "agent", "preferences", "projects", "technical")
ACTIVITY_DIR = "activity-log"
_HISTORY_HEADING = "## History"
_HISTORY_MAX_ENTRIES = 3

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
# The section a durable line goes to — a constraint is a fact that must keep
# holding, not the newest headline from a category.
_CONSTRAINTS_SECTION = "Constraints"
# Their order in the index. The snapshot is capped and overflows from the end, so
# the durable sections come first; a journal written before a section existed is
# migrated into this order rather than appended after the unbounded one.
_HUD_ORDER = ("User", _CONSTRAINTS_SECTION, "Agent", "Recent")
# Sections this version renamed, and what absorbed their lines. The lines are
# moved, never dropped: a heading change must not cost a journal what it held.
_HUD_RENAMES = (("Preferences", "User"), ("Active Constraints", "Recent"))
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# A note's frontmatter says when it stops applying, and whether it already has.
# The condition is the half of a finding that lets a later session retire it
# instead of re-reading it: "safe to delete" is a claim somebody has to be able
# to check, and a finding whose expiry nobody wrote down is a finding nobody can
# retire.
_NO_APPLIES_WHEN = "not stated"
_STATUS_ACTIVE = "active"
_STATUS_SUPERSEDED = "superseded"
_BACKLINKS_HEADING = "## Backlinks"
# What makes a HUD line survive the section's cap. It travels in the index line
# itself because the capper only ever sees the index text, never the note file.
_PIN_MARKER = "📌 "


def log_activity(
    summary: Annotated[
        str,
        Field(
            description=(
                "One line of what happened. The date, time, and file path are "
                "derived here — pass only the summary itself."
            )
        ),
    ],
    files: Annotated[
        list[str] | None,
        Field(description="Paths you touched this turn, if any."),
    ] = None,
) -> str:
    """Records one line of work in the journal's activity log.

    Call this BEFORE your reply on a turn that changed files or established a
    root cause, decision, or API quirk a later session would otherwise
    rediscover; then deliver the complete answer — never end the turn on the
    "Logged to ..." result. Skip greetings, clarifying questions, refusals,
    single lookups, and anything already recorded.

    Verify before recording: a wrong entry misleads every future session, and a
    number or an absence needs its source (`wc -l: 832`, `rg: 0 hits`) or stays
    out. Unless the user asked for the write, do not announce it. Use
    WriteJournalNote when the finding must be findable by topic.
    """
    with _open_journal() as root:
        result = _log_activity_locked(root, summary, files)
        # The entry carries its own timestamp from inside the helper; this
        # label is the same minute except across a minute rollover.
        _commit_or_defer(root, f"activity: {datetime.now():%Y-%m-%d %H:%M}")
        return result


log_activity.__name__ = "LogActivity"


def _log_activity_locked(root: str, summary: str, files: list[str] | None) -> str:
    """Record the activity line under *root*, returning the tool's result.

    The caller holds the journal lock and makes the commit, so a transaction can
    call this many times for one lock and one commit."""
    now = datetime.now()
    day_file = _ensure_activity_path(root, now)
    file_note = ", ".join(files) if files else "—"
    entry = f"- {now.strftime('%H:%M')} — {summary.strip()}. Files: {file_note}."
    _insert_before_backlinks(day_file, entry)
    return f"Logged to {_posix_relpath(day_file, root)}"


def write_journal_note(
    category: Annotated[
        str,
        Field(
            description=(
                f"One of: {', '.join(NOTE_CATEGORIES)}. `user` and `agent` are "
                "who the two parties are; `preferences` is how the user wants "
                "to be worked with (the agent's own choices go under `agent`). "
                "`projects` records project context; `technical` records "
                "reusable technical findings."
            )
        ),
    ],
    slug: Annotated[
        str,
        Field(
            description=(
                "Kebab-case; becomes the filename. Reusing an existing slug "
                "overwrites that note — the previous Context/Finding is kept "
                "as one bounded History entry, not preserved in full. Call "
                "SearchJournal for this slug or topic first if you are not "
                "certain it is free or that you mean to revise it, and wait "
                "for its result before this call — don't batch the two."
            )
        ),
    ],
    title: Annotated[
        str,
        Field(
            description=(
                "Short heading for the note; also the link label used by "
                "indexes and backlinks. Retitling an existing slug relabels "
                "its index entries."
            )
        ),
    ],
    context: Annotated[str, Field(description="When the finding applies.")],
    finding: Annotated[
        str,
        Field(
            description=(
                "The durable fact itself, stated so a future session with no "
                "memory of this conversation understands it standalone."
            )
        ),
    ],
    source: Annotated[
        str, Field(description="A file:line, commit hash, or URL backing the finding.")
    ],
    links: Annotated[
        list[str] | None,
        Field(
            description=(
                "Journal-root-relative paths of related notes (e.g. "
                "`technical/retry-policy.md`); each gets a reciprocal "
                "backlink automatically."
            )
        ),
    ] = None,
    hud_line: Annotated[
        str | None,
        Field(
            description=(
                "One-line compression pinned to the injected index, under the "
                "section for this category. Pin durable identity, preferences or "
                "active constraints; the section is capped and the oldest lines "
                "past the cap are evicted and named in the result. On revision "
                "pass an updated line if the fact changed — omission retains the "
                "old pinned line. A supplied line replaces the one for this note."
            )
        ),
    ] = None,
    pinned: Annotated[
        bool,
        Field(
            description=(
                "Keep this note's hud_line through the section's cap: pinned "
                "lines are evicted only when every line in the section is "
                "pinned. Set it for a constraint or an identity that must not "
                "disappear, and leave it off for a line you may revise away. On "
                "a `projects` or `technical` note, a pinned line is also a "
                "durable constraint: it goes under `## Constraints` instead of "
                "`## Recent`."
            )
        ),
    ] = False,
    section: Annotated[
        str | None,
        Field(
            description=(
                "The index section this hud_line belongs in, when the category "
                "does not decide it: `User` (who the user is, and how they want "
                "to be worked with), `Agent` (who you are, and your own standing "
                "choices), `Constraints` (a fact that must keep holding), or "
                "`Recent` (a headline that may age out). Omit to take the "
                "category's own section."
            )
        ),
    ] = None,
    applies_when: Annotated[
        str | None,
        Field(
            description=(
                "The condition under which this note still holds — `while "
                "zrb 3.26 is the released line`, `until the pocket engine "
                "stops being the default`, `while go uses the office laptop`. "
                "Somebody has to be able to test it later, so name something "
                "checkable: a version, a file, a setting, a stated preference. "
                "It is what lets a later session retire the note instead of "
                "re-reading it; a note without one cannot be retired."
            )
        ),
    ] = None,
) -> str:
    """Records a durable finding as a topic note, findable by search later.

    Call this BEFORE your reply, then deliver the complete answer — the write
    is recordkeeping, never the result. Write every field to stand alone: a
    future session finds the note by topic, with no memory of this
    conversation.

    Prefer it to LogActivity when a later session will need the finding by
    topic: who the user is or a preference they stated (highest value, usually
    said once — record it that turn), a root cause, a decision, or an API quirk.

    Record only what this session verified: an unchecked diagnosis, or a
    comparison with something you never saw, is a guess, and a wrong entry
    misleads every session that finds it. Skip anything already recorded —
    search first when unsure.

    This tool maintains the indexes, backlinks, and git history, so never edit
    journal files directly, even to tidy up after a write: revise here or
    remove with DeleteJournalNote. Unless the user asked for the write, do not
    announce it.
    """
    with _open_journal() as root:
        result = _write_note_locked(
            root,
            category,
            slug,
            title,
            context,
            finding,
            source,
            links,
            hud_line,
            pinned,
            section,
            applies_when,
        )
        _commit_or_defer(root, f"write: {category}/{slug}")
        if not (applies_when or "").strip():
            result += (
                " No applies_when given: a note that cannot say when it stops "
                "applying cannot be retired, only re-read."
            )
        return result


write_journal_note.__name__ = "WriteJournalNote"


def supersede_journal_note(
    category: Annotated[
        str,
        Field(description=f"One of: {', '.join(NOTE_CATEGORIES)}."),
    ],
    slug: Annotated[str, Field(description="The note's slug, without `.md`.")],
    reason: Annotated[
        str,
        Field(
            description=(
                "Why it no longer applies, and the note that replaced it if "
                "one did (`superseded by the prebuffer note: the cause was "
                "decode spikes, not GIL contention`)."
            )
        ),
    ],
) -> str:
    """Retires a note whose `applies_when` no longer holds.

    The note stays on disk — a journal that deletes its evidence cannot explain
    how it got somewhere — but it leaves the injected index in the same call, so
    a false constraint cannot sit in front of a later session until somebody
    notices. Its frontmatter says `status: superseded` and its `## History` says
    why.

    Use it, not DeleteJournalNote, when the finding was right and has stopped
    being true. DeleteJournalNote is for a note that should never have existed.
    """
    with _open_journal() as root:
        result = _supersede_note_locked(root, category, slug, reason)
        _commit_or_defer(root, f"supersede: {category}/{slug}")
        return result


supersede_journal_note.__name__ = "SupersedeJournalNote"


def _write_note_locked(
    root: str,
    category: str,
    slug: str,
    title: str,
    context: str,
    finding: str,
    source: str,
    links: list[str] | None,
    hud_line: str | None,
    pinned: bool,
    section: str | None = None,
    applies_when: str | None = None,
) -> str:
    """Write the note and its index/HUD entries under *root*.

    The caller holds the lock and makes the commit. Returns exactly the string
    the tool returns, eviction note included — that is how a caller learns an
    older line under the same section lost its place."""
    _check_category(category)
    _check_slug(slug)
    targets = _resolve_links(root, links or [])
    note_path = os.path.join(root, category, f"{slug}.md")
    _write_note_file(
        note_path, slug, title, context, finding, source, targets, applies_when or ""
    )
    for target in targets:
        _add_backlink(target, note_path, title)
    _register_in_index(os.path.join(root, category, _index_name()), note_path, title)
    _register_in_index(
        os.path.join(root, _index_name()),
        note_path,
        title,
        heading="## Recent Insights",
    )
    hud_section = _hud_section_for(category, pinned, section)
    evicted = (
        _upsert_hud_line(
            root,
            hud_section,
            hud_line,
            _posix_relpath(note_path, root),
            pinned,
        )
        if hud_line
        else []
    )
    result = f"Wrote {_posix_relpath(note_path, root)}"
    if evicted:
        result += _eviction_note(hud_section, evicted)
    return result


def _hud_section_for(category: str, pinned: bool, section: str | None) -> str:
    """Which HUD section this note's line belongs in.

    The caller's own *section* wins, then firmness decides: a pinned line on a
    `projects` or `technical` note is a constraint that has to keep holding, so
    it goes to `## Constraints` rather than the rotating `## Recent`. Pinning a
    `user` or `preferences` line keeps it in `## User`, because a pinned
    identity is still an identity, not a constraint."""
    if section:
        name = section.strip().removeprefix("## ").strip()
        if name not in _HUD_ORDER:
            raise ValueError(
                f"[SYSTEM SUGGESTION]: unknown section {section!r}. "
                f"Use one of: {', '.join(_HUD_ORDER)}."
            )
        return name
    if pinned and category in ("projects", "technical"):
        return _CONSTRAINTS_SECTION
    return _HUD_SECTION[category]


def delete_journal_note(
    category: Annotated[
        str,
        Field(
            description=(
                f"One of: {', '.join(NOTE_CATEGORIES)}. `user` and `agent` are "
                "who the two parties are; `preferences` is how the user wants "
                "to be worked with, and an agent's own standing choices go "
                "under `agent`, not here."
            )
        ),
    ],
    slug: Annotated[
        str, Field(description="The note's existing filename, without `.md`.")
    ],
) -> str:
    """Deletes a note and every link to it: its category-index and Recent
    Insights entries, its pinned HUD line, and any Related/Backlinks line in
    other notes.

    There is no History fallback and you cannot undo it. Confirm the target
    first (Read it, or SearchJournal for it) rather than deleting a remembered
    or assumed slug, and wait for that result — don't batch the two. A human
    can recover the file from the journal's git history; you cannot. Unless
    the user asked for the deletion, do not announce it.
    """
    with _open_journal() as root:
        result = _delete_note_locked(root, category, slug)
        _commit_or_defer(root, f"delete: {category}/{slug}")
        return result


delete_journal_note.__name__ = "DeleteJournalNote"


def _supersede_note_locked(root: str, category: str, slug: str, reason: str) -> str:
    """Retire a note that stopped applying, under *root*.

    The caller holds the journal lock and makes the commit. The file stays —
    its evidence is why the journal can explain itself later — but its line
    leaves the injected index here and now, because a note that has stopped
    applying and still sits in every turn's context is a claim that has to be
    paid for in every turn until somebody notices."""
    _check_category(category)
    _check_slug(slug)
    note_rel = _posix_relpath(os.path.join(root, category, f"{slug}.md"), root)
    note_path = os.path.join(root, category, f"{slug}.md")
    if not os.path.isfile(note_path):
        raise ValueError(
            f"[SYSTEM SUGGESTION]: no note at {note_rel}. SearchJournal for the "
            "correct slug, or omit the supersede."
        )
    entry = f"- {datetime.now():%Y-%m-%d} — superseded: {reason.strip()}"
    text = _with_status(_read_text(note_path), _STATUS_SUPERSEDED)
    text = _append_under_heading(text, _HISTORY_HEADING, entry)
    _snapshot_before_write(note_path)
    _write_text(note_path, text)
    dropped = _remove_note_hud_line(root, note_rel)
    result = f"Superseded {note_rel}: {reason.strip()}"
    if dropped:
        result += f" Removed from the index: {dropped[0].strip()}"
    return result


def _with_status(text: str, status: str) -> str:
    """*text* with its frontmatter `status:` set to *status*."""
    if re.search(r"(?m)^status: ", text):
        return re.sub(r"(?m)^status: .*$", f"status: {status}", text, count=1)
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        return "\n".join([lines[0], f"status: {status}", *lines[1:]]) + "\n"
    return f"---\nstatus: {status}\n---\n{text}"


def _remove_note_hud_line(root: str, note_rel: str) -> list[str]:
    """Drop *note_rel*'s line from every HUD section, returning what went."""
    own = f" ([note]({note_rel}))"
    index_path = os.path.join(root, _index_name())
    current = _read_text(index_path)
    lines = current.splitlines()
    dropped: list[str] = []
    for name in _HUD_ORDER:
        heading = f"## {name}"
        if heading not in lines:
            continue
        start, end = _section_bounds(lines, heading)
        body = lines[start:end]
        kept = [line for line in body if not line.rstrip().endswith(own)]
        dropped.extend(line for line in body if line.rstrip().endswith(own))
        if len(kept) != len(body):
            lines = [*lines[:start], *kept, *lines[end:]]
    if dropped:
        _write_text(index_path, "\n".join(lines) + "\n")
    return dropped


def _delete_note_locked(root: str, category: str, slug: str) -> str:
    """Delete the note and every link to it under *root*.

    The caller holds the journal lock and makes the commit."""
    _check_category(category)
    _check_slug(slug)
    note_path = os.path.join(root, category, f"{slug}.md")
    if not os.path.isfile(note_path):
        raise ValueError(
            f"[SYSTEM SUGGESTION]: no note at {category}/{slug}.md. "
            "SearchJournal for the correct slug, or omit the delete."
        )
    _scrub_links_to(root, note_path)
    _snapshot_before_write(note_path)
    os.remove(note_path)
    return f"Deleted {_posix_relpath(note_path, root)}"


@contextmanager
def journal_transaction(
    message: str | None = None,
) -> Iterator["JournalTransaction"]:
    """Make many journal changes under one lock and one commit.

    The Python seam a script or an import needs: batching used to mean reaching
    past the tools into the private helpers, because a tool called inside
    another write waited out the lock timeout against a lock its own thread
    held. A journal tool called inside this block now re-enters the lock its
    caller holds, so both shapes work; this one is still the better shape for a
    batch, since it commits once instead of once per call. This is not a
    model-facing tool — the model keeps writing one note per call, because each
    of its writes has to be confirmed by its own result.

    *message* is the commit's subject; with none, the commit counts the
    changes. A body that raises makes no commit: every file it touched is put
    back as it was — the bytes it held, or its absence — and the exception
    carries on. The snapshot is taken by the writes themselves rather than from
    git, because git has no baseline for an ignored or untracked note, and
    because `_open_journal` migrates an older root index before the body runs.
    A file the body never touched is left alone, however dirty the journal was.
    The snapshot starts once the journal is open, so the tree and repository
    `_open_journal` sets up — and the root index it migrates — are setup rather
    than part of the body: a failed body never leaves a first-time journal
    half-built, and never deletes a file setup created.

    With zero changes, nothing is committed. `SearchJournal` does not take the
    journal lock, so a long transaction is visible mid-flight — the same grain
    a run of individual calls has.

    Not nestable, and it says so rather than pretending: the snapshot is one per
    thread, so a nested block would start by discarding the outer one's, and the
    outer body's later failure could no longer put back what it had changed. A
    helper that wants to batch should take the transaction it is given, or call
    the journal tools, whose changes ride this block's single commit.
    """
    if getattr(_lock_state, "in_transaction", 0):
        raise ValueError(
            "[SYSTEM SUGGESTION]: journal_transaction is already open on this "
            "thread, and nested transactions cannot honour both blocks' "
            "rollback — the snapshot is one per thread — so this call wrote "
            "nothing. Use the transaction you were given, or call the journal "
            "tools, whose changes ride the outer block's commit."
        )
    with _open_journal() as root:
        transaction = JournalTransaction(root)
        _lock_state.in_transaction = 1
        _lock_state.deferred_changes = 0
        _begin_snapshot()
        try:
            yield transaction
        except BaseException:
            _restore_snapshots(_take_snapshot())
            raise
        finally:
            _lock_state.in_transaction = 0
            _take_snapshot()
        # A tool called inside the body counted its change here instead of
        # committing it; the whole body still makes one commit, at the end.
        changes = transaction.change_count + getattr(_lock_state, "deferred_changes", 0)
        _lock_state.deferred_changes = 0
        if changes:
            _git_commit(root, message or f"batch: {changes} change(s)")


class JournalTransaction:
    """The changes made inside one `journal_transaction`.

    Each method is the lock-free, commit-free half of the matching tool, so it
    returns the same string the tool would and adds one to `change_count`.
    Never build one directly: `journal_transaction` owns the lock and the
    commit, and the object is only valid inside the `with` block it opens.
    """

    def __init__(self, root: str) -> None:
        self._root = root
        self.change_count = 0

    def log_activity(self, summary: str, files: list[str] | None = None) -> str:
        """Record one activity line; the whole batch commits at exit."""
        return self._record(_log_activity_locked(self._root, summary, files))

    def write_note(
        self,
        category: str,
        slug: str,
        title: str,
        context: str,
        finding: str,
        source: str,
        links: list[str] | None = None,
        hud_line: str | None = None,
        pinned: bool = False,
        section: str | None = None,
        applies_when: str | None = None,
    ) -> str:
        """Write one note; the whole batch commits at exit."""
        return self._record(
            _write_note_locked(
                self._root,
                category,
                slug,
                title,
                context,
                finding,
                source,
                links,
                hud_line,
                pinned,
                section,
                applies_when,
            )
        )

    def delete_note(self, category: str, slug: str) -> str:
        """Delete one note; the whole batch commits at exit."""
        return self._record(_delete_note_locked(self._root, category, slug))

    def _record(self, result: str) -> str:
        self.change_count += 1
        return result


#: Files the running transaction has already touched, and their bytes before the
#: touch (`None` for a file that did not exist). One at a time is enough: the
#: journal lock admits one writer, and this is only set inside its body.
_SNAPSHOT: "dict[str, bytes | None] | None" = None


def _begin_snapshot() -> None:
    global _SNAPSHOT
    _SNAPSHOT = {}


def _take_snapshot() -> dict[str, bytes | None]:
    """Return what the body has touched so far, and stop recording."""
    global _SNAPSHOT
    taken = _SNAPSHOT or {}
    _SNAPSHOT = None
    return taken


def _snapshot_before_write(path: str) -> None:
    """Remember *path*'s bytes the first time the running body touches it.

    Bytes rather than a git baseline, because git has none for an ignored or
    untracked file: a note matching a `.gitignore` rule can be overwritten and
    `git reset` will never bring it back. A file that cannot be read is not
    recorded, so a failed restore leaves it as the body wrote it rather than
    truncating it with bytes this call never saw.
    """
    if _SNAPSHOT is None or path in _SNAPSHOT:
        return
    try:
        with open(path, "rb") as handle:
            _SNAPSHOT[path] = handle.read()
    except FileNotFoundError:
        _SNAPSHOT[path] = None
    except OSError:
        return


def _restore_snapshots(snapshot: dict[str, bytes | None]) -> None:
    """Put every touched file back: its bytes, or its absence. Best effort.

    Silent on a file it cannot restore, like `_git_commit`: the journal's own
    history still holds what the body was about to change.
    """
    for path, content in snapshot.items():
        try:
            if content is None:
                if os.path.isfile(path):
                    os.remove(path)
                continue
            with open(path, "wb") as handle:
                handle.write(content)
        except OSError:
            continue


def _scrub_links_to(root: str, target_path: str) -> None:
    """Drop every `- [title](path)` or HUD `([note](path))` line elsewhere in
    *root* that resolves to *target_path*.

    The label is matched greedily since a title may contain `]`;
    the end-anchored target always finds the last link on the line.

    A full-tree scan per delete; add an index if the journal grows large.
    """
    link_re = re.compile(r"^- (?:\[.*\]\(([^)]+)\)|.*\(\[note\]\(([^)]+)\)\))\s*$")
    target_abs = os.path.abspath(target_path)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for filename in filenames:
            if not filename.endswith(".md"):
                continue
            file_path = os.path.join(dirpath, filename)
            if os.path.abspath(file_path) == target_abs:
                continue
            text = _read_text(file_path)
            if not text:
                continue
            changed = False
            kept: list[str] = []
            for line in text.splitlines():
                match = link_re.match(line)
                if match:
                    resolved = os.path.abspath(
                        os.path.join(
                            os.path.dirname(file_path),
                            match.group(1) or match.group(2),
                        )
                    )
                    if resolved == target_abs:
                        changed = True
                        continue
                kept.append(line)
            if changed:
                _write_text(file_path, "\n".join(kept).rstrip() + "\n")


# Whether this thread holds the journal lock, so a journal tool called from
# inside another journal write re-enters instead of waiting out the timeout
# against its own lock. `in_transaction` counts the `journal_transaction`
# bodies this thread is inside, and `deferred_changes` counts the changes a
# tool made there and left for the transaction's single commit.
_lock_state = threading.local()


def _commit_or_defer(root: str, message: str) -> None:
    """Commit now, or hand the change to the open transaction.

    `journal_transaction` promises one commit and none at all when its body
    raises. A tool called inside that body used to commit straight away, which
    broke both halves: the rollback restored the files but the commit stayed in
    history, and the transaction then committed again at exit. The change is
    counted here instead, and rides the transaction's single commit.
    """
    if getattr(_lock_state, "in_transaction", 0):
        _lock_state.deferred_changes = getattr(_lock_state, "deferred_changes", 0) + 1
        return
    _git_commit(root, message)


@contextmanager
def _open_journal() -> Iterator[str]:
    """Yield the journal root with its tree in place, the lock held, and git
    initialized when `LLM_JOURNAL_GIT_ENABLED`."""
    root = ensure_journal_tree()
    if getattr(_lock_state, "depth", 0):
        # This thread already holds the root lock — a tool called from inside a
        # journal write, or a transaction body that logs. Re-entering is safe:
        # nothing else can interleave while the outermost call holds it, and
        # waiting for it would burn the whole timeout and then fail against
        # this thread's own lock.
        _lock_state.depth += 1
        try:
            yield root
        finally:
            _lock_state.depth -= 1
        return
    # One root lock makes the multi-file update atomic against concurrent writers.
    try:
        with hold_file_lock(
            os.path.join(root, ".lock"),
            timeout=max(0.0, CFG.LLM_JOURNAL_LOCK_TIMEOUT),
        ):
            _lock_state.depth = 1
            try:
                _migrate_root_index(root)
                if CFG.LLM_JOURNAL_GIT_ENABLED:
                    _ensure_journal_git(root)
                yield root
            finally:
                _lock_state.depth = 0
    except FileLockTimeout as exc:
        raise ValueError(
            "[SYSTEM SUGGESTION]: journal is busy; another writer held "
            f"{os.path.join(root, '.lock')} for the whole "
            f"{max(0.0, CFG.LLM_JOURNAL_LOCK_TIMEOUT)}s allowed by "
            "LLM_JOURNAL_LOCK_TIMEOUT, so this call wrote nothing. Retry once "
            "the other writer is done, or raise that setting if journal writes "
            "are legitimately slow here."
        ) from exc


def _migrate_root_index(root: str) -> None:
    """Bring the root index up to the skeleton this version writes, lock held.

    Three things an older journal is missing: a renamed HUD section's lines in
    the section that absorbed it, a HUD section that did not exist (a named
    constraint beside the rotating headlines), and the category's link in
    `## Directories`. A read-modify-write, so it belongs where the lock is:
    reading the index before `hold_file_lock` let a writer write back a copy
    taken before another writer added its line, losing that line on both sides
    of a successful call.
    """
    root_index = os.path.join(root, _index_name())
    current = _read_text(root_index)
    migrated = _ensure_directory_links(
        _ensure_hud_sections(_absorb_renamed_sections(current))
    )
    if migrated != current:
        _write_text(root_index, migrated)


def _absorb_renamed_sections(text: str) -> str:
    """Move a renamed HUD section's lines into the section that absorbed them.

    `## Preferences` is now `## User` (it mixed what the user is like with the
    agent's own standing rules, so the heading claimed one owner and held two)
    and `## Active Constraints` is now `## Recent` (a rotating queue of newest
    headlines under a name that promised constraints). The lines are moved, in
    order, after what the target already held: a renamed heading must not cost
    the journal an entry. Running it twice changes nothing.
    """
    renamed, sections = _split_index_sections(text)
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
    ordered = [name for name in _HUD_ORDER if name in bodies]
    ordered += [name for name in order if name not in _HUD_ORDER]
    return _join_index_sections(renamed, [(name, bodies[name]) for name in ordered])


def _split_index_sections(text: str) -> "tuple[list[str], list[tuple[str, list[str]]]]":
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


def _join_index_sections(
    preamble: list[str], sections: "list[tuple[str, list[str]]]"
) -> str:
    """Render an index in the shape `_root_index_skeleton` writes."""
    parts = ["\n".join(preamble).rstrip("\n"), "\n"]
    for name, body in sections:
        content = "\n".join(body).strip("\n")
        parts.append(f"\n## {name}\n")
        if content:
            parts.append(f"\n{content}\n")
    return "".join(parts)


def _check_category(category: str) -> None:
    if category not in NOTE_CATEGORIES:
        raise ValueError(
            f"[SYSTEM SUGGESTION]: unknown category {category!r}. "
            f"Use one of: {', '.join(NOTE_CATEGORIES)}."
        )


def _check_slug(slug: str) -> None:
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


def ensure_journal_tree() -> str:
    """Create the journal root, its six directories, and their indexes.

    Only what is missing: an existing index is never rewritten here, since the
    lock is not held yet. `_migrate_root_index` does the rewriting, under it.
    A configured `LLM_JOURNAL_INDEX_FILE` names the indexes created here, so a
    journal written under a different name keeps its files and gains fresh ones.
    """
    journal_dir = CFG.LLM_JOURNAL_DIR
    if not journal_dir:
        raise ValueError(
            "[SYSTEM SUGGESTION]: journal directory is not configured "
            "(LLM_JOURNAL_DIR is unset). Report this rather than retrying."
        )
    root = os.path.abspath(os.path.expanduser(journal_dir))
    _makedirs_owner_only(root)
    index_name = _index_name()
    for name in (*NOTE_CATEGORIES, ACTIVITY_DIR):
        _makedirs_owner_only(os.path.join(root, name))
        _write_if_absent(
            os.path.join(root, name, index_name),
            f"# {name.replace('-', ' ').title()}\n",
        )
    _write_if_absent(os.path.join(root, index_name), _root_index_skeleton())
    # A journal written before the private-mode rule keeps its old modes; this
    # narrows it once, and is a no-op on every later call. Run last, so a
    # first-time tree is narrowed only once every descendant it creates above
    # already exists — the marker it writes never claims a half-hardened tree.
    # Only the entries this function itself just created or confirmed are
    # named: LLM_JOURNAL_DIR is a directory the user configures directly, and
    # may already hold content that belongs to something else entirely — the
    # root's own mode, and anything in it zrb did not just account for, are
    # left exactly as they are.
    tighten_once(root, owned_entries=(*NOTE_CATEGORIES, ACTIVITY_DIR, index_name))
    return root


def _ensure_journal_git(root: str) -> None:
    """Best-effort `git init` of the journal root. Never raises.

    Callers must hold the journal lock, or two first-time writers race."""
    if os.path.isdir(os.path.join(root, ".git")):
        return
    try:
        subprocess.run(
            ["git", "init", "--quiet", root],
            capture_output=True,
            check=False,
            timeout=CFG.LLM_GIT_CMD_TIMEOUT / 1000,
        )
    except (OSError, subprocess.SubprocessError):
        return
    _write_if_absent(os.path.join(root, ".gitignore"), ".lock\n")
    _git_commit(root, "init: journal tree")


def _git_commit(root: str, message: str) -> None:
    """Best-effort `git add -A && git commit` in *root*; silent on any failure.

    Inline `-c user.*` so no global git identity is needed."""
    if not os.path.isdir(os.path.join(root, ".git")):
        return
    git_identity = ["-c", "user.name=zrb-journal", "-c", "user.email=journal@zrb.local"]
    timeout = CFG.LLM_GIT_CMD_TIMEOUT / 1000
    try:
        subprocess.run(
            ["git", "-C", root, *git_identity, "add", "-A"],
            capture_output=True,
            check=False,
            timeout=timeout,
        )
        subprocess.run(
            [
                "git",
                "-C",
                root,
                *git_identity,
                "commit",
                "-m",
                message,
                "--allow-empty-message",
                "--quiet",
            ],
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        # Includes TimeoutExpired (GPG-sign prompt, stale index.lock).
        return


def _root_index_skeleton() -> str:
    index_name = _index_name()
    directories = " · ".join(
        f"[{name}]({name}/{index_name})" for name in (*NOTE_CATEGORIES, ACTIVITY_DIR)
    )
    # Order is load-bearing: the injected snapshot is capped and overflows from
    # the end, so the unbounded section goes last and evicts only itself.
    sections = "".join(f"## {name}\n\n" for name in _HUD_ORDER)
    return (
        "# Journal\n\n"
        f"{sections}"
        f"## Directories\n\n- {directories}\n\n"
        "## Recent Insights\n"
    )


def _ensure_hud_sections(text: str) -> str:
    """Add any HUD section this index predates, at its place in `_HUD_ORDER`.

    A journal created before a category existed keeps its old skeleton —
    `_write_if_absent` never rewrites an index — and appending the new heading at
    the end would put it after `## Recent Insights`, where the capped snapshot
    evicts it first.
    """
    for name in _HUD_ORDER:
        if f"## {name}" not in text.splitlines():
            text = _insert_section_in_order(text, name)
    return text


def _ensure_directory_links(text: str) -> str:
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
    link_re = _directory_link_re()
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() != "## Directories":
            continue
        bullet_at = next(
            (
                offset
                for offset in range(index + 1, len(lines))
                if lines[offset].startswith("- ")
            ),
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
            rewritten = _insert_directory_link(rewritten, name, expected)
        lines[bullet_at] = rewritten
        rebuilt = "\n".join(lines)
        return rebuilt + "\n" if text.endswith("\n") else rebuilt
    return text


def _insert_directory_link(line: str, name: str, expected: list[str]) -> str:
    """Add the category's index link before the first link that must follow it."""
    token = f"[{name}]({name}/{_index_name()})"
    for match in _directory_link_re().finditer(line):
        target = match.group(2)
        if target not in expected:
            continue
        if expected.index(target) > expected.index(name):
            return f"{line[: match.start()]}{token} · {line[match.start() :]}"
    if line.strip() == "-":
        return f"- {token}"
    return f"{line} · {token}"


def _insert_section_in_order(text: str, name: str) -> str:
    """Insert an empty ``## name`` before the next heading that must follow it."""
    heading = f"## {name}"
    later = [f"## {other}" for other in _HUD_ORDER]
    later += ["## Directories", "## Recent Insights"]
    stop = later[later.index(heading) + 1 :] if heading in later else later
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line in stop:
            head = lines[:index]
            if head and head[-1].strip():
                head = [*head, ""]
            return "\n".join([*head, heading, "", *lines[index:]])
    return f"{text.rstrip()}\n\n{heading}\n"


def _ensure_activity_path(root: str, now: datetime) -> str:
    """Create year/month/day indexes down to the day file, linking each level."""
    year, month, day = (
        now.strftime("%Y"),
        now.strftime("%Y-%m"),
        now.strftime("%Y-%m-%d"),
    )
    index_name = _index_name()
    activity = os.path.join(root, ACTIVITY_DIR)
    year_dir = os.path.join(activity, year)
    month_dir = os.path.join(year_dir, month)
    _makedirs_owner_only(month_dir)
    _write_if_absent(os.path.join(year_dir, index_name), f"# {year}\n")
    _write_if_absent(os.path.join(month_dir, index_name), f"# {month}\n")
    _register_link(os.path.join(activity, index_name), f"{year}/{index_name}", year)
    _register_link(os.path.join(year_dir, index_name), f"{month}/{index_name}", month)
    _register_link(os.path.join(month_dir, index_name), f"{day}.md", day)
    day_file = os.path.join(month_dir, f"{day}.md")
    _write_if_absent(
        day_file,
        f"# {day}\n\n{_BACKLINKS_HEADING}\n\n- [month index]({index_name})\n",
    )
    return day_file


def _write_note_file(
    note_path: str,
    slug: str,
    title: str,
    context: str,
    finding: str,
    source: str,
    targets: list[str],
    applies_when: str = "",
) -> None:
    """Write the note, merging (never dropping) the existing ``## Backlinks``
    and ``## Related`` links, and appending the superseded Context/Finding to
    ``## History`` (capped at ``_HISTORY_MAX_ENTRIES``).

    *applies_when* is the condition under which the finding still holds. It
    lives in the frontmatter rather than the prose because a later session has
    to be able to *test* it: a note nobody can say the expiry of is a note
    nobody can retire."""
    history = _merge_entries(
        _entries_under(note_path, _HISTORY_HEADING), _prior_revision_entry(note_path)
    )
    if len(history) > _HISTORY_MAX_ENTRIES:
        history = history[-_HISTORY_MAX_ENTRIES:]
    related = _merge_entries(
        _entries_under(note_path, "## Related"),
        [
            f"- [{_title_of(target)}]({_posix_relpath(target, os.path.dirname(note_path))})"
            for target in targets
        ],
    )
    # The directory index is always the first backlink.
    backlinks = _merge_entries(
        _entries_under(note_path, _BACKLINKS_HEADING),
        [f"- [index]({_index_name()})"],
    )
    lines = [
        "---",
        f"slug: {slug}",
        f"applies_when: {applies_when.strip() or _NO_APPLIES_WHEN}",
        f"status: {_STATUS_ACTIVE}",
        "---",
        f"# {title}",
        "",
        f"**Context:** {context}",
        f"**Finding:** {finding}",
        f"**Source:** {source}",
        "",
    ]
    if history:
        lines.append(_HISTORY_HEADING)
        lines.append("")
        lines.extend(history)
        lines.append("")
    if related:
        lines.append("## Related")
        lines.append("")
        lines.extend(related)
        lines.append("")
    lines.append(_BACKLINKS_HEADING)
    lines.append("")
    lines.extend(backlinks)
    lines.append("")
    _write_text(note_path, "\n".join(lines))


def _entries_under(path: str, heading: str) -> list[str]:
    """The `- ` lines under *heading* in *path*, or `[]`."""
    lines = _read_text(path).splitlines()
    if heading not in lines:
        return []
    start, end = _section_bounds(lines, heading)
    return [line for line in lines[start:end] if line.startswith("- ")]


def _merge_entries(existing: list[str], new: list[str]) -> list[str]:
    """Existing entries in their original order, then any genuinely new ones."""
    merged = list(existing)
    for entry in new:
        if entry not in merged:
            merged.append(entry)
    return merged


def _resolve_links(root: str, links: list[str]) -> list[str]:
    """Turn journal-relative link paths into absolute ones, rejecting misses."""
    resolved: list[str] = []
    for link in links:
        candidate = os.path.abspath(os.path.join(root, link))
        if not _is_inside(candidate, root):
            raise ValueError(
                f"[SYSTEM SUGGESTION]: link {link!r} points outside the journal. "
                "Use a path relative to the journal root."
            )
        if not os.path.isfile(candidate):
            raise ValueError(
                f"[SYSTEM SUGGESTION]: link target {link!r} does not exist. "
                "SearchJournal for the correct path, or omit the link."
            )
        resolved.append(candidate)
    return resolved


def _is_inside(path: str, parent: str) -> bool:
    return path == parent or path.startswith(f"{parent}{os.sep}")


def _index_name() -> str:
    """Filename of every index this module writes: the root's and each category's.

    The reader (`render_journal_index`) resolves the root index from the same
    knob through the same `resolve_journal_index_name` check, so a name that
    only one side honored or validated left the written index uninjectable —
    or, unvalidated, let the reader be pointed outside the journal entirely.
    """
    return resolve_journal_index_name(CFG.LLM_JOURNAL_INDEX_FILE)


def _directory_link_re() -> re.Pattern[str]:
    """`[label](<category>/<index file>)`, the links `## Directories` carries."""
    return re.compile(rf"\[([^\]]*)\]\(([^)]*)/{re.escape(_index_name())}\)")


def _posix_relpath(path: str, start: str) -> str:
    """`os.path.relpath` with `/` separators, for portable markdown links."""
    return os.path.relpath(path, start).replace(os.sep, "/")


def _add_backlink(target: str, source_path: str, source_title: str) -> None:
    rel = _posix_relpath(source_path, os.path.dirname(target))
    entry = f"- [{source_title}]({rel})"
    text = _read_text(target)
    if entry in text:
        return
    if _BACKLINKS_HEADING not in text:
        text = f"{text.rstrip()}\n\n{_BACKLINKS_HEADING}\n"
    _write_text(target, f"{text.rstrip()}\n{entry}\n")


def _register_in_index(
    index_path: str, note_path: str, title: str, heading: str | None = None
) -> None:
    rel = _posix_relpath(note_path, os.path.dirname(index_path))
    _register_link(index_path, rel, title, heading=heading)


def _register_link(
    index_path: str, rel_target: str, label: str, heading: str | None = None
) -> None:
    """Append `- [label](rel_target)` to an index, under *heading* if given.

    An existing entry for the target is relabelled in place; duplicates are dropped.
    """
    entry = f"- [{label}]({rel_target})"
    text = _read_text(index_path)
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
        updated = "\n".join(kept) + "\n"
        if updated != text:
            _write_text(index_path, updated)
        return
    if heading is None:
        body = text.rstrip()
        gap = "\n" if body.rsplit("\n", 1)[-1].startswith("- ") else "\n\n"
        _write_text(index_path, f"{body}{gap}{entry}\n")
        return
    _write_text(index_path, _append_under_heading(text, heading, entry))


def _append_under_heading(text: str, heading: str, entry: str) -> str:
    lines = text.splitlines()
    if heading not in lines:
        return f"{text.rstrip()}\n\n{heading}\n\n{entry}\n"
    start, end = _section_bounds(lines, heading)
    body = [line for line in lines[start:end] if line.strip()]
    body.append(entry)
    return "\n".join([*lines[:start], "", *body, "", *lines[end:]]).rstrip() + "\n"


def _section_bounds(lines: list[str], heading: str) -> tuple[int, int]:
    """`[start, end)` of the body under *heading*, up to the next `## `."""
    start = lines.index(heading) + 1
    end = start
    while end < len(lines) and not lines[end].startswith("## "):
        end += 1
    return start, end


def _upsert_hud_line(
    root: str, section: str, line: str, note_rel: str, pinned: bool = False
) -> list[str]:
    """Pin *line* under *section*, replacing any earlier line from the same note.

    Lines are keyed by their trailing note link; an unlinked line is replaced
    only when identical to the new one. A supplied line that already carries a
    note link — a revision may repeat the line as it was read in the index —
    has it stripped first, so the note is pinned once. Any pin marker in what
    the caller passed is stripped too: whether the line is pinned is decided by
    *pinned*, not by text the caller may have echoed back from the index.

    Returns whatever the section's cap evicted, in its original order.
    """
    own = f" ([note]({note_rel}))"
    text = _hud_line_text(line, own)
    entry = f"{_with_pin_marker(f'- {text}', pinned)}{own}"
    index_path = os.path.join(root, _index_name())
    current = _read_text(index_path)
    if entry in current.splitlines():
        return []
    # A note has one line, in one section: re-filing it under a new section
    # (a line that turns out to be a constraint, a preference that was really
    # the agent's own rule) must move it, not copy it.
    current = _drop_from_other_hud_sections(current, section, own, text)
    heading = f"## {section}"
    lines = current.splitlines()
    if heading in lines:
        start, end = _section_bounds(lines, heading)
        body = lines[start:end]
        if _is_echoed_line(text, [ln for ln in body if ln.strip()]):
            text = _hud_text_without_links(text)
            entry = f"{_with_pin_marker(f'- {text}', pinned)}{own}"
        kept = [ln for ln in body if not _is_own_hud_line(ln, own, text)]
        current = "\n".join([*lines[:start], *kept, *lines[end:]]) + "\n"
    current = _append_under_heading(current, heading, entry)
    current, evicted = _cap_section_entries(
        current, heading, CFG.LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION
    )
    _write_text(index_path, current)
    return evicted


def _drop_from_other_hud_sections(
    text: str, section: str, own: str, line_text: str
) -> str:
    """Remove this note's line from every HUD section but *section*.

    Matching is `_is_own_hud_line`'s, so the note's line is found by its link
    even though the prose changed, and another note's line that quotes the same
    words is left alone."""
    for name in _HUD_ORDER:
        if name == section:
            continue
        heading = f"## {name}"
        lines = text.splitlines()
        if heading not in lines:
            continue
        start, end = _section_bounds(lines, heading)
        body = lines[start:end]
        kept = [line for line in body if not _is_own_hud_line(line, own, line_text)]
        if len(kept) == len(body):
            continue
        text = "\n".join([*lines[:start], *kept, *lines[end:]]) + "\n"
    return text


def _hud_line_text(line: str, own: str) -> str:
    """The line's own text: no bullet, no pin marker, no link to this note.

    Links to other notes are left intact."""
    text = line.strip().removeprefix("- ").strip()
    text = text.removeprefix(_PIN_MARKER).strip()
    while text.endswith(own):
        text = text.removesuffix(own).rstrip()
    return text


def _with_pin_marker(base: str, pinned: bool) -> str:
    """Prefix *base* with the pin marker when *pinned*, else leave it alone."""
    if not pinned:
        return base
    return f"- {_PIN_MARKER}{base.removeprefix('- ')}"


_HUD_NOTE_LINK_RE = re.compile(r"\(\[note\]\([^)]*\)\)\s*$")


def _hud_text_without_links(line: str) -> str:
    """*line*'s prose with the bullet, a pin marker and any note links removed."""
    text = line.strip().removeprefix("- ").strip()
    text = text.removeprefix(_PIN_MARKER).strip()
    while True:
        match = _HUD_NOTE_LINK_RE.search(text)
        if not match:
            return text.rstrip()
        text = text[: match.start()].rstrip()


def _is_echoed_line(text: str, existing: list[str]) -> bool:
    """Whether *text* is a line read back from this section, its link included.

    A caller may hand back the line it read in the index; that trailing
    `([note](…))` is the index's, not content, and copying it onto the new line
    would point the new note at the old one. A line the caller wrote itself may
    legitimately end in a link to another note ("See also …"), so the index
    decides: only text that reproduces an existing line's prose *and* its link
    is an echo.
    """
    match = _HUD_NOTE_LINK_RE.search(text)
    if not match:
        return False
    link = match.group(0).strip()
    prose = text[: match.start()].rstrip()
    return any(
        line.rstrip().endswith(link) and _hud_text_without_links(line) == prose
        for line in existing
    )


def _is_own_hud_line(line: str, own: str, text: str) -> bool:
    """True when *line* is this note's pin, or an unlinked copy of *text*.

    A revision keeps one line per note, so the note's own line is matched by its
    link even when the text changed. Matching by text covers a copy that carries
    no link yet — but only then: a line linked to a *different* note stays, even
    when both notes pinned exactly the same words, because that line is how the
    other note is reached from the index.
    """
    stripped = line.rstrip()
    if stripped.endswith(own):
        return True
    if _HUD_NOTE_LINK_RE.search(stripped):
        return False
    return _hud_line_text(line, own) == text


def _is_pinned_line(line: str) -> bool:
    """True when *line* carries the pin marker the cap must not evict first."""
    return line.lstrip().startswith(f"- {_PIN_MARKER}")


def _cap_section_entries(
    text: str, heading: str, max_entries: int
) -> tuple[str, list[str]]:
    """Keep the newest *max_entries* lines under *heading* (`<= 0` uncapped).

    For HUD sections only; catalogs like `Recent Insights` stay complete.
    Returns the text and the lines it dropped, in their original order, so the
    caller can report a loss instead of the write quietly succeeding."""
    if max_entries <= 0:
        return text, []
    lines = text.splitlines()
    if heading not in lines:
        return text, []
    start, end = _section_bounds(lines, heading)
    body = [line for line in lines[start:end] if line.strip()]
    if len(body) <= max_entries:
        return text, []
    body, evicted = _split_by_pin(body, max_entries)
    capped = "\n".join([*lines[:start], "", *body, "", *lines[end:]])
    return capped.rstrip() + "\n", evicted


def _split_by_pin(body: list[str], max_entries: int) -> tuple[list[str], list[str]]:
    """Drop the oldest unpinned lines down to *max_entries*; return kept, dropped.

    A pinned line goes only when every line in the section is pinned, so a
    section of pinned constraints may stay over the cap rather than lose one.
    """
    is_pinned = [_is_pinned_line(line) for line in body]
    if all(is_pinned):
        return body[-max_entries:], body[:-max_entries]
    evictable = [index for index, pinned in enumerate(is_pinned) if not pinned]
    dropped = set(evictable[: len(body) - max_entries])
    kept = [line for index, line in enumerate(body) if index not in dropped]
    evicted = [line for index, line in enumerate(body) if index in dropped]
    return kept, evicted


def _eviction_note(section: str, evicted: list[str]) -> str:
    """Say what the section's cap dropped, and how to keep a line next time.

    The write used to report success while an older pinned constraint vanished;
    the model can only re-pin what it is told about. The list bullet is dropped
    from each line so the quote reads as the line itself."""
    lines = ", ".join(f'"{line.removeprefix("- ")}"' for line in evicted)
    cap = CFG.LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION
    return (
        f". Evicted from ## {section} (cap {cap}): {lines} — re-pin with "
        "pinned=True or raise LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION."
    )


def _insert_before_backlinks(path: str, entry: str) -> None:
    """Append an entry above the trailing Backlinks block, which stays last."""
    text = _read_text(path)
    if entry in text:
        return
    if _BACKLINKS_HEADING not in text:
        _write_text(path, f"{text.rstrip()}\n{entry}\n")
        return
    head, _, tail = text.partition(_BACKLINKS_HEADING)
    _write_text(path, f"{head.rstrip()}\n{entry}\n\n{_BACKLINKS_HEADING}{tail}")


def _prior_revision_entry(note_path: str) -> list[str]:
    """The current Context/Finding as a dated `## History` bullet, or `[]`."""
    text = _read_text(note_path)
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


def _title_of(path: str) -> str:
    return (
        get_first_heading(_read_text(path))
        or os.path.splitext(os.path.basename(path))[0]
    )


def _makedirs_owner_only(path: str) -> None:
    """`makedirs_owner_only`, with a journal-specific, model-facing message.

    The shared helper raises a bare `PermissionError` naming the offending
    path; this translates it into the `[SYSTEM SUGGESTION]` convention every
    other configuration error in this module already uses.
    """
    try:
        makedirs_owner_only(path)
    except PermissionError as e:
        raise ValueError(
            f"[SYSTEM SUGGESTION]: {e} The journal directory and every "
            "directory above it must be a real directory, not a link to one "
            "— reconfigure LLM_JOURNAL_DIR or remove the link."
        ) from e


def _write_if_absent(path: str, content: str) -> None:
    if not os.path.exists(path):
        _write_text(path, content)


def _read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _write_text(path: str, content: str) -> None:
    """Write *content* to *path* owner-only; see `write_text_owner_only`.

    `tighten_once` only runs once, at `ensure_journal_tree`; every note, day
    file and month/year index this module creates afterwards goes through
    here, so the owner-only guarantee has to come from the write itself
    instead of relying on a later pass that will never revisit it.
    """
    _snapshot_before_write(path)
    write_text_owner_only(path, content)
