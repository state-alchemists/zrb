"""The condition a note holds under, in a form a machine can check.

`applies_when` has been required since the journal learned to retire a note, and
almost every value is prose: "while zrb 3.29 is the released line", "while go
uses the office laptop". A person can read those and a session can too, but
nothing can *check* one, so a note that stopped holding still arrives every
turn until somebody notices.

This module reads the narrow subset that can be checked without asking anyone:

``file:<path>``
    holds while the file's content still hashes to the digest the note records
    beside it, in `applies_when_digest`. The writer records that digest at write
    time (`condition_digest`), because a condition nobody stamped is a condition
    nobody can evaluate. The path is untrusted input: it must stay inside the
    repository once symlinks are resolved and be a regular file, and at most
    `MAX_HASH_BYTES` of it is read.

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
"""What a recorded digest looks like. It lives in its own frontmatter key rather
than at the end of the path: `config@deadbeefcafe` is a legal file name, so a
digest written into the value could not be told apart from one — and a reader
that guessed wrong would hide a note nobody touched."""


@dataclass(frozen=True)
class Condition:
    """One checkable condition: what kind it is, and its payload."""

    kind: str
    value: str


@dataclass(frozen=True)
class Origin:
    """Where a `file:` condition was stamped, as far as the check cares.

    A digest means nothing on its own. The same relative path in another
    repository is another file, and so is the same path in another checkout of a
    repository with the same directory name — `/work/a/zrb` and `/work/b/zrb` both
    tag as `zrb`, because a tag is the name a person would say. All three have to
    agree with this machine before a hash is compared: the note's tag with the
    checkout in hand, the tree the digest was taken in with the one now open, and
    the digest with the file. Any of them disagreeing answers "cannot tell", which
    keeps the note.
    """

    repo: str = ""
    checkout: str = ""
    digest: str = ""


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


_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_CAN_OPEN_RELATIVE = os.open in os.supports_dir_fd
"""Whether this platform can open a name relative to another directory's
descriptor. Windows cannot, and there the resolved-path check is the only guard."""

_SEPARATOR = re.compile(r"[\\/]" if os.altsep else re.escape(os.sep))
"""What separates path components *here*.

POSIX allows a backslash inside a file name and Windows reads it as a separator,
so a rule that accepts both everywhere makes one platform read a name as two
components: `foo\\bar` is one file on POSIX and a directory plus a file on
Windows. The containment check, the `..` refusal and the descriptor walk all use
this one pattern, so the path that is validated is the path that is read."""


def file_sha(path: str) -> str:
    """The digest a `file:` condition records for *path*, or ``""`` when it cannot
    be read.

    Bounded on purpose (`MAX_HASH_BYTES`) and limited to regular files: a condition
    names a source file, so a device, a directory and a multi-gigabyte artefact are
    all "cannot tell" rather than something to read into memory."""
    try:
        descriptor = os.open(path, os.O_RDONLY | _NOFOLLOW)
    except (OSError, ValueError):
        # `ValueError` is an embedded NUL: `os.open` refuses the name outright.
        return ""
    return _digest_of(descriptor)


def _digest_of(descriptor: int) -> str:
    """The digest behind *descriptor*, which is closed — ``""`` when it cannot be read.

    Everything is settled from the descriptor: `fstat` refuses anything that is not
    a regular file and bounds the read, and a file that grows past the bound while
    it is being read is "cannot tell" rather than a digest of the part that fit. A
    name is never resolved a second time, so what is hashed is what was checked."""
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
    if len(content) > MAX_HASH_BYTES:
        # The file grew between `fstat` and the read, so this is the digest of a
        # truncated snapshot — not of the file the condition names.
        return ""
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
    if any(ord(character) < 32 for character in value):
        # A NUL can never be in a name, and `realpath` raises on one rather than
        # answering; the rest of the C0 range is no more a path a note can name.
        # A condition is text a model wrote, so it is refused here, not trusted.
        return ""
    if any(part == ".." for part in _SEPARATOR.split(value)):
        return ""
    inside = os.path.realpath(root)
    target = os.path.realpath(os.path.join(inside, value))
    try:
        if os.path.commonpath([inside, target]) != inside:
            return ""
    except ValueError:
        return ""
    return target


def _open_below(directory: str, relative: str) -> int:
    """*relative* opened for reading from *directory*, following no symlink on the way.

    `O_NOFOLLOW` guards the last component only, so a directory swapped for a
    symlink after the path was validated would still be followed — and the read
    would leave the repository without ever breaking the earlier check. Each
    component is opened relative to the descriptor of the one before it, so there is
    no name left to re-resolve once the parent has been handed over.

    On a platform without `dir_fd` this degrades to one `O_NOFOLLOW` open, which is
    the guarantee `file_sha` has: the final name cannot be a link, an intermediate
    one is only as good as the validation."""
    parts = [part for part in _SEPARATOR.split(relative) if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        raise PermissionError(f"{relative!r} is not a path below {directory!r}")
    if not _CAN_OPEN_RELATIVE:
        return os.open(os.path.join(directory, *parts), os.O_RDONLY | _NOFOLLOW)
    descriptor = os.open(directory, os.O_RDONLY | _DIRECTORY)
    try:
        for part in parts[:-1]:
            following = os.open(
                part, os.O_RDONLY | _DIRECTORY | _NOFOLLOW, dir_fd=descriptor
            )
            os.close(descriptor)
            descriptor = following
        return os.open(parts[-1], os.O_RDONLY | _NOFOLLOW, dir_fd=descriptor)
    finally:
        os.close(descriptor)


def _condition_digest(root: str, value: str) -> str | None:
    """The digest of the file *value* names in *root* — ``None`` gone, ``""`` unreadable.

    *value* is validated first and read second, and the two steps are about the same
    object: the validation resolves the name, the walk opens the resolved components
    without following a link. Nothing is reopened by a name that was checked
    earlier, so a rename or a symlink between the two cannot move the read."""
    target = condition_path(value, root)
    if not target:
        return ""
    inside = os.path.realpath(root)
    try:
        descriptor = _open_below(inside, os.path.relpath(target, inside))
    except FileNotFoundError:
        return None
    except OSError:
        return ""
    return _digest_of(descriptor) or ""


def checkout_id(root: str) -> str:
    """The tree a digest is taken in, as a short opaque digest; ``""`` for none.

    The repository tag is a directory name, which two checkouts can share. A
    digest compared in the wrong one is a mismatch about somebody else's file, and
    a mismatch retires the note — so the tree itself is recorded beside the digest
    and has to match before a hash means anything. A checkout that moved answers
    "cannot tell" (a different id), which keeps the note.

    The id is a digest rather than the path so a note never spells out somebody's
    home directory, and so it survives being read on another machine without
    pretending to know that machine's layout."""
    if not root:
        return ""
    return hashlib.sha256(os.path.realpath(root).encode()).hexdigest()[:SHA_LENGTH]


