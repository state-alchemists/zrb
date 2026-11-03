"""Where the memory lives on disk.

One directory holds four kinds of file and a lock. This module is the only place
that knows their names, so the tools, the renderer and the migration cannot drift
apart: a path is derived from an id or a date, never supplied by a model.

The default directory carries a version segment (``memory/v1``). Two zrb installs
share this machine — pipx and a development checkout — and a versioned default is
what keeps an older install from reading a newer format as its own. The journal's
single flat directory had the same exposure and no answer for it.
"""

from __future__ import annotations

import hashlib
import os

from zrb.config.config import CFG
from zrb.util.owner_only import makedirs_owner_only, tighten_once, write_text_owner_only

CORE_FILE = "core.md"
FACTS_DIR = "facts"
DIARY_DIR = "diary"
LOG_DIR = "log"
LOCK_FILE = ".lock"
GITIGNORE_FILE = ".gitignore"
STATE_DIR = ".state"

# What git must never track: the lock is a descriptor, and the state directory is
# this machine's bookkeeping rather than a claim about the world. Entries are
# appended to any `.gitignore` already there, never written over it.
_GITIGNORE_ENTRIES = (LOCK_FILE, f"{STATE_DIR}/")


def memory_dir() -> str:
    """The store's root, absolute, with `~` expanded."""
    return os.path.abspath(os.path.expanduser(CFG.LLM_MEMORY_DIR))


def core_path() -> str:
    return os.path.join(memory_dir(), CORE_FILE)


def lock_path() -> str:
    return os.path.join(memory_dir(), LOCK_FILE)


def facts_dir() -> str:
    return os.path.join(memory_dir(), FACTS_DIR)


def diary_dir() -> str:
    return os.path.join(memory_dir(), DIARY_DIR)


def log_dir() -> str:
    return os.path.join(memory_dir(), LOG_DIR)


def fact_path(fact_id: str) -> str:
    """``facts/<id>.md``.

    *fact_id* is checked, not trusted: the tools validate it, and this refuses
    anything a filesystem would read as a path even when a caller skipped that
    check. `Fact` ids never hold a separator, so a value that does is a bug or an
    attack, and a join is the wrong place to discover it.
    """
    return os.path.join(facts_dir(), f"{_checked_name(fact_id)}.md")


def diary_path(day: str) -> str:
    return os.path.join(diary_dir(), f"{_checked_name(day)}.md")


def log_path(day: str) -> str:
    return os.path.join(log_dir(), f"{_checked_name(day)}.md")


def _checked_name(name: str) -> str:
    """*name* if the store can hold it, else `ValueError`.

    A name is one path component: no separator of either platform's flavour, no
    `.`/`..`, no NUL. Checking both separators on every platform is deliberate —
    a store written on Windows and read on Linux must refuse the same names.
    """
    if (
        not name
        or name in (".", "..")
        or "\x00" in name
        or "/" in name
        or "\\" in name
    ):
        raise ValueError(f"{name!r} is not a name the memory store can hold")
    return name


def relative(path: str) -> str:
    """*path* as a search result names it: relative to the store, forward slashes."""
    return os.path.relpath(path, memory_dir()).replace(os.sep, "/")


def state_path(key: str) -> str:
    """A per-conversation state file. *key* is hashed, so no name leaves the store."""
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return os.path.join(memory_dir(), STATE_DIR, f"{digest}.json")


def ensure_store() -> str:
    """Create the store's directories (and its git repository) if they are missing.

    Owner-only, like every other place zrb keeps private text: a memory holds
    what the user told the agent, and a `0755` directory on a shared machine
    lists it to every local account. `tighten_once` narrows a store created by an
    earlier build, once, and the marker it leaves records that it did.

    Idempotent, and cheap enough to call before every read: an unwritten memory is
    empty, not broken.
    """
    root = memory_dir()
    for path in (root, facts_dir(), diary_dir(), log_dir()):
        makedirs_owner_only(path)
    _write_gitignore(root)
    tighten_once(root)
    return root


def _write_gitignore(root: str) -> None:
    """Add this store's entries to `.gitignore`, never rewriting what is there.

    A user may configure `LLM_MEMORY_DIR` to a directory with its own ignore
    rules — `secrets.md`, say. Rewriting the file would un-ignore that file, and
    the next `git_commit`'s `git add -A` would then commit it into the store's
    audit repository. Appending only the missing lines keeps both promises: the
    lock and the state directory stay untracked, and nothing a human excluded
    becomes tracked.
    """
    path = os.path.join(root, GITIGNORE_FILE)
    try:
        with open(path, encoding="utf-8") as f:
            existing = f.read()
    except FileNotFoundError:
        existing = ""
    except OSError:
        return
    present = {line.strip() for line in existing.splitlines()}
    missing = [entry for entry in _GITIGNORE_ENTRIES if entry not in present]
    if not missing:
        return
    separator = "" if not existing or existing.endswith("\n") else "\n"
    try:
        write_text_owner_only(path, existing + separator + "\n".join(missing) + "\n")
    except OSError:
        # A store that cannot be written is reported when the write is attempted,
        # not here: rendering a missing file must stay harmless.
        pass
