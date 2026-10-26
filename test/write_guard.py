"""Keep the test suite's writes inside temp directories.

A test that writes to the developer's home or into the source tree leaves
state nobody sees: 96 session logs per run in the real `~/.zrb/session`, and
`test-generated-*` directories (gitignored) beside the scaffolder tests.

`conftest.py` enforces two layers. It points `HOME` and `USERPROFILE` at a
per-run directory, so everything resolved through `os.path.expanduser` lands in
temp. It then installs `WriteGuard` as a process-wide audit hook, which refuses
a write to the two places the suite has no business writing — the real home
and the repository — whatever path a test spells. A write anywhere else
(`tmp_path`, the temp directory, `/dev/null`) is not the guard's concern.

The guard judges creations, writes and deletions (`open` for writing,
`os.mkdir`, `os.remove`/`os.unlink`, `os.rmdir`, and both ends of `os.rename`,
`os.replace` and `os.link`; `shutil.rmtree` and `shutil.move` go through these).
A relative path is resolved against the cwd, or against its `dir_fd` through
`/proc/self/fd` (Linux) or `F_GETPATH` (macOS); where a descriptor cannot be
traced (Windows) the guard refuses rather than guess.

Known blind spots: a subprocess inherits the redirected `HOME` but is not
hooked; and the `open` audit event carries no `dir_fd`, so a relative
`os.open(name, flags, dir_fd=fd)` cannot be told from one against the cwd and is
not judged at all (a relative `open()` is judged against the cwd).
"""

import os
import sys
from collections.abc import Iterable

# Directories and files the tools around the suite write into the repository:
# bytecode, coverage data, reports, caches. A write below one is not a leak.
ARTIFACT_NAMES = frozenset(
    os.path.normcase(name)
    for name in {
        "__pycache__",
        ".pytest_cache",
        ".hypothesis",
        ".mypy_cache",
        ".ruff_cache",
        ".pyright",
        "htmlcov",
        "node_modules",
        "dist",
        "build",
        ".venv",
        "venv",
        ".tox",
        "README.pypi.md",
    }
)
ARTIFACT_PREFIXES = (os.path.normcase(".coverage"),)

_WRITE_MODE_CHARACTERS = "wax+"
_WRITE_FLAGS = (
    os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND  # POSIX + Windows
)


def _canonical(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))


def _canonical_entry(path: str) -> str:
    """Canonicalize the directory entry a path names, without following it.

    `os.remove`, `os.rename`, `os.link`, `os.symlink` and `os.mkdir` act on the
    entry itself: for a symlink, that is the link, not what it points at. The
    parent is resolved; the final name is kept as it is.
    """
    parent, name = os.path.split(os.path.abspath(path))
    if not name:
        return _canonical(parent)
    return os.path.join(_canonical(parent), os.path.normcase(name))


