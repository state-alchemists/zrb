"""The condition a note holds under, in a form a machine can check.

`applies_when` has been required since the journal learned to retire a note, and
almost every value is prose: "while zrb 3.29 is the released line", "while go
uses the office laptop". A person can read those and a session can too, but
nothing can *check* one, so a note that stopped holding still arrives every
turn until somebody notices.

This module reads the narrow subset that can be checked without asking anyone:

``file:<path>@<sha>``
    holds while the file's content still hashes to *sha*. The writer stamps the
    hash at write time (`stamp`), because a condition nobody stamped is a
    condition nobody can evaluate. The path is untrusted input: it must stay
    inside the repository once symlinks are resolved and be a regular file, and
    at most `MAX_HASH_BYTES` of it is read.

``version:<3.29`` / ``version:=3.29.1`` / ``version:>=3.29``
    holds while zrb's own version satisfies the comparison.

``setting:<NAME>=<value>``
    holds while the configuration value has that token.

``date:<YYYY-MM-DD>``
    holds until the end of that day.

Anything else is prose, and prose never expires: `parse_condition` returns
``None`` and the note is treated as holding. Guessing that a sentence is false
would retire a note its author still believes, which is worse than the note
staying.
"""

import hashlib
import os
import re
import stat
from dataclasses import dataclass
from datetime import date

from packaging.version import InvalidVersion, Version

FILE_PREFIX = "file:"
VERSION_PREFIX = "version:"
SETTING_PREFIX = "setting:"
DATE_PREFIX = "date:"

SHA_LENGTH = 12
"""How much of the digest a condition records: enough to tell a file changed,
short enough that a hand-written condition stays readable."""

MAX_HASH_BYTES = 8 * 1024 * 1024
"""How much of a file a condition will read: a source file, not an artefact.

A `file:` path is written by a model, so it is untrusted input. Reading it whole
would let `/dev/zero` hang the turn and a multi-gigabyte file exhaust memory, so
the read is bounded and anything larger answers "cannot tell"."""

