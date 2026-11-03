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
    condition nobody can evaluate.

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
from dataclasses import dataclass
from datetime import date

FILE_PREFIX = "file:"
VERSION_PREFIX = "version:"
SETTING_PREFIX = "setting:"
DATE_PREFIX = "date:"

SHA_LENGTH = 12
"""How much of the digest a condition records: enough to tell a file changed,
short enough that a hand-written condition stays readable."""

_TRUE_TOKENS = frozenset({"on", "true", "yes", "1", "enabled"})
_FALSE_TOKENS = frozenset({"off", "false", "no", "0", "disabled"})
_VERSION_RE = re.compile(r"^(<=|>=|==|=|<|>)?\s*(\d+(?:\.\d+)*)$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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
    """The digest a `file:` condition records for *path*, or ``""`` if unreadable."""
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:SHA_LENGTH]
    except OSError:
        return ""


def stamp(text: str, root: str) -> str:
    """*text* with the file condition's hash filled in, recorded now.

    A `file:` condition that names no hash is stamped here, so the note says what
    it was written against rather than asking a later reader to guess. A file
    that cannot be read, or a condition that is already stamped, is returned
    unchanged: a note is never refused for naming a path that does not exist yet.
    """
    condition = parse_condition(text)
    if condition is None or condition.kind != "file":
        return text
    path, _, recorded = condition.value.rpartition("@")
    if recorded and path:
        return text
    target = os.path.join(root, condition.value) if root else condition.value
    digest = file_sha(target)
    if not digest:
        return text
    return f"{FILE_PREFIX}{condition.value}@{digest}"


def is_condition_met(condition: Condition, root: str, version: str) -> bool | None:
    """Whether *condition* still holds — ``None`` when this machine cannot tell.

    ``None`` is not "false": a condition this module cannot evaluate keeps its
    note alive, because retiring a note on a failure to look would delete memory
    the first time a path moved."""
    if condition.kind == "file":
        return _is_file_unchanged(condition.value, root)
    if condition.kind == "version":
        return _is_version_matching(condition.value, version)
    if condition.kind == "setting":
        return _is_setting_matching(condition.value)
    if condition.kind == "date":
        return _is_before_date(condition.value)
    return None


def _is_file_unchanged(value: str, root: str) -> bool | None:
    path, _, recorded = value.rpartition("@")
    if not recorded:
        return None
    target = os.path.join(root, path) if root else path
    digest = file_sha(target)
    if not digest:
        # The file is gone, which is a change, not an inability to check.
        return False
    return digest == recorded


def _is_version_matching(value: str, version: str) -> bool | None:
    found = _VERSION_RE.match(value.strip())
    if not found:
        return None
    operator, wanted = found.group(1) or "=", found.group(2)
    current = _version_tuple(version)
    target = _version_tuple(wanted)
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


def _version_tuple(text: str) -> tuple[int, ...] | None:
    """The numeric parts of *text*, or ``None`` when it is not a version."""
    found = _VERSION_RE.match(text.strip().lstrip("v"))
    if not found:
        return None
    parts = tuple(int(part) for part in found.group(2).split("."))
    while len(parts) > 1 and parts[-1] == 0:
        parts = parts[:-1]
    return parts


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


def expired_note_rels(notes, root: str, version: str | None = None) -> set[str]:
    """The notes whose condition is *known to be* false, by journal-relative path.

    A note with no condition, a prose condition, or one this machine cannot
    evaluate is not here: expiry removes what is disproved, never what is merely
    unchecked."""
    resolved = current_version() if version is None else version
    expired: set[str] = set()
    for note in notes:
        condition = parse_condition(note.applies_when)
        if condition is None:
            continue
        if is_condition_met(condition, root, resolved) is False:
            expired.add(note.rel)
    return expired
