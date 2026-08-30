import glob
import os
from typing import Annotated, Any

from pydantic import Field

from zrb.config.config import CFG
from zrb.llm.tool.file_observation import record_listed
from zrb.util.file import is_path_excluded, walk_files
from zrb.util.truncate import truncate_items

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
    Keeps leading files within the output char budget (head-keep).

    Returns (files, omitted_count). If no truncation needed, omitted_count is None.
    """
    kept, omitted = truncate_items(sorted_files, CFG.LLM_MAX_OUTPUT_CHARS)
    return kept, (omitted or None)


def list_files(
    path: Annotated[
        str, Field(description="Directory to list, recursively up to 3 levels deep.")
    ] = ".",
    exclude_patterns: Annotated[
        list[str] | None,
        Field(
            description=(
                "Glob patterns to exclude. Defaults to a standard set "
                "(.git, node_modules, __pycache__, etc.); pass [] to include all."
            )
        ),
    ] = None,
    include_hidden: Annotated[
        bool, Field(description="False (default) hides dotfiles; True surfaces them.")
    ] = False,
) -> dict[str, Any]:
    """
    Recursively lists files up to 3 levels deep. Auto-excludes .git, node_modules,
    __pycache__, etc. Pass exclude_patterns=[] to include all. Dotfiles are hidden
    by default; use include_hidden=True to surface them.
    """
    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        return {
            "error": (
                f"Path does not exist: {abs_path}. "
                "[SYSTEM SUGGESTION]: List the nearest parent that does "
                "exist to see the real layout."
            )
        }

    patterns_to_exclude = (
        exclude_patterns if exclude_patterns is not None else DEFAULT_EXCLUDED_PATTERNS
    )

    sorted_files = walk_files(
        abs_path,
        include_hidden=include_hidden,
        depth=3,
        excluded_patterns=patterns_to_exclude,
    )

    truncated, omitted = _truncate_file_list(sorted_files)
    record_listed(abs_path, [os.path.join(abs_path, p) for p in truncated])
    if omitted is not None:
        return {
            "files": truncated,
            "truncation_notice": (
                f"[TRUNCATED {omitted} files. Showing first {len(truncated)} "
                f"of {len(sorted_files)}.]"
            ),
        }

    return {"files": sorted_files}


def glob_files(
    pattern: Annotated[str, Field(description="Glob pattern to match, e.g. **/*.py.")],
    path: Annotated[str, Field(description="Directory to search under.")] = ".",
    exclude_patterns: Annotated[
        list[str] | None,
        Field(
            description=(
                "Glob patterns to exclude. Defaults to a standard set "
                "(.git, node_modules, __pycache__, etc.); pass [] to include all."
            )
        ),
    ] = None,
    include_hidden: Annotated[
        bool, Field(description="False (default) skips dotfiles; True matches them.")
    ] = False,
) -> dict[str, Any]:
    """
    Finds files matching glob patterns (e.g. **/*.py). Auto-excludes .git, node_modules,
    __pycache__, etc. Pass exclude_patterns=[] to include all. Dotfiles are hidden
    by default; use include_hidden=True to match them.
    """
    found_files = []
    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        return {
            "error": (
                f"Path does not exist: {abs_path}. "
                "[SYSTEM SUGGESTION]: List the nearest parent that does "
                "exist to see the real layout."
            )
        }

    patterns_to_exclude = (
        exclude_patterns if exclude_patterns is not None else DEFAULT_EXCLUDED_PATTERNS
    )

    search_pattern = os.path.join(abs_path, pattern)
    candidates = glob.glob(
        search_pattern, recursive=True, include_hidden=include_hidden
    )

    for candidate in candidates:
        if os.path.isdir(candidate):
            continue

        rel_path = os.path.relpath(candidate, abs_path)

        if not include_hidden and any(
            part.startswith(".") for part in rel_path.split(os.sep)
        ):
            continue

        if is_path_excluded(rel_path, patterns_to_exclude):
            continue

        found_files.append(rel_path)

    sorted_files = sorted(found_files)

    truncated, omitted = _truncate_file_list(sorted_files)
    record_listed(abs_path, [os.path.join(abs_path, p) for p in truncated])
    if omitted is not None:
        return {
            "files": truncated,
            "truncation_notice": (
                f"[TRUNCATED {omitted} files. Showing first {len(truncated)} "
                f"of {len(sorted_files)}.]"
            ),
        }

    return {"files": sorted_files}
