import glob
import os
import subprocess
from typing import Annotated, Any

from pydantic import Field

from zrb.config.config import CFG
from zrb.llm.tool.file_observation import record_listed
from zrb.util.file import matches_any_pattern, walk_files
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


def _listing_result(abs_path: str, sorted_files: list[str]) -> dict[str, Any]:
    """Cap the listing and record what was shown for RM's listed-path check."""
    truncated, omitted = _truncate_file_list(sorted_files)
    record_listed(abs_path, [os.path.join(abs_path, p) for p in truncated])
    if omitted is None:
        return {"files": sorted_files}
    return {
        "files": truncated,
        "truncation_notice": (
            f"[TRUNCATED {omitted} files. Showing first {len(truncated)} "
            f"of {len(sorted_files)}.]"
        ),
    }


def _truncate_file_list(
    sorted_files: list[str],
) -> tuple[list[str], int | None]:
    """Head-keep within the output budget; ``(files, omitted_count or None)``."""
    kept, omitted = truncate_items(sorted_files, CFG.LLM_MAX_OUTPUT_CHARS)
    return kept, (omitted or None)


def _git_visible_files(abs_path: str) -> set[str] | None:
    """Files git would show under *abs_path* (tracked + untracked, not ignored).

    ``None`` when this is not a git checkout or git is unavailable, so the
    caller keeps the unfiltered walk instead of hiding everything.
    """
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                abs_path,
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
            ],
            capture_output=True,
            text=True,
            timeout=CFG.LLM_GIT_CMD_TIMEOUT / 1000,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return {
        os.path.normpath(line.replace("/", os.sep))
        for line in result.stdout.splitlines()
        if line
    }


def _without_gitignored(abs_path: str, files: list[str]) -> list[str]:
    """Drop files `.gitignore` hides, when *abs_path* is inside a checkout."""
    visible = _git_visible_files(abs_path)
    if visible is None:
        return files
    return [path for path in files if os.path.normpath(path) in visible]


def _summarize_by_top_level(files: list[str]) -> list[dict[str, Any]]:
    """File counts per immediate child (`.` for files directly in the root)."""
    counts: dict[str, int] = {}
    for path in files:
        top = path.split(os.sep, 1)[0] if os.sep in path else "."
        counts[top] = counts.get(top, 0) + 1
    return [{"path": top, "files": count} for top, count in sorted(counts.items())]


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
    depth: Annotated[
        int,
        Field(
            description=(
                "How many directory levels below `path` to descend (default 3; "
                "1 lists only the direct children)."
            )
        ),
    ] = 3,
    gitignore: Annotated[
        bool,
        Field(
            description=(
                "True (default) hides files .gitignore excludes. False lists "
                "them, which is useful only when the ignored tree is the target."
            )
        ),
    ] = True,
    summary: Annotated[
        bool,
        Field(
            description=(
                "False (default) returns every path. True returns per-directory "
                "file counts instead, which is the cheap way to orient in a "
                "large tree."
            )
        ),
    ] = False,
) -> dict[str, Any]:
    """
    Lists a directory tree, for orienting in an unfamiliar area of a project.

    When you already know the name or extension you want, Glob is narrower;
    when you want what is *inside* the files, Grep. Listing a large tree to
    locate one file you could have named is the expensive way to find it.

    A git checkout hides what `.gitignore` excludes (generated coverage HTML,
    build output), so the listing is the repository's real shape rather than
    every artifact on disk. `summary=True` returns counts per top-level
    directory instead of every path.
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
        depth=depth,
        excluded_patterns=patterns_to_exclude,
    )
    if gitignore:
        sorted_files = _without_gitignored(abs_path, sorted_files)
    if summary:
        return {
            "path": abs_path,
            "total_files": len(sorted_files),
            "directories": _summarize_by_top_level(sorted_files),
        }

    return _listing_result(abs_path, sorted_files)


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
    Finds files by name or extension, anywhere under a directory.

    This searches paths, not contents — use Grep to search what is inside the
    files, and LS when you do not yet know what you are looking for.
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

        if matches_any_pattern(rel_path, patterns_to_exclude):
            continue

        found_files.append(rel_path)

    sorted_files = sorted(found_files)

    return _listing_result(abs_path, sorted_files)
