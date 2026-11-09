"""Reading and writing the store.

Every write runs in one transaction: take the lock, then read, then merge, then
render, then write, then commit. The order is the point. The journal's write path
read a note before it took its lock, so two sessions revising one subject could
each read the old claim and the second would silently drop the first's revision —
and with one memory directory shared by every session, worktree and install on a
machine, that is the normal case rather than a corner.

A read needs no lock: files are replaced atomically, so a reader sees the old
document or the new one and never half of either.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, timedelta

from zrb.config.config import CFG
from zrb.llm.memory import paths
from zrb.llm.memory.model import (
    KIND_DIARY,
    STATUS_ACTIVE,
    STATUS_RETIRED,
    Diary,
    Fact,
    date_error,
    format_stamp,
    id_error,
    split_document,
)
from zrb.llm.memory.paths import (
    CORE_FILE,
    DIARY_DIR,
    FACTS_DIR,
    GITIGNORE_FILE,
    LOG_DIR,
)
from zrb.llm.memory.render import render_core
from zrb.util.file_lock import hold_file_lock
from zrb.util.owner_only import makedirs_owner_only, write_text_owner_only

# How long a git call may take before the commit is abandoned. A commit is an
# audit trail, never a prerequisite: a store on a slow or full disk must still
# accept a claim.
_GIT_TIMEOUT_SECONDS = 20

# The handover a first turn reads is the newest one, but only while it is recent:
# a two-month-old "ask for the DNS credentials" is a thread that ended.
_HANDOVER_MAX_AGE_DAYS = 7

_TIME_FORMAT = "%H:%M"


def today() -> str:
    return date.today().isoformat()


def now() -> str:
    return format_stamp()


def read_document(path: str) -> str:
    """The file's text, or ``""`` when it cannot be read.

    Invalid UTF-8 counts as unreadable: a store is browsable and syncable, so a
    corrupted or wrongly-encoded file must degrade to "absent" rather than take a
    turn down through `render_memory_block` or a search.
    """
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeError):
        return ""


def write_document(path: str, content: str) -> None:
    """Write *content* to *path* atomically, owner-only.

    The temporary file sits beside the target so `os.replace` is a rename on one
    filesystem: a reader never sees a document that is still being written, which
    is what lets `search` run without the lock.
    """
    directory = os.path.dirname(path)
    makedirs_owner_only(directory)
    temporary = os.path.join(directory, f".{os.path.basename(path)}.tmp")
    write_text_owner_only(temporary, content)
    os.replace(temporary, path)


@contextmanager
def locked() -> Iterator[None]:
    """Hold the store's write lock. Taken *before* the read, always."""
    paths.ensure_store()
    with hold_file_lock(paths.lock_path(), timeout=CFG.LLM_MEMORY_LOCK_TIMEOUT):
        yield


def load_fact(fact_id: str, include_retired: bool = True) -> Fact | None:
    """The fact under *fact_id*, or ``None``.

    A retired fact is returned by default: `forget` keeps the file, and a caller
    that must not revive or re-render it filters on `active` itself. A name the
    store could not have written reads as an empty read rather than an error: a
    reader is never the place a bad name should surface.
    """
    if not fact_id:
        return None
    try:
        fact = Fact.from_markdown(read_document(paths.fact_path(fact_id)))
    except ValueError:
        return None
    if fact is None:
        return None
    # The file name is the id. A document whose frontmatter disagrees is not the
    # fact that was asked for, and retiring it would write a different subject.
    if fact.id != fact_id:
        return None
    if not include_retired and not fact.is_active:
        return None
    return fact


def save_fact(fact: Fact) -> None:
    write_document(paths.fact_path(fact.id), fact.to_markdown())


def load_facts(include_retired: bool = False) -> list[Fact]:
    """Every fact, ordered by id, so a rendered core is the same bytes twice."""
    facts: list[Fact] = []
    directory = paths.facts_dir()
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return facts
    for name in names:
        if not name.endswith(".md") or name.startswith("."):
            continue
        fact = Fact.from_markdown(read_document(os.path.join(directory, name)))
        # The file name *is* the id, and an id that is not a subject id was not
        # written by this store. A mismatch is skipped rather than reported: a
        # pointer that names a file the store does not hold is worse than no
        # pointer, because the reader believes it.
        if fact is None or id_error(fact.id) is not None:
            continue
        if name.removesuffix(".md") != fact.id:
            continue
        if not include_retired and not fact.is_active:
            continue
        facts.append(fact)
    facts.sort(key=lambda item: item.id)
    return facts


def load_diary(day: str) -> Diary | None:
    try:
        entry = Diary.from_markdown(read_document(paths.diary_path(day)))
    except ValueError:
        return None
    if entry is None or entry.id != day:
        return None
    return entry


