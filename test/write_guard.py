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

The guard sees writes made by Python in the process it runs in; a subprocess
inherits the redirected `HOME` but is not hooked.
"""

import os
import sys
from collections.abc import Iterable

# Directories and files the tools around the suite write into the repository:
# bytecode, coverage data, reports, caches. A write below one is not a leak.
ARTIFACT_NAMES = frozenset(
    {
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
ARTIFACT_PREFIXES = (".coverage",)

_WRITE_MODE_CHARACTERS = "wax+"
_WRITE_FLAGS = (
    os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND  # POSIX + Windows
)


def _canonical(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))


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


def _is_resolvable(args: tuple) -> bool:
    """False for a relative `os.open` path: its `dir_fd`, if any, is not in the event."""
    mode = args[1] if len(args) > 1 else None
    path = _as_text(args[0])
    return mode is not None or (path is not None and os.path.isabs(path))


def written_paths(event: str, args: tuple) -> list[object]:
    """Return the paths an audit event creates or opens for writing."""
    if event == "open":
        return [args[0]] if _writes_through_open(args) and _is_resolvable(args) else []
    if event == "os.mkdir":
        return [args[0]]
    if event in ("os.rename", "os.link"):
        return [args[1]]
    if event == "os.symlink":
        return [args[1]]
    return []


class WriteGuard:
    """Refuse writes into forbidden roots, except for known tool artifacts.

    `allowed_roots` win over `forbidden_roots`: on Windows the temp directory
    lives inside the real home.
    """

    def __init__(
        self, forbidden_roots: Iterable[str], allowed_roots: Iterable[str]
    ) -> None:
        self._forbidden = [_canonical(r) for r in forbidden_roots if r]
        self._allowed = [_canonical(r) for r in allowed_roots if r]
        self.violations: list[str] = []
        self._checking = False

    def find_forbidden(self, path: str) -> str | None:
        """Return the canonical path when writing it is forbidden, else None."""
        target = _canonical(path)
        if any(_is_inside(target, root) for root in self._allowed):
            return None
        for root in self._forbidden:
            if _is_inside(target, root):
                relative = os.path.relpath(target, root)
                return None if _is_artifact(relative) else target
        return None

    def audit(self, event: str, args: tuple) -> None:
        """`sys.addaudithook` callback: record and refuse a forbidden write."""
        if self._checking:
            return
        self._checking = True
        try:
            for raw in written_paths(event, args):
                text = _as_text(raw)
                offender = self.find_forbidden(text) if text else None
                if offender is not None:
                    self.violations.append(offender)
                    raise PermissionError(
                        f"The test suite may only write inside temp, but a test "
                        f"wrote to {offender}. Use tmp_path (or monkeypatch the "
                        f"setting that points there) instead."
                    )
        finally:
            self._checking = False


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