def _is_inside(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:  # different drives on Windows
        return False


def _as_text(path: object) -> str | None:
    """Return a filesystem path as text, or None for a file descriptor."""
    if isinstance(path, int):
        return None
    try:
        text = os.fsdecode(os.fspath(path))  # type: ignore[arg-type]
    except TypeError:
        return None
    return text or None


def _writes_through_open(args: tuple) -> bool:
    mode = args[1] if len(args) > 1 else None
    if isinstance(mode, str):
        return any(c in mode for c in _WRITE_MODE_CHARACTERS)
    flags = args[2] if len(args) > 2 else None
    return isinstance(flags, int) and bool(flags & _WRITE_FLAGS)


def _opens_judgeably_for_writing(args: tuple) -> bool:
    if not _writes_through_open(args):
        return False
    text = _as_text(args[0])
    is_os_open = not isinstance(args[1] if len(args) > 1 else None, str)
    return not (is_os_open and text is not None and not os.path.isabs(text))


def _fd_directory(fd: int) -> str | None:
    """Return the directory a descriptor refers to, or None if unknowable.

    Chosen by what the system offers, never by `sys.platform`: a test may patch
    the platform name, and `F_GETPATH` does not exist on Linux."""
    try:
        if os.path.isdir("/proc/self/fd"):
            return os.readlink(f"/proc/self/fd/{fd}")
        import fcntl  # lazy: platform-only — POSIX; Windows has no `fcntl`

        get_path = getattr(fcntl, "F_GETPATH", None)  # macOS only
        if get_path is None:
            return None
        raw = fcntl.fcntl(fd, get_path, b"\0" * 1024)
        return os.fsdecode(raw.split(b"\0", 1)[0])
    except (OSError, ImportError):
        return None


def _as_dir_fd(value: object) -> int | None:
    """A real descriptor from an audit `dir_fd` slot; None means the cwd."""
    return value if isinstance(value, int) and value >= 0 else None


def resolve_target(path: object, dir_fd: object = None) -> str | None:
    """Return the absolute path the OS would use, or None if unresolvable.

    A relative path is taken against the descriptor when one is given, else
    against the cwd. A descriptor that cannot be traced to a directory (Windows,
    a closed fd) yields None, which the guard treats as forbidden.
    """
    text = _as_text(path)
    if text is None:
        return ""  # a descriptor, not a path: nothing to judge
    if os.path.isabs(text):
        return text
    fd = _as_dir_fd(dir_fd)
    if fd is None:
        return os.path.join(os.getcwd(), text)
    base = _fd_directory(fd)
    return None if base is None else os.path.join(base, text)


def written_targets(event: str, args: tuple) -> list[tuple[object, object, bool]]:
    """Return `(path, dir_fd, follows)` for each path an audit event changes.

    `follows` is True when the operation acts on what a final symlink points at
    (writing or truncating a file), False when it acts on the directory entry.
    `os.ftruncate` emits `os.truncate` with a descriptor, which carries no path
    and is skipped: a known blind spot, with `chmod`, `utime` and `setxattr`
    (they change metadata, not content).

    `open` events carry no `dir_fd`, so a relative `os.open` name (the one `open`
    event with no mode text) may be relative to a descriptor and is not judged:
    a known blind spot. A relative `open()` is judged against the cwd.
    """
    if event == "open":
        return [(args[0], None, True)] if _opens_judgeably_for_writing(args) else []
    if event == "os.truncate":
        return [(args[0], None, True)]
    if event in ("os.mkdir", "os.remove", "os.rmdir"):
        return [(args[0], args[2] if event == "os.mkdir" else args[1], False)]
    if event in ("os.rename", "os.link"):
        return [(args[0], args[2], False), (args[1], args[3], False)]
    if event == "os.symlink":
        return [(args[1], args[2], False)]
    return []


class WriteGuard:
    """Refuse writes and deletions in forbidden roots, except tool artifacts.

    `allowed_roots` win over `forbidden_roots`: on Windows the temp directory
    lives inside the real home. A move is judged by both its ends, so taking a
    repository file out to temp is refused as well as putting one in.
    """

    def __init__(
        self, forbidden_roots: Iterable[str], allowed_roots: Iterable[str]
    ) -> None:
        self._forbidden = [_canonical(r) for r in forbidden_roots if r]
        self._allowed = [_canonical(r) for r in allowed_roots if r]
        self.violations: list[str] = []
        self._checking = False

    def find_forbidden(self, path: str, follows: bool = True) -> str | None:
        """Return the canonical path when changing it is forbidden, else None.

        `follows=False` judges the directory entry itself (a symlink is not
        resolved), for deleting, moving and creating entries.
        """
        target = _canonical(path) if follows else _canonical_entry(path)
        allowed = [r for r in self._allowed if _is_inside(target, r)]
        forbidden = [r for r in self._forbidden if _is_inside(target, r)]
        if not forbidden:
            return None
        # The most specific root decides, so temp inside the repository is
        # allowed and a repository inside temp (a checkout under /tmp) is not.
        # A tie goes to the forbidden root.
        deepest_forbidden = max(forbidden, key=len)
        if allowed and len(max(allowed, key=len)) > len(deepest_forbidden):
            return None
        relative = os.path.relpath(target, deepest_forbidden)
        return None if _is_artifact(relative) else target

    def audit(self, event: str, args: tuple) -> None:
        """`sys.addaudithook` callback: record and refuse a forbidden write."""
        if self._checking:
            return
        self._checking = True
        try:
            for path, dir_fd, follows in written_targets(event, args):
                self._judge(path, dir_fd, follows)
        finally:
            self._checking = False

    def _judge(self, path: object, dir_fd: object, follows: bool) -> None:
        resolved = resolve_target(path, dir_fd)
        if resolved is None:
            self._refuse(
                f"{path!r} is relative to a directory descriptor that cannot be "
                f"traced to a path on this platform, so it cannot be shown to be "
                f"inside temp",
                str(path),
            )
        elif resolved:
            offender = self.find_forbidden(resolved, follows)
            if offender is not None:
                self._refuse(f"a test wrote to {offender}", offender)

    def _refuse(self, reason: str, recorded: str) -> None:
        self.violations.append(recorded)
        raise PermissionError(
            f"The test suite may only write inside temp, but {reason}. "
            f"Use tmp_path (or monkeypatch the setting that points there) instead."
        )


def _is_artifact(relative_path: str) -> bool:
    return any(
        part in ARTIFACT_NAMES or part.startswith(ARTIFACT_PREFIXES)
        for part in relative_path.split(os.sep)
    )


_installed: WriteGuard | None = None


def install(forbidden_roots: Iterable[str], allowed_roots: Iterable[str]) -> WriteGuard:
    """Install the process-wide guard once; later calls return the same one.

    An audit hook cannot be removed, so a second `pytest_configure` in the same
    process (the hermetic-environment test re-runs it) must not stack another.
    """
    global _installed
    if _installed is None:
        _installed = WriteGuard(forbidden_roots, allowed_roots)
        sys.addaudithook(_installed.audit)
    return _installed