def save_diary(entry: Diary) -> None:
    write_document(paths.diary_path(entry.id), entry.to_markdown())


def load_diaries(include_retired: bool = False) -> dict[str, Diary]:
    """Every diary entry keyed by its date, newest first."""
    entries: dict[str, Diary] = {}
    directory = paths.diary_dir()
    try:
        names = sorted(os.listdir(directory), reverse=True)
    except OSError:
        return entries
    for name in names:
        if not name.endswith(".md") or name.startswith("."):
            continue
        entry = Diary.from_markdown(read_document(os.path.join(directory, name)))
        if entry is None or date_error(entry.id) is not None:
            continue
        if name.removesuffix(".md") != entry.id:
            continue
        if not include_retired and not entry.is_active:
            continue
        entries[entry.id] = entry
    return entries


def latest_handover(today_day: str | None = None) -> Diary | None:
    """The newest entry carrying a handover, within the last week."""
    current = _as_date(today_day) or date.today()
    oldest = current - timedelta(days=_HANDOVER_MAX_AGE_DAYS)
    for day, entry in load_diaries().items():
        when = _as_date(day)
        if when is None or when < oldest or when > current:
            continue
        if entry.handover.strip():
            return entry
    return None


def latest_diary_before(day: str) -> Diary | None:
    """The newest active entry strictly before *day*, or ``None``.

    `load_diaries` is newest first and a day is its id, so the first entry that
    sorts earlier is the one wanted. Left unbounded on purpose: a store written
    to last month still has a last day, and the line carries its date, so naming
    an old one is honest where naming none would be silent.
    """
    for entry_day, entry in load_diaries().items():
        if entry_day < day:
            return entry
    return None


def log_lines(day: str) -> list[str]:
    """The event lines of *day*: the `# date` header is not one of them."""
    return [
        line
        for line in read_document(paths.log_path(day)).splitlines()
        if line.strip() and not line.startswith("# ")
    ]


def append_log(text: str, tags: str = "", day: str | None = None) -> str:
    """Append one line to today's log and return the line as written.

    The date is the filename and the clock time is derived, so a day file cannot
    hold a line from another day and the writer never supplies either.

    A day file is one line per event, with the day's header on the first line and
    no blank line between any two. Joining whole lines is what keeps that true:
    the file already ends with a newline, so pasting another one in front of the
    event left a gap under every appended line. A blank line an older writer or a
    hand edit left is dropped on the way out, so an old day heals as it grows.
    """
    entry_day = day or today()
    body = " ".join(text.split())
    stamp = datetime.now().strftime(_TIME_FORMAT)
    suffix = f" ({tags})" if tags.strip() else ""
    line = f"- {stamp} — {body}{suffix}"
    path = paths.log_path(entry_day)
    kept = [old for old in read_document(path).splitlines() if old.strip()]
    if not kept:
        kept = [f"# {entry_day}"]
    write_document(path, "\n".join([*kept, line]) + "\n")
    return line


def recent_log_lines(limit: int = 4, day: str | None = None) -> list[str]:
    """The last *limit* lines, today's first and yesterday's when today is short."""
    if limit <= 0:
        return []
    current = _as_date(day) or date.today()
    lines: list[str] = []
    for offset in (0, 1):
        wanted_day = current - timedelta(days=offset)
        wanted = wanted_day.isoformat()
        # A line lifted from another day carries the date it came from; a line
        # from today does not, because "today" is already the block's heading.
        prefix = (
            "" if offset == 0 else f"- {wanted_day.month:02d}-{wanted_day.day:02d} "
        )
        day_lines = log_lines(wanted)
        if offset:
            day_lines = [f"{prefix}{line.removeprefix('- ')}" for line in day_lines]
        lines = day_lines + lines
        if len(lines) >= limit:
            break
    return lines[-limit:]


def prune_logs() -> list[str]:
    """Delete log days past `LLM_MEMORY_LOG_RETENTION_DAYS`; return what went.

    Only `log/` is pruned. The diary is what the log was for, so a store that
    kept only the diary is still a store with a past.
    """
    days = CFG.LLM_MEMORY_LOG_RETENTION_DAYS
    if days <= 0:
        return []
    oldest = date.today() - timedelta(days=days)
    removed: list[str] = []
    directory = paths.log_dir()
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return removed
    for name in names:
        if not name.endswith(".md"):
            continue
        when = _as_date(name.removesuffix(".md"))
        if when is None or when >= oldest:
            continue
        try:
            os.remove(os.path.join(directory, name))
        except OSError:
            continue
        removed.append(name)
    return removed