def condition_digest(text: str, root: str) -> str:
    """The digest *text* records for its file, or ``""`` when it records none.

    A `file:` condition names a path. The digest says what that path held when the
    note was written, and the note stores it beside the condition — in
    `applies_when_digest`, never appended to the value. Inside the value it cannot
    be told apart from a path that happens to end in twelve hex digits
    (`config@deadbeefcafe` is a legal file name), and a reader that guessed wrong
    would hide a note nobody touched.

    No root means no repository was in hand, and a digest taken from the process's
    own directory would point at whatever happens to sit beside a later reader. A
    path that leaves the tree (`condition_path`) and a file that cannot be read
    are equally unstampable: the note keeps the condition and carries no digest,
    which reads as uncheckable and keeps the note.
    """
    condition = parse_condition(text)
    if condition is None or condition.kind != "file" or not root:
        return ""
    if not condition_path(condition.value, root):
        return ""
    return _condition_digest(root, condition.value) or ""


def is_condition_met(
    condition: Condition, root: str, version: str, origin: Origin = Origin()
) -> bool | None:
    """Whether *condition* still holds — ``None`` when this machine cannot tell.

    ``None`` is not "false": a condition this module cannot evaluate keeps its
    note alive, because retiring a note on a failure to look would delete memory
    the first time a path moved.

    *origin* is what the note recorded about the file it names, and every part of
    it has to agree with this machine before a digest is compared (`Origin`):
    without that, the same relative path in another checkout answers about another
    file, and a mismatch there retires a note that is still true."""
    if condition.kind == "file":
        return _is_file_unchanged(condition.value, root, origin)
    if condition.kind == "version":
        return _is_version_matching(condition.value, version)
    if condition.kind == "setting":
        return _is_setting_matching(condition.value)
    if condition.kind == "date":
        return _is_before_date(condition.value)
    return None


def _is_file_unchanged(value: str, root: str, origin: Origin) -> bool | None:
    if not origin.repo:
        # The note belongs to another repository, or to no place at all. Its
        # relative path here is not the file it was written about.
        return None
    if not _SHA_RE.match(origin.digest or "") or not origin.checkout:
        # Nothing was recorded, so there is no digest to compare against. Reading
        # the value as if one were there would report a live note as false.
        return None
    if origin.checkout != checkout_id(root):
        # Same directory name, different tree: a mismatch here would be about
        # somebody else's file, which is the most expensive way to be wrong.
        return None
    digest = _condition_digest(root, value)
    if digest is None:
        # The file is gone, which is a change, not an inability to check.
        return False
    if not digest:
        # Not in the tree, present but unreadable, not a regular file, or past
        # `MAX_HASH_BYTES`: we cannot tell, and a note is never hidden on a
        # failure to look.
        return None
    return digest == origin.digest


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
    wrong — `root` names this checkout's tree, not that note's. The digest is
    still checked against the tree it was taken in (`Origin.checkout`): two
    checkouts can share a directory name, and a file condition answered in the
    wrong one is a false expiry about somebody else's file."""
    resolved = current_version() if version is None else version
    expired: set[str] = set()
    for note in notes:
        condition = parse_condition(note.applies_when)
        if condition is None:
            continue
        origin = Origin(
            repo=note.repo if note.repo and note.repo == current else "",
            checkout=note.applies_when_checkout,
            digest=note.applies_when_digest,
        )
        if is_condition_met(condition, root, resolved, origin) is False:
            expired.add(note.rel)
    return expired
