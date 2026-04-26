import glob
import os
from typing import Any

from zrb.config.config import CFG
from zrb.util.file import is_path_excluded

DEFAULT_EXCLUDED_PATTERNS = [
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".Python",
    "build",
    "dist",
    ".env",
    ".venv",
    "env",
    "venv",
    ".idea",
    ".vscode",
    ".git",
    "node_modules",
    ".pytest_cache",
    ".coverage",
    "htmlcov",
    ".claude",
]


def _truncate_file_list(
    sorted_files: list[str],
) -> tuple[list[str], int | None]:
    """
    Truncates a sorted file list to head+tail using the configured line limit.

    Returns (files, omitted_count). If no truncation needed, omitted_count is None.
    """
    head = tail = CFG.LLM_FILE_READ_LINES // 2
    if len(sorted_files) > head + tail:
        truncated = sorted_files[:head] + sorted_files[-tail:]
        omitted = len(sorted_files) - head - tail
        return truncated, omitted
    return sorted_files, None


def list_files(
    path: str = ".",
    auto_truncate: bool = True,
    exclude_patterns: list[str] | None = None,
) -> dict[str, Any]:
    """
    Recursively lists files up to 3 levels deep.

    Auto-excludes `.git`, `node_modules`, `__pycache__`, etc. Sorted alphabetically.
    Pass `exclude_patterns=[]` to include all files.
    """
    all_files: list[str] = []
    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        return {"error": f"Path does not exist: {abs_path}"}

    depth = 3
    patterns_to_exclude = (
        exclude_patterns if exclude_patterns is not None else DEFAULT_EXCLUDED_PATTERNS
    )

    initial_depth = abs_path.rstrip(os.sep).count(os.sep)
    for root, dirs, files in os.walk(abs_path, topdown=True):
        current_depth = root.rstrip(os.sep).count(os.sep) - initial_depth
        if current_depth >= depth - 1:
            del dirs[:]

        dirs[:] = [
            d
            for d in dirs
            if not d.startswith(".") and not is_path_excluded(d, patterns_to_exclude)
        ]

        for filename in files:
            if not filename.startswith(".") and not is_path_excluded(
                filename, patterns_to_exclude
            ):
                full_path = os.path.join(root, filename)
                rel_full_path = os.path.relpath(full_path, abs_path)
                if not is_path_excluded(rel_full_path, patterns_to_exclude):
                    all_files.append(rel_full_path)

    sorted_files = sorted(all_files)

    if auto_truncate:
        truncated, omitted = _truncate_file_list(sorted_files)
        if omitted is not None:
            head = tail = CFG.LLM_FILE_READ_LINES // 2
            return {
                "files": truncated,
                "truncation_notice": f"[TRUNCATED {omitted} files. Showing first {head} and last {tail} files.]",
            }

    return {"files": sorted_files}


def glob_files(
    pattern: str,
    path: str = ".",
    auto_truncate: bool = True,
    exclude_patterns: list[str] | None = None,
) -> dict[str, Any]:
    """
    Finds files matching glob patterns (e.g., `**/*.py`). Supports `**` for recursive search.

    Auto-excludes `.git`, `node_modules`, `__pycache__`, etc. Sorted alphabetically.
    Pass `exclude_patterns=[]` to include all files.
    """
    found_files = []
    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        return {"error": f"Path does not exist: {abs_path}"}

    patterns_to_exclude = (
        exclude_patterns if exclude_patterns is not None else DEFAULT_EXCLUDED_PATTERNS
    )

    search_pattern = os.path.join(abs_path, pattern)
    candidates = glob.glob(search_pattern, recursive=True)

    for candidate in candidates:
        if os.path.isdir(candidate):
            continue

        rel_path = os.path.relpath(candidate, abs_path)

        if any(part.startswith(".") for part in rel_path.split(os.sep)):
            continue

        if is_path_excluded(rel_path, patterns_to_exclude):
            continue

        found_files.append(rel_path)

    sorted_files = sorted(found_files)

    if auto_truncate:
        truncated, omitted = _truncate_file_list(sorted_files)
        if omitted is not None:
            head = tail = CFG.LLM_FILE_READ_LINES // 2
            return {
                "files": truncated,
                "truncation_notice": f"[TRUNCATED {omitted} files. Showing first {head} and last {tail} files.]",
            }

    return {"files": sorted_files}