def write_core(facts: list[Fact] | None = None) -> str:
    """Render the core from *facts* and write it when the text changed.

    Returns the text, which is what the caller's cap check measured: a value
    computed a second time is a second answer.
    """
    content = render_core(load_facts() if facts is None else facts)
    path = paths.core_path()
    if read_document(path) != content:
        write_document(path, content)
    return content


# What the audit trail owns. A commit stages *and names* only these, because
# `LLM_MEMORY_DIR` may point at a directory holding something else — a checkout, a
# scratch note, a credential — and a store that commits its neighbour's files is a
# store that leaks them. Naming them at the commit matters as much as staging them:
# the index is shared with whoever else works in the repository, and a bare commit
# takes along everything they had staged.
_MANAGED_PATHS = (CORE_FILE, FACTS_DIR, DIARY_DIR, LOG_DIR, GITIGNORE_FILE)

# Written inside `.git` when *this* store created the repository. A `.git` without
# it belongs to somebody else, and adding our commits to their history is not
# ours to do.
_OWNED_MARKER = os.path.join(".git", "zrb-memory")


def git_commit(message: str) -> None:
    """Commit the store's own files, and only those. Best effort: a failure never
    fails a write."""
    if not CFG.LLM_MEMORY_GIT_ENABLED:
        return
    root = paths.memory_dir()
    if _repository_for(root) is None:
        return
    managed = [
        name for name in _MANAGED_PATHS if os.path.exists(os.path.join(root, name))
    ]
    if not managed:
        return
    if _git(root, "add", "-A", "--", *managed) is None:
        return
    staged = _staged_paths(root, managed)
    if not staged:
        return
    _git(
        root,
        "-c",
        "user.name=zrb-memory",
        "-c",
        "user.email=zrb-memory@localhost",
        "commit",
        "-q",
        "-m",
        message,
        "--",
        *staged,
    )


def _staged_paths(root: str, managed: list[str]) -> list[str]:
    """The files this store staged, as names the commit accepts.

    Directories are not paths to git: a `diary` with no entry in it yet matches
    nothing, and one unmatched name makes git refuse the whole commit — so the
    list comes from the index instead. `--relative` keeps each name resolvable
    from the store's directory, which is where the commit runs.
    """
    changed = _git(
        root, "diff", "--cached", "--name-only", "--relative", "--", *managed
    )
    if changed is None:
        return []
    return [line for line in changed.splitlines() if line]


def _repository_for(root: str) -> str | None:
    """The repository this store commits into, or ``None`` if it has none to use.

    Two of them are ours. The store's own: a directory zrb created and marked,
    which is what `LLM_MEMORY_DIR` pointing somewhere else leaves behind. And the
    notes directory, when the store sits inside it and that directory *is* the
    repository — the default layout, where notes and memory share one history.

    A repository that merely contains the notes directory is not ours. A project
    checkout with the notes under it, or a dotfiles repository holding `$HOME`,
    would get memory commits in its history, and its staged work inside them: the
    notes are a guest there, and a guest does not commit.
    """
    if os.path.isdir(os.path.join(root, ".git")):
        marker = os.path.join(root, _OWNED_MARKER)
        return root if os.path.isfile(marker) else None
    if paths.is_store_within_notes():
        enclosing = _enclosing_repository(root)
        if enclosing is not None:
            return enclosing if _is_notes_root(enclosing) else None
    return _init_owned_repository(root)


def _is_notes_root(toplevel: str) -> bool:
    """Whether *toplevel* is the notes directory itself, not a directory above it."""
    return os.path.realpath(toplevel) == os.path.realpath(paths.notes_dir())


def _enclosing_repository(root: str) -> str | None:
    """The working tree *root* sits inside, if there is one."""
    top = _git(root, "rev-parse", "--show-toplevel")
    if top is None:
        return None
    return top.strip() or None


def _init_owned_repository(root: str) -> str | None:
    """Create this store's own repository and mark it as ours: the root, or None."""
    if _git(root, "init", "-q") is None:
        return None
    try:
        with open(os.path.join(root, _OWNED_MARKER), "w", encoding="utf-8") as f:
            f.write("this repository is the memory store's audit trail\n")
    except OSError:
        return None
    return root


def _git(root: str, *args: str) -> str | None:
    try:
        done = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode == 0 else None


def _as_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


__all__ = [
    "KIND_DIARY",
    "STATUS_ACTIVE",
    "STATUS_RETIRED",
    "append_log",
    "git_commit",
    "latest_handover",
    "load_diaries",
    "load_diary",
    "load_fact",
    "load_facts",
    "locked",
    "log_lines",
    "now",
    "prune_logs",
    "read_document",
    "recent_log_lines",
    "save_diary",
    "save_fact",
    "split_document",
    "today",
    "write_core",
    "write_document",
]
