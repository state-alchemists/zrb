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
from zrb.llm.memory.paths import (
    CORE_FILE,
    DIARY_DIR,
    FACTS_DIR,
    GITIGNORE_FILE,
    LOG_DIR,
)
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
    """
    entry_day = day or today()
    body = " ".join(text.split())
    stamp = datetime.now().strftime(_TIME_FORMAT)
    suffix = f" ({tags})" if tags.strip() else ""
    line = f"- {stamp} — {body}{suffix}"
    path = paths.log_path(entry_day)
    existing = read_document(path)
    header = f"# {entry_day}\n"
    content = f"{existing or header}\n{line}\n"
    write_document(path, content)
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
            ""
            if offset == 0
            else f"- {wanted_day.month:02d}-{wanted_day.day:02d} "
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


# What the audit trail owns. A commit stages only these, because `LLM_MEMORY_DIR`
# may point at a directory holding something else — a checkout, a scratch note, a
# credential — and a store that commits its neighbour's files is a store that
# leaks them.
_MANAGED_PATHS = (CORE_FILE, FACTS_DIR, DIARY_DIR, LOG_DIR, GITIGNORE_FILE)

# Written inside `.git` when *this* store created the repository. A `.git` without
# it belongs to somebody else, and adding our commits to their history is not
# ours to do.
_OWNED_MARKER = os.path.join(".git", "zrb-memory")


def git_commit(message: str) -> None:
    """Commit the store's own files. Best effort: a failure never fails a write."""
    if not CFG.LLM_MEMORY_GIT_ENABLED:
        return
    root = paths.memory_dir()
    if not _is_our_repository(root):
        return
    staged = [name for name in _MANAGED_PATHS if os.path.exists(os.path.join(root, name))]
    if not staged:
        return
    if _git(root, "add", "-A", "--", *staged) is None:
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
    )


def _is_our_repository(root: str) -> bool:
    """Whether the git repository at *root* is this store's to commit into.

    A missing repository is created and marked. An existing one we did not create
    is left alone: `zrb` cannot tell a dedicated memory directory from a project
    checkout somebody pointed `LLM_MEMORY_DIR` at.
    """
    marker = os.path.join(root, _OWNED_MARKER)
    if not os.path.isdir(os.path.join(root, ".git")):
        if _git(root, "init", "-q") is None:
            return False
        try:
            with open(marker, "w", encoding="utf-8") as f:
                f.write("this repository is the memory store's audit trail\n")
        except OSError:
            return False
        return True
    return os.path.isfile(marker)


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
