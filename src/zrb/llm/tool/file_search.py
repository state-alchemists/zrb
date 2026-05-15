import fnmatch
import os
import re
import shutil
import subprocess
import time
from typing import Any

from zrb.config.config import CFG
from zrb.llm.tool.file_list import DEFAULT_EXCLUDED_PATTERNS
from zrb.util.file import is_path_excluded
from zrb.util.truncate import truncate_output


def search_files(
    regex: str,
    path: str = ".",
    file_pattern: str = "",
    auto_truncate: bool = True,
    exclude_patterns: list[str] | None = None,
    timeout: float = 30.0,
    context_lines: int = 2,
    files_only: bool = False,
    case_sensitive: bool = True,
) -> dict[str, Any]:
    """
    Searches for a regex pattern across files. Results include line numbers and context.

    `context_lines` (default 2): surrounding lines shown per match.
    `files_only=True`: returns `{"files": [...], "summary": "..."}` — much smaller output.
    `case_sensitive=False`: case-insensitive search.
    `file_pattern`: restrict to specific file types (e.g., `*.py`).
    Lines are truncated at 1000 chars in output.
    """
    start_time = time.time()
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        pattern = re.compile(regex, flags)
    except re.error as e:
        return {"error": f"Invalid regex pattern: {e}"}

    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        return {"error": f"Path not found: {path}"}

    preserved_head_lines = CFG.LLM_FILE_READ_LINES // 4
    preserved_tail_lines = CFG.LLM_FILE_READ_LINES // 4

    patterns_to_exclude = (
        exclude_patterns if exclude_patterns is not None else DEFAULT_EXCLUDED_PATTERNS
    )

    rg_result = _search_with_ripgrep(
        pattern=pattern,
        regex=regex,
        abs_path=abs_path,
        file_pattern=file_pattern,
        case_sensitive=case_sensitive,
        context_lines=context_lines,
        files_only=files_only,
        auto_truncate=auto_truncate,
        patterns_to_exclude=patterns_to_exclude,
        timeout=timeout,
        preserved_head_lines=preserved_head_lines,
        preserved_tail_lines=preserved_tail_lines,
    )
    if rg_result is not None:
        return rg_result

    return _search_with_os_walk(
        abs_path=abs_path,
        pattern=pattern,
        file_pattern=file_pattern,
        patterns_to_exclude=patterns_to_exclude,
        timeout=timeout,
        start_time=start_time,
        context_lines=context_lines,
        files_only=files_only,
        auto_truncate=auto_truncate,
        preserved_head_lines=preserved_head_lines,
        preserved_tail_lines=preserved_tail_lines,
    )


def _build_file_match_entry(
    rel_file_path: str, matches: list[dict[str, Any]], files_only: bool
) -> str | dict[str, Any]:
    """Build a single result entry: file path string or {file, matches} dict."""
    return rel_file_path if files_only else {"file": rel_file_path, "matches": matches}


def _count_actual_matches(matches: list[dict[str, Any]]) -> int:
    """Count matches that have a non-zero line number."""
    return sum(1 for m in matches if m.get("line_number", 0) > 0)


def _truncate_file_results(
    results: list[Any], preserved_head_lines: int, preserved_tail_lines: int
) -> tuple[list[Any], str | None]:
    """Truncate results and return (truncated_list, truncation_notice)."""
    if len(results) <= preserved_head_lines + preserved_tail_lines:
        return results, None
    truncated = results[:preserved_head_lines] + results[-preserved_tail_lines:]
    omitted = len(results) - preserved_head_lines - preserved_tail_lines
    notice = (
        f"[TRUNCATED {omitted} result files. Showing first {preserved_head_lines}"
        f" and last {preserved_tail_lines} files with matches.]"
    )
    return truncated, notice


