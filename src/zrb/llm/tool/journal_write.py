"""Journal writers that own the on-disk format.

The model supplies *content*; this module derives paths, timestamps, index
entries and backlinks, which upholds these invariants by construction:

- **broken-link** — a link is only written after its target is confirmed on disk.
- **missing-backlink** — the reciprocal entry is inserted in the same call.
- **orphan** — every note is listed in its category index, and every category
  index is linked from the root index.
- **missing-index** — indexes are created on the way down to the leaf.
- **no lost update** — a coarse-grained lock on the root's `.lock` makes each
  writer's multi-file graph update atomic against a concurrent writer.

A note's frontmatter is the one source of truth for what the indexes say about
it (`journal_note`); a write changes the note and then renders every index from
the notes again (`journal_index`), so no fact lives in two files.
"""

import os
import re
import subprocess
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Annotated

from pydantic import Field

from zrb.config.config import CFG
from zrb.llm.journal_index_name import resolve_journal_index_name
from zrb.llm.journal_usage_log import (
    DELETED,
    SUPERSEDED,
    WRITTEN,
    record_note_event,
)
from zrb.llm.tool.journal_index import (
    ACTIVITY_DIR,
    HUD_LINE_SOFT_LIMIT,
    hud_lines_of,
    hud_section_for,
    normalize_hud_line,
    plan_hud,
    render_category_index,
    render_root_index,
    root_index_skeleton,
    with_link,
)
from zrb.llm.tool.journal_index_migration import absorb_renamed_sections, plan_adoptions
from zrb.llm.tool.journal_note import (
    HISTORY_HEADING,
    NOTE_CATEGORIES,
    STATUS_ACTIVE,
    STATUS_SUPERSEDED,
    Note,
    append_under_heading,
    check_category,
    check_slug,
    compose_note,
    format_stamp,
    insert_before_backlinks,
    list_notes,
    next_stamp,
    one_line,
    read_text,
    relative,
    scrub_links_to,
    set_frontmatter,
    with_backlink,
)
from zrb.util.file_lock import FileLockTimeout, hold_file_lock
from zrb.util.owner_only import makedirs_owner_only, tighten_once, write_text_owner_only


def log_activity(
    summary: Annotated[
        str,
        Field(
            description=(
                "One line of what happened; date, time and path are derived, so a "
                "clock time at the start of it is dropped. A line may be a moment "
                "instead of work: the user's words quoted, then why they mattered."
            )
        ),
    ],
    files: Annotated[
        list[str] | None,
        Field(description="Paths you touched this turn, if any."),
    ] = None,
    importance: Annotated[
        int | None,
        Field(
            description=(
                "How much this line matters to whoever reads the day back, 1 to "
                "10; omit it for an ordinary line. A later session's first turn "
                "shows the highest lines from today and yesterday, so reserve the "
                "top of the range for a constraint, a decision, or a thread left "
                "open."
            )
        ),
    ] = None,
) -> str:
    """Records one line of the day in the journal's activity log.

    Call this BEFORE your reply on a turn that changed files or established a
    root cause, decision, or API quirk a later session would otherwise
    rediscover; then deliver the complete answer — never end the turn on the
    "Logged to ..." result. Skip greetings, clarifying questions, refusals,
    single lookups, and anything already recorded.

    A turn that touched no file still earns a line when something happened
    between you and the user — a joke worth keeping, a thing they told you about
    themselves. Quote their words, then say why it mattered. This line is the
    only copy: a later session cannot recover the conversation any other way.

    Verify before recording: a wrong entry misleads every future session, and a
    number or an absence needs its source (`wc -l: 832`) or stays out. Unless the user asked for the write, do not announce it. Use
    WriteJournalNote when the finding must be findable by topic.
    """
    with _open_journal() as root:
        result = _log_activity_locked(root, summary, files, importance)
        # The entry carries its own timestamp from inside the helper; this
        # label is the same minute except across a minute rollover.
        _commit_or_defer(root, f"activity: {datetime.now():%Y-%m-%d %H:%M}")
        return result


