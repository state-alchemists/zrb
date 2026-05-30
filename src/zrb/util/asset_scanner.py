"""Recursive file-system scanning utility shared by SkillManager and SubAgentManager.

Replaces the duplicated ``_scan_dir`` / ``_scan_dir_recursive`` pattern that
previously lived in both ``loader_mixin.py`` and ``skill/manager.py``.
"""

from collections.abc import Callable
from pathlib import Path

IGNORE_DIRS = [
    ".git",
    "node_modules",
    "__pycache__",
    "venv",
    "dist",
    "build",
    "htmlcov",
]


def scan_files(
    directory: Path,
    max_depth: int,
    on_file_found: Callable[[Path], None],
    ignore_dirs: list[str] | None = None,
) -> None:
    """Recursively walk *directory* up to *max_depth* calling *on_file_found*.

    Skips hidden directories (leading ``.``) and any listed in *ignore_dirs*
    (defaults to :data:`IGNORE_DIRS`). Silently ignores ``PermissionError``
    and ``OSError`` so that one inaccessible branch never aborts the full scan.
    """
    effective_ignore = ignore_dirs if ignore_dirs is not None else IGNORE_DIRS
    try:
        search_path = directory.resolve()
        _scan_recursive(
            search_path, search_path, max_depth, 0, on_file_found, effective_ignore
        )
    except Exception:
        pass


def _scan_recursive(
    base_dir: Path,
    current_dir: Path,
    max_depth: int,
    current_depth: int,
    on_file_found: Callable[[Path], None],
    ignore_dirs: list[str],
) -> None:
    if current_depth > max_depth:
        return
    try:
        for item in current_dir.iterdir():
            if item.is_dir():
                if item.name in ignore_dirs or item.name.startswith("."):
                    continue
                _scan_recursive(
                    base_dir,
                    item,
                    max_depth,
                    current_depth + 1,
                    on_file_found,
                    ignore_dirs,
                )
            elif item.is_file():
                on_file_found(item)
    except (PermissionError, OSError):
        pass