_TRUE_TOKENS = frozenset({"on", "true", "yes", "1", "enabled"})
_FALSE_TOKENS = frozenset({"off", "false", "no", "0", "disabled"})
_VERSION_RE = re.compile(r"^(<=|>=|==|=|<|>)?\s*(\S.*)$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SHA_RE = re.compile(rf"^[0-9a-f]{{{SHA_LENGTH}}}$")
"""What a recorded digest looks like. A suffix of this shape is *read* as a stamp
only when the value as a whole does not name a file: `config@prod.yml` is a path,
and so is `config@deadbeefcafe` when that file exists. Mistaking a path for a
stamp hides the note the moment it is written."""


@dataclass(frozen=True)
class Condition:
    """One checkable condition: what kind it is, and its payload."""

    kind: str
    value: str


def parse_condition(text: str) -> Condition | None:
    """The checkable condition in *text*, or ``None`` when it is prose."""
    prose = " ".join((text or "").split())
    for prefix, kind in (
        (FILE_PREFIX, "file"),
        (VERSION_PREFIX, "version"),
        (SETTING_PREFIX, "setting"),
        (DATE_PREFIX, "date"),
    ):
        if prose.lower().startswith(prefix):
            value = prose[len(prefix) :].strip()
            return Condition(kind, value) if value else None
    return None


def file_sha(path: str) -> str:
    """The digest a `file:` condition records for *path*, or ``""`` when it cannot
    be read.

    Bounded on purpose (`MAX_HASH_BYTES`) and limited to regular files: a condition
    names a source file, so a device, a directory and a multi-gigabyte artefact are
    all "cannot tell" rather than something to read into memory."""
    return _file_digest(path) or ""


def _file_digest(path: str) -> str | None:
    """*path*'s digest — ``None`` when it is not there, ``""`` when it cannot be read.

    The file is opened by name **once** and everything after that is settled from
    the descriptor: `O_NOFOLLOW` refuses a symlink swapped in after `condition_path`
    validated the path, `fstat` refuses anything that is not a regular file, and the
    size it reports bounds the read. Reopening the path by name would hand the race
    back to whoever can write to the tree."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        return None
    except OSError:
        return ""
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_HASH_BYTES:
            return ""
        with os.fdopen(descriptor, "rb") as f:
            descriptor = -1
            content = f.read(MAX_HASH_BYTES + 1)
    except OSError:
        return ""
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    return hashlib.sha256(content).hexdigest()[:SHA_LENGTH]


def condition_path(value: str, root: str) -> str:
    """The file *value* names inside *root*, or ``""`` when it names none we may read.

    A condition is text a model wrote, so its path is untrusted input: it must be
    relative, stay inside the tree once symlinks are resolved, and — checked when
    it is read — be a regular file. Without that, `file:` is a way to read anything
    the process can reach under a name that looks like a test fixture: `/dev/zero`
    blocks the turn, `/etc/passwd` leaves the repository entirely, and a symlink
    does the same without spelling `..`."""
    if not root or not value or os.path.isabs(value):
        return ""
    if any(part == ".." for part in re.split(r"[\\/]", value)):
        return ""
    inside = os.path.realpath(root)
    target = os.path.realpath(os.path.join(inside, value))
    try:
        if os.path.commonpath([inside, target]) != inside:
            return ""
    except ValueError:
        return ""
    return target


def stamp(text: str, root: str) -> str:
    """*text* with the file condition's hash filled in, recorded now.

    A `file:` condition that names no hash is stamped here, so the note says what
    it was written against rather than asking a later reader to guess. No root
    means no repository was in hand, and a hash taken from the process's own
    directory would point at whatever happens to sit beside a later reader — so
    the condition is left unstamped, which reads as uncheckable and keeps the
    note. A condition already stamped, or a file that cannot be read, comes back
    unchanged: a note is never refused for naming a path that does not exist yet.

    "Already stamped" means the last `@`-segment is a digest (`_SHA_RE`) **and** the
    whole value does not name a file. `config@prod.yml` is a file name, and so is
    `config@deadbeefcafe` when that file exists: reading either as `path@digest`
    would compare the hash of one file with the other's name and hide the note
    immediately. A path that exists as a whole is stamped as the path it is.

    A path that leaves the tree is left unstamped rather than refused (see
    `condition_path`): the note is still worth keeping, it just cannot be checked.
    """
    condition = parse_condition(text)
    if condition is None or condition.kind != "file" or not root:
        return text
    target = condition_path(condition.value, root)
    if not target:
        return text
    path, _, recorded = condition.value.rpartition("@")
    if path and _SHA_RE.match(recorded) and not os.path.exists(target):
        return text
    digest = file_sha(target)
    if not digest:
        return text
    return f"{FILE_PREFIX}{condition.value}@{digest}"


def is_condition_met(
    condition: Condition, root: str, version: str, repo: str = ""
) -> bool | None:
    """Whether *condition* still holds — ``None`` when this machine cannot tell.

    ``None`` is not "false": a condition this module cannot evaluate keeps its
    note alive, because retiring a note on a failure to look would delete memory
    the first time a path moved.

    *repo* is the repository whose tree *root* names, empty when the note belongs
    to no repository or to one other than the checkout in hand. A `file:`
    condition is answered only when it is not empty: the same relative path in
    another checkout is another file, and a hash mismatch there would retire a
    note that is still true."""
    if condition.kind == "file":
        return _is_file_unchanged(condition.value, root) if repo else None
    if condition.kind == "version":
        return _is_version_matching(condition.value, version)
    if condition.kind == "setting":
        return _is_setting_matching(condition.value)
    if condition.kind == "date":
        return _is_before_date(condition.value)
    return None


def _is_file_unchanged(value: str, root: str) -> bool | None:
    path, separator, recorded = value.rpartition("@")
    if not separator or not path or not _SHA_RE.match(recorded):
        # Nothing was stamped, so there is no digest to compare against. Reading
        # the value as `path@digest` anyway would report a live note as false.
        return None
    target = condition_path(path, root)
    if not target:
        # The path leaves the tree, so it is not one this condition may read.
        return None
    whole = condition_path(value, root)
    if whole and os.path.exists(whole):
        # The value as a whole names a file, so it is a path whose last segment
        # happens to look like a digest — not a stamped condition. There is no
        # digest of `path` to compare, and "cannot tell" keeps the note.
        return None
    digest = _file_digest(target)
    if digest is None:
        # The file is gone, which is a change, not an inability to check.
        return False
    if not digest:
        # Present but unreadable, not a regular file, or past `MAX_HASH_BYTES`:
        # we cannot tell, and a note is never hidden on a failure to look.
        return None
    return digest == recorded


def _is_version_matching(value: str, version: str) -> bool | None:
    found = _VERSION_RE.match(value.strip())
    if not found:
        return None
    operator = found.group(1) or "="
    current = _version(version)
    target = _version(found.group(2))
    if current is None or target is None:
        return None
    if operator in ("=", "=="):
        return current == target
    if operator == "<":
        return current < target
    if operator == "<=":
        return current <= target
    if operator == ">":
        return current > target
    return current >= target


def _version(text: str) -> Version | None:
    """*text* as a comparable version, or ``None`` when it is not one.

    PEP 440 ordering, so a development build of 3.29 answers `version:<3.29` with
    a real false rather than "cannot tell", and a postrelease answers `>3.29`
    with a real true. A version this build cannot parse is still uncheckable — the
    answer being "cannot tell" must never be reached by guessing."""
    try:
        return Version(text.strip())
    except InvalidVersion:
        return None


def _is_setting_matching(value: str) -> bool | None:
    name, separator, wanted = value.partition("=")
    if not separator or not name.strip():
        return None
    from zrb.config.config import CFG  # lazy: hot-path internal — pulls the config tree

    actual = getattr(CFG, name.strip(), None)
    if actual is None:
        return None
    return _token(actual) == _token(wanted)


def _token(value: object) -> str:
    """A setting compared as the word a condition would write for it."""
    text = str(value).strip().lower()
    if text in _TRUE_TOKENS:
        return "true"
    if text in _FALSE_TOKENS:
        return "false"
    return text


def _is_before_date(value: str) -> bool | None:
    if not _DATE_RE.match(value.strip()):
        return None
    try:
        last = date.fromisoformat(value.strip())
    except ValueError:
        return None
    return date.today() <= last


def current_version() -> str:
    """zrb's own version, or ``""`` when it cannot be read from here."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("zrb")
    except PackageNotFoundError:
        return ""


def expired_note_rels(
    notes, root: str, current: str, version: str | None = None
) -> set[str]:
    """The notes whose condition is *known to be* false, by journal-relative path.

    A note with no condition, a prose condition, or one this machine cannot
    evaluate is not here: expiry removes what is disproved, never what is merely
    unchecked.

    *current* is the repository in hand. A note about another one is passed an
    empty repository, which makes its `file:` condition uncheckable rather than
    wrong — `root` names this checkout's tree, not that note's."""
    resolved = current_version() if version is None else version
    expired: set[str] = set()
    for note in notes:
        condition = parse_condition(note.applies_when)
        if condition is None:
            continue
        repo = note.repo if note.repo and note.repo == current else ""
        if is_condition_met(condition, root, resolved, repo) is False:
            expired.add(note.rel)
    return expired