def _build_search_output(
    result_entries: list[Any],
    match_count: int,
    file_match_count: int,
    searched_file_count: int | None,
    regex: str,
    path: str,
    auto_truncate: bool,
    preserved_head_lines: int,
    preserved_tail_lines: int,
    files_only: bool,
    warning: str | None = None,
) -> dict[str, Any]:
    """Build the final search result dict from accumulated match data.

    Shared by both the ripgrep and the fallback os.walk code paths.
    """
    results = result_entries
    truncation_notice = None
    if auto_truncate:
        results, truncation_notice = _truncate_file_results(
            results, preserved_head_lines, preserved_tail_lines
        )

    if match_count == 0:
        searched = (
            f" (searched {searched_file_count} files)" if searched_file_count else ""
        )
        summary = (
            f"No matches found for pattern '{regex}' in path '{path}'{searched}. "
            f"[SYSTEM SUGGESTION]: Try broadening your regex pattern, removing the "
            f"file_pattern filter, or checking if you're searching in the correct directory."
        )
    else:
        searched = (
            f" (searched {searched_file_count} files)" if searched_file_count else ""
        )
        summary = f"Found {match_count} matches in {file_match_count} files.{searched}"

    if files_only:
        result: dict[str, Any] = {"files": results, "summary": summary}
        if truncation_notice:
            result["truncation_notice"] = truncation_notice
        if warning:
            result["warning"] = warning
        return result

    return {
        "results": results,
        "summary": summary,
        **(  # only include non-None optional fields
            {"truncation_notice": truncation_notice} if truncation_notice else {}
        ),
        **({"warning": warning} if warning else {}),
    }