log_activity.__name__ = "LogActivity"


IMPORTANCE_MIN, IMPORTANCE_MAX = 1, 10
"""The range `imp N` is held to; the day block ranks a day's lines on it."""

# A clock time the summary brought along, with the date and the dash an agent
# tends to copy from the file it is reading. Matched only at the start, and only
# with colons: "2.5 kg" is a number, not a stamp.
_LEADING_STAMP = re.compile(
    r"^\s*(?:\d{4}-\d{2}-\d{2}[ T])?\d{1,2}:\d{2}(?::\d{2})?\s*(?:[—–-]\s*)?"
)


def _clean_summary(summary: str) -> str:
    """*summary* without a clock time at its start, and without a trailing period.

    This tool writes the timestamp, so one in the text is a second stamp — a line
    read back as `19:32 — 19:35 — …` says two events happened. The period is
    added back by the caller, so one already there would double it. A summary
    that is only a time keeps its text rather than losing all of it.
    """
    text = summary.strip()
    cleaned = _LEADING_STAMP.sub("", text, count=1).strip()
    if not cleaned:
        return text
    return cleaned[:-1].rstrip() if cleaned.endswith(".") else cleaned


def _log_activity_locked(
    root: str,
    summary: str,
    files: list[str] | None,
    importance: int | None = None,
) -> str:
    """Record the activity line under *root*, returning the tool's result.

    The caller holds the journal lock and makes the commit, so a transaction can
    call this many times for one lock and one commit."""
    now = datetime.now()
    day_file = _ensure_activity_path(root, now)
    file_note = ", ".join(files) if files else "—"
    ranked = (
        f" · imp {max(IMPORTANCE_MIN, min(IMPORTANCE_MAX, importance))}"
        if importance is not None
        else ""
    )
    entry = (
        f"- {now.strftime('%H:%M')} — {_clean_summary(summary)}. "
        f"Files: {file_note}{ranked}."
    )
    _write_if_changed(day_file, insert_before_backlinks(read_text(day_file), entry))
    return f"Logged to {relative(day_file, root)}"


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
                "Kebab-case filename. Reusing a slug overwrites that note; "
                "the old Context/Finding survives only as one bounded History "
                "entry. SearchJournal first unless you are certain the slug "
                "is free or is the note you mean to revise, and wait for its "
                "result before this call — don't batch the two."
            )
        ),
    ],
    title: Annotated[
        str,
        Field(
            description=(
                "Short heading; also the index and backlink label. Retitling "
                "an existing slug relabels its index entries."
            )
        ),
    ],
    context: Annotated[str, Field(description="When the finding applies.")],
    finding: Annotated[
        str,
        Field(
            description=(
                "The durable fact, standalone for a future session with no "
                "memory of this conversation."
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
                "`technical/retry-policy.md`); each gets a backlink."
            )
        ),
    ] = None,
    hud_line: Annotated[
        str | None,
        Field(
            description=(
                "One-line summary (aim for 160 characters or fewer) pinned to "
                "the injected index, in this "
                "category's section. The section is capped: the oldest lines "
                "past it are evicted and named in the result. On revision "
                "pass an updated line if the fact changed; omitting keeps the "
                "old one."
            )
        ),
    ] = None,
    pinned: Annotated[
        bool,
        Field(
            description=(
                "Keep hud_line through the section cap (evicted only when "
                "every line in the section is pinned). Set it for a "
                "constraint or identity that must not disappear. On a "
                "`projects` or `technical` note a pinned line goes under `## "
                "Constraints`, not `## Recent`."
            )
        ),
    ] = False,
    applies_when: Annotated[
        str | None,
        Field(
            description=(
                "The condition under which the note still holds, e.g. `while "
                "zrb 3.26 is the released line`, `while go uses the office "
                "laptop`. Name something checkable: a version, file, setting "
                "or stated preference. Without one the note can never be "
                "retired, only re-read."
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

    Record only what this session verified: an unchecked diagnosis is a guess,
    and a wrong entry misleads every session that finds it. Skip anything
    already recorded — search first when unsure.

    This tool maintains the indexes, backlinks, and git history, so never edit
    journal files directly: revise here or remove with DeleteJournalNote.
    Unless the user asked for the write, do not announce it.
    """
    # Before the journal is opened: a refused request must not create a tree.
    check_category(category)
    check_slug(slug)
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
            applies_when,
        )
        _commit_or_defer(root, f"write: {category}/{slug}")
        _record_or_queue(WRITTEN, category, slug)
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

    The note stays on disk as evidence but leaves the injected index in the
    same call, so a false constraint cannot keep reaching later sessions. Its
    frontmatter says `status: superseded` and its `## History` says why.

    Use it, not DeleteJournalNote, when the finding was right and has stopped
    being true. DeleteJournalNote is for a note that should never have existed.
    """
    with _open_journal() as root:
        result = _supersede_note_locked(root, category, slug, reason)
        _commit_or_defer(root, f"supersede: {category}/{slug}")
        _record_or_queue(SUPERSEDED, category, slug)
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
    applies_when: str | None = None,
) -> str:
    """Write the note under *root* and render the indexes from the notes.

    The caller holds the lock and makes the commit. Returns exactly the string
    the tool returns, eviction note included — that is how a caller learns an
    older line under the same section lost its place."""
    check_category(category)
    check_slug(slug)
    notes = _load_notes(root)
    note_path = os.path.join(root, category, f"{slug}.md")
    note_rel = relative(note_path, root)
    previous = next((note for note in notes if note.rel == note_rel), None)
    line, is_pinned = _hud_state(hud_line, pinned, previous, notes, note_rel)
    targets = _resolve_links(root, links or [])
    fields = {
        "slug": slug,
        "title": title,
        "context": context,
        "finding": finding,
        "source": source,
        "applies_when": applies_when or "",
        "status": STATUS_ACTIVE,
        "hud_line": line,
        "pinned": "true" if is_pinned else "",
        "updated": format_stamp(next_stamp(notes, datetime.now())),
    }
    _write_text(
        note_path,
        compose_note(read_text(note_path), note_path, _index_name(), fields, targets),
    )
    for target in targets:
        _add_backlink(target, note_path, title)
    section = hud_section_for(category, is_pinned)
    cap = CFG.LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION
    already = plan_hud(notes, cap)[section].evicted
    rendered = _render_indexes(root)
    evicted = [
        evicted_line
        for evicted_line in plan_hud(rendered, cap)[section].evicted
        if evicted_line not in already
    ]
    result = f"Wrote {note_rel}"
    if evicted:
        result += _eviction_note(section, evicted)
    if len(line) > HUD_LINE_SOFT_LIMIT:
        result += (
            f" The hud_line is {len(line)} characters, over the "
            f"{HUD_LINE_SOFT_LIMIT} a headline should stay within: rewrite it "
            "shorter with another WriteJournalNote."
        )
    return result


def _hud_state(
    hud_line: str | None,
    pinned: bool,
    previous: Note | None,
    notes: list[Note],
    note_rel: str,
) -> tuple[str, bool]:
    """The `hud_line` and `pinned` a write leaves on the note.

    A write that supplies no line keeps the note's own, pin included: the pin
    belongs to a line, and a revision that leaves the line alone leaves it be."""
    line = normalize_hud_line(hud_line or "", note_rel, notes)
    if line:
        return line, pinned
    return (previous.hud_line, previous.pinned) if previous else ("", False)


def delete_journal_note(
    category: Annotated[
        str,
        Field(description=(f"One of: {', '.join(NOTE_CATEGORIES)}.")),
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
        _record_or_queue(DELETED, category, slug)
        return result


delete_journal_note.__name__ = "DeleteJournalNote"


def _supersede_note_locked(root: str, category: str, slug: str, reason: str) -> str:
    """Retire a note that stopped applying, under *root*.

    The caller holds the journal lock and makes the commit. The file stays —
    its evidence is why the journal can explain itself later — but its line
    leaves the injected index here and now, because a note that has stopped
    applying and still sits in every turn's context is a claim that has to be
    paid for in every turn until somebody notices."""
    check_category(category)
    check_slug(slug)
    note_path = os.path.join(root, category, f"{slug}.md")
    note_rel = relative(note_path, root)
    if not os.path.isfile(note_path):
        raise ValueError(
            f"[SYSTEM SUGGESTION]: no note at {note_rel}. SearchJournal for the "
            "correct slug, or omit the supersede."
        )
    dropped = hud_lines_of(read_text(os.path.join(root, _index_name())), note_rel)
    entry = f"- {datetime.now():%Y-%m-%d} — superseded: {reason.strip()}"
    text = set_frontmatter(read_text(note_path), {"status": STATUS_SUPERSEDED})
    _write_text(note_path, append_under_heading(text, HISTORY_HEADING, entry))
    _render_indexes(root)
    result = f"Superseded {note_rel}: {reason.strip()}"
    if dropped:
        result += f" Removed from the index: {dropped[0].strip()}"
    return result


def _delete_note_locked(root: str, category: str, slug: str) -> str:
    """Delete the note and every link to it under *root*.

    The caller holds the journal lock and makes the commit. A line that is
    nothing but a link to the note goes with it — a hand-written one too —
    because leaving it would put a broken link in the journal."""
    check_category(category)
    check_slug(slug)
    note_path = os.path.join(root, category, f"{slug}.md")
    if not os.path.isfile(note_path):
        raise ValueError(
            f"[SYSTEM SUGGESTION]: no note at {category}/{slug}.md. "
            "SearchJournal for the correct slug, or omit the delete."
        )
    for path, text in scrub_links_to(root, note_path).items():
        _write_text(path, text)
    _snapshot_before_write(note_path)
    os.remove(note_path)
    _render_indexes(root)
    return f"Deleted {relative(note_path, root)}"


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
    because `_open_journal` migrates an older journal before the body runs.
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
        _lock_state.pending_events = []
        _begin_snapshot()
        try:
            yield transaction
        except BaseException:
            _restore_snapshots(_take_snapshot())
            _lock_state.pending_events = []
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
        # Only now is the body known to have succeeded: a rolled-back change
        # leaves no event, and each change leaves exactly one, in order.
        _flush_pending_events()


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

    def log_activity(
        self,
        summary: str,
        files: list[str] | None = None,
        importance: int | None = None,
    ) -> str:
        """Record one activity line; the whole batch commits at exit."""
        return self._record(
            _log_activity_locked(self._root, summary, files, importance)
        )

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
        applies_when: str | None = None,
    ) -> str:
        """Write one note; the whole batch commits at exit."""
        result = self._record(
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
                applies_when,
            )
        )
        _record_or_queue(WRITTEN, category, slug)
        return result

    def delete_note(self, category: str, slug: str) -> str:
        """Delete one note; the whole batch commits at exit."""
        result = self._record(_delete_note_locked(self._root, category, slug))
        _record_or_queue(DELETED, category, slug)
        return result

    def supersede_note(self, category: str, slug: str, reason: str) -> str:
        """Retire one note that stopped applying; the whole batch commits at exit."""
        result = self._record(
            _supersede_note_locked(self._root, category, slug, reason)
        )
        _record_or_queue(SUPERSEDED, category, slug)
        return result

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


# Whether this thread holds the journal lock, so a journal tool called from
# inside another journal write re-enters instead of waiting out the timeout
# against its own lock. `in_transaction` counts the `journal_transaction`
# bodies this thread is inside, `deferred_changes` counts the changes a tool
# made there and left for the transaction's single commit, and `pending_events`
# holds their usage-log events until that commit succeeds.
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


def _record_or_queue(event: str, category: str, slug: str) -> None:
    """Log a note event now, or queue it for the open transaction.

    Inside `journal_transaction` a change is not real until the body returns:
    a rollback must leave no event behind, so the event waits for the flush."""
    if getattr(_lock_state, "in_transaction", 0):
        _lock_state.pending_events.append((event, category, slug))
        return
    record_note_event(event, category, slug)


def _flush_pending_events() -> None:
    events = getattr(_lock_state, "pending_events", [])
    _lock_state.pending_events = []
    for event, category, slug in events:
        record_note_event(event, category, slug)


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
                _migrate_journal(root)
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


def _migrate_journal(root: str) -> None:
    """Bring the journal up to the format this version writes, lock held.

    Three things an older journal is missing: a renamed HUD section's lines in
    the section that absorbed it, the pin and HUD line of a note that lived only
    in the index text (copied into the note's frontmatter, so the index can be
    derived), and whatever the render adds (a HUD section that did not exist, the
    category's link in `## Directories`). A read-modify-write, so it belongs where
    the lock is: reading the index before `hold_file_lock` let a writer write back
    a copy taken before another writer added its line.

    Idempotent, and it never drops a line: one that no note accounts for stays
    where it was, as a foreign line. See `journal_index` for the ownership rule.
    """
    root_index = os.path.join(root, _index_name())
    absorbed = absorb_renamed_sections(read_text(root_index))
    _write_if_changed(root_index, absorbed)
    notes = _load_notes(root)
    adoptions = plan_adoptions(absorbed, notes)
    if adoptions:
        stamp = min(note.updated for note in notes if note.rel in adoptions)
        for offset, (rel, adoption) in enumerate(adoptions.items()):
            path = os.path.join(root, rel)
            moment = format_stamp(stamp + timedelta(microseconds=offset))
            _write_text(
                path,
                set_frontmatter(
                    read_text(path),
                    {
                        "hud_line": one_line(adoption.hud_line),
                        "pinned": "true" if adoption.pinned else None,
                        "updated": moment,
                    },
                ),
            )
    _render_indexes(root)


def _render_indexes(root: str) -> list[Note]:
    """Render the root index and every category index from the notes.

    Writes only a file whose text changed, so rendering twice is a no-op.
    Returns the notes it rendered from."""
    index_name = _index_name()
    notes = _load_notes(root)
    root_index = os.path.join(root, index_name)
    _write_if_changed(
        root_index,
        render_root_index(
            read_text(root_index),
            notes,
            CFG.LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION,
            index_name,
            CFG.LLM_JOURNAL_CATALOG_MAX_ENTRIES,
        ),
    )
    for category in NOTE_CATEGORIES:
        path = os.path.join(root, category, index_name)
        _write_if_changed(path, render_category_index(read_text(path), notes, category))
    return notes


def _load_notes(root: str) -> list[Note]:
    index_name = _index_name()
    return list_notes(root, (index_name, "index.md"))


def ensure_journal_tree() -> str:
    """Create the journal root, its six directories, and their indexes.

    Only what is missing: an existing index is never rewritten here, since the
    lock is not held yet. `_migrate_journal` does the rewriting, under it.
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
    _write_if_absent(os.path.join(root, index_name), root_index_skeleton(index_name))
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
        f"# {day}\n\n## Backlinks\n\n- [month index]({index_name})\n",
    )
    return day_file


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


def _add_backlink(target: str, source_path: str, source_title: str) -> None:
    rel = relative(source_path, os.path.dirname(target))
    _write_if_changed(
        target, with_backlink(read_text(target), f"- [{source_title}]({rel})")
    )


def _register_link(index_path: str, rel_target: str, label: str) -> None:
    """List *rel_target* in an activity-log index; see `with_link`."""
    _write_if_changed(index_path, with_link(read_text(index_path), rel_target, label))


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


def _write_text(path: str, content: str) -> None:
    """Write *content* to *path* owner-only; see `write_text_owner_only`.

    `tighten_once` only runs once, at `ensure_journal_tree`; every note, day
    file and month/year index this module creates afterwards goes through
    here, so the owner-only guarantee has to come from the write itself
    instead of relying on a later pass that will never revisit it.
    """
    _snapshot_before_write(path)
    write_text_owner_only(path, content)


def _write_if_changed(path: str, content: str) -> None:
    if content != read_text(path):
        _write_text(path, content)