def _search_with_ripgrep(
    pattern: "re.Pattern",
    regex: str,
    abs_path: str,
    file_pattern: str,
    case_sensitive: bool,
    context_lines: int,
    files_only: bool,
    auto_truncate: bool,
    patterns_to_exclude: list[str],
    timeout: float,
    preserved_head_lines: int,
    preserved_tail_lines: int,
) -> "dict[str, Any] | None":
    """Use ripgrep to find matching files, then extract matches via Python. Returns None on failure."""
    if not shutil.which("rg"):
        return None

    rg_cmd = ["rg", "--files-with-matches", "--no-messages"]
    if not case_sensitive:
        rg_cmd.append("--ignore-case")
    if file_pattern:
        rg_cmd.extend(["--glob", file_pattern])
    for pat in patterns_to_exclude:
        rg_cmd.extend(["--glob", f"!{pat}"])
    rg_cmd.extend(["--", regex, abs_path])

    try:
        proc = subprocess.run(rg_cmd, capture_output=True, text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None

    if proc.returncode == 2:
        return None

    matching_files = [f.strip() for f in proc.stdout.splitlines() if f.strip()]

    result_entries: list[Any] = []
    match_count = 0
    file_match_count = 0

    for file_path in matching_files:
        rel_file_path = os.path.relpath(file_path, os.getcwd())
        try:
            matches = _get_file_matches(
                file_path,
                pattern,
                context_lines=context_lines,
                preserved_head_lines=preserved_head_lines,
                preserved_tail_lines=preserved_tail_lines,
            )
            if matches:
                file_match_count += 1
                match_count += _count_actual_matches(matches)
                result_entries.append(
                    _build_file_match_entry(rel_file_path, matches, files_only)
                )
        except Exception:
            pass

    return _build_search_output(
        result_entries=result_entries,
        match_count=match_count,
        file_match_count=file_match_count,
        searched_file_count=None,
        regex=regex,
        path=abs_path,
        auto_truncate=auto_truncate,
        preserved_head_lines=preserved_head_lines,
        preserved_tail_lines=preserved_tail_lines,
        files_only=files_only,
    )


def _search_with_os_walk(
    abs_path: str,
    pattern: "re.Pattern",
    file_pattern: str,
    patterns_to_exclude: list[str],
    timeout: float,
    start_time: float,
    context_lines: int,
    files_only: bool,
    auto_truncate: bool,
    preserved_head_lines: int,
    preserved_tail_lines: int,
) -> dict[str, Any]:
    """Fallback search via os.walk (used when ripgrep is unavailable)."""
    result_entries: list[Any] = []
    match_count = 0
    searched_file_count = 0
    file_match_count = 0
    warning: str | None = None

    for root, dirs, files in os.walk(abs_path):
        if time.time() - start_time > timeout:
            warning = f"Search timed out after {timeout} seconds."
            break
        dirs[:] = [
            d
            for d in dirs
            if not d.startswith(".") and not is_path_excluded(d, patterns_to_exclude)
        ]
        for filename in files:
            if time.time() - start_time > timeout:
                warning = f"Search timed out after {timeout} seconds."
                break
            if filename.startswith("."):
                continue
            if is_path_excluded(filename, patterns_to_exclude):
                continue
            if file_pattern and not fnmatch.fnmatch(filename, file_pattern):
                continue

            file_path = os.path.join(root, filename)
            rel_file_path = os.path.relpath(file_path, os.getcwd())
            if is_path_excluded(rel_file_path, patterns_to_exclude):
                continue
            searched_file_count += 1

            try:
                matches = _get_file_matches(
                    file_path,
                    pattern,
                    context_lines=context_lines,
                    preserved_head_lines=preserved_head_lines,
                    preserved_tail_lines=preserved_tail_lines,
                )
                if matches:
                    file_match_count += 1
                    match_count += _count_actual_matches(matches)
                    result_entries.append(
                        _build_file_match_entry(rel_file_path, matches, files_only)
                    )
            except Exception:
                pass

    return _build_search_output(
        result_entries=result_entries,
        match_count=match_count,
        file_match_count=file_match_count,
        searched_file_count=searched_file_count,
        regex=pattern.pattern,
        path=abs_path,
        auto_truncate=auto_truncate,
        preserved_head_lines=preserved_head_lines,
        preserved_tail_lines=preserved_tail_lines,
        files_only=files_only,
        warning=warning,
    )


def _get_file_matches(
    file_path: str,
    pattern: re.Pattern,
    context_lines: int = 2,
    preserved_head_lines: int | None = None,
    preserved_tail_lines: int | None = None,
    max_line_length: int = 1000,
) -> list[dict[str, Any]]:
    """Search for regex matches in a file with context."""
    if preserved_head_lines is None:
        preserved_head_lines = CFG.LLM_FILE_READ_LINES // 4
    if preserved_tail_lines is None:
        preserved_tail_lines = CFG.LLM_FILE_READ_LINES // 4

    def _truncate(s: str) -> str:
        # Use truncate_output directly for consistent truncation
        # For a single line, we use head_lines=1, tail_lines=0
        # and max_chars=max_line_length to ensure it's truncated properly
        truncated_str, _ = truncate_output(
            s.rstrip(),
            head_lines=1,
            tail_lines=0,
            max_line_length=max_line_length,
            max_chars=max_line_length,
        )
        return truncated_str

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    matches = []
    for line_idx, line in enumerate(lines):
        if pattern.search(line):
            line_num = line_idx + 1
            context_start = max(0, line_idx - context_lines)
            context_end = min(len(lines), line_idx + context_lines + 1)

            match_data = {
                "line_number": line_num,
                "line_content": _truncate(line),
                "context_before": [
                    _truncate(lines[j]) for j in range(context_start, line_idx)
                ],
                "context_after": [
                    _truncate(lines[j]) for j in range(line_idx + 1, context_end)
                ],
            }
            matches.append(match_data)

    # Apply truncation to matches within a file if there are too many
    if len(matches) > preserved_head_lines + preserved_tail_lines:
        truncated_matches = (
            matches[:preserved_head_lines] + matches[-preserved_tail_lines:]
        )
        omitted = len(matches) - preserved_head_lines - preserved_tail_lines
        # Add a truncation notice as a special match entry
        truncation_notice = {
            "line_number": 0,
            "line_content": f"[TRUNCATED {omitted} matches in this file. Showing first {preserved_head_lines} and last {preserved_tail_lines} matches.]",
            "context_before": [],
            "context_after": [],
        }
        truncated_matches.append(truncation_notice)
        return truncated_matches

    return matches
