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
from zrb.util.truncate import truncate_items, truncate_text

# Per-line snippet cap in search output (a single matched/context line).
_MAX_LINE_LENGTH = 1000
# Head-keep cap on the number of matches reported for one file.
_MAX_MATCHES_PER_FILE = 100


def search_files(
    pattern: str,
    path: str = ".",
    file_pattern: str = "",
    exclude_patterns: list[str] | None = None,
    timeout: float = 30.0,
    context_lines: int = 2,
    files_only: bool = False,
    case_sensitive: bool = True,
) -> dict[str, Any]:
    """
    Searches file *contents* for a regular expression. Results include line
    numbers and context.

    `pattern`: a regular expression (e.g. `def \\w+`), NOT a glob — to find
        files by name, use Glob instead.
    `file_pattern`: a glob restricting which files to search (e.g., `*.py`).
    `context_lines` (default 2): surrounding lines shown per match.
    `files_only=True`: returns `{"files": [...], "summary": "..."}` — much smaller output.
    `case_sensitive=False`: case-insensitive search.
    Lines are truncated at 1000 chars in output.
    """
    start_time = time.time()
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        compiled = re.compile(pattern, flags)
    except re.error as e:
        return {"error": f"Invalid regex pattern: {e}"}

    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        return {"error": f"Path not found: {path}"}

    patterns_to_exclude = (
        exclude_patterns if exclude_patterns is not None else DEFAULT_EXCLUDED_PATTERNS
    )

    rg_result = _search_with_ripgrep(
        pattern=compiled,
        regex=pattern,
        abs_path=abs_path,
        file_pattern=file_pattern,
        case_sensitive=case_sensitive,
        context_lines=context_lines,
        files_only=files_only,
        patterns_to_exclude=patterns_to_exclude,
        timeout=timeout,
    )
    if rg_result is not None:
        return rg_result

    return _search_with_os_walk(
        abs_path=abs_path,
        pattern=compiled,
        file_pattern=file_pattern,
        patterns_to_exclude=patterns_to_exclude,
        timeout=timeout,
        start_time=start_time,
        context_lines=context_lines,
        files_only=files_only,
    )


def _build_file_match_entry(
    rel_file_path: str, matches: list[dict[str, Any]], files_only: bool
) -> str | dict[str, Any]:
    """Build a single result entry: file path string or {file, matches} dict."""
    return rel_file_path if files_only else {"file": rel_file_path, "matches": matches}


def _count_actual_matches(matches: list[dict[str, Any]]) -> int:
    """Count matches that have a non-zero line number."""
    return sum(1 for m in matches if m.get("line_number", 0) > 0)


def _truncate_file_results(results: list[Any]) -> tuple[list[Any], str | None]:
    """Keep leading result files within the output char budget (head-keep).

    Returns (truncated_list, truncation_notice).
    """
    kept, omitted = truncate_items(results, CFG.LLM_MAX_OUTPUT_CHARS)
    if omitted == 0:
        return results, None
    notice = (
        f"[TRUNCATED {omitted} result files. Showing first {len(kept)} "
        f"of {len(results)} files with matches.]"
    )
    return kept, notice


def _build_search_output(
    result_entries: list[Any],
    match_count: int,
    file_match_count: int,
    searched_file_count: int | None,
    regex: str,
    path: str,
    files_only: bool,
    warning: str | None = None,
) -> dict[str, Any]:
    """Build the final search result dict from accumulated match data.

    Shared by both the ripgrep and the fallback os.walk code paths.
    """
    results, truncation_notice = _truncate_file_results(result_entries)

    if match_count == 0:
        searched = (
            f" (searched {searched_file_count} files)" if searched_file_count else ""
        )
        summary = (
            f"No matches found for regex '{regex}' in path '{path}'{searched}. "
            f"[SYSTEM SUGGESTION]: Try broadening your regex, removing the "
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


def _merge_skipped_warning(warning: str | None, skipped_count: int) -> str | None:
    """Fold a 'files skipped' notice into the existing warning, if any.

    Surfaces silently-unreadable files so partial results are never presented
    as complete.
    """
    if skipped_count <= 0:
        return warning
    notice = (
        f"{skipped_count} file(s) were skipped because they could not be read "
        f"(permission denied, encoding error, or removed mid-scan); "
        f"results may be incomplete."
    )
    return f"{warning} {notice}" if warning else notice


def _search_with_ripgrep(
    pattern: "re.Pattern",
    regex: str,
    abs_path: str,
    file_pattern: str,
    case_sensitive: bool,
    context_lines: int,
    files_only: bool,
    patterns_to_exclude: list[str],
    timeout: float,
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
    skipped_count = 0

    for file_path in matching_files:
        rel_file_path = os.path.relpath(file_path, os.getcwd())
        try:
            matches = _get_file_matches(
                file_path,
                pattern,
                context_lines=context_lines,
            )
            if matches:
                file_match_count += 1
                match_count += _count_actual_matches(matches)
                result_entries.append(
                    _build_file_match_entry(rel_file_path, matches, files_only)
                )
        except Exception as e:
            skipped_count += 1
            CFG.LOGGER.debug(f"file_search: skipped unreadable file {file_path}: {e}")

    return _build_search_output(
        result_entries=result_entries,
        match_count=match_count,
        file_match_count=file_match_count,
        searched_file_count=None,
        regex=regex,
        path=abs_path,
        warning=_merge_skipped_warning(None, skipped_count),
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
) -> dict[str, Any]:
    """Fallback search via os.walk (used when ripgrep is unavailable)."""
    result_entries: list[Any] = []
    match_count = 0
    searched_file_count = 0
    file_match_count = 0
    skipped_count = 0
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
                )
                if matches:
                    file_match_count += 1
                    match_count += _count_actual_matches(matches)
                    result_entries.append(
                        _build_file_match_entry(rel_file_path, matches, files_only)
                    )
            except Exception as e:
                skipped_count += 1
                CFG.LOGGER.debug(
                    f"file_search: skipped unreadable file {file_path}: {e}"
                )

    return _build_search_output(
        result_entries=result_entries,
        match_count=match_count,
        file_match_count=file_match_count,
        searched_file_count=searched_file_count,
        regex=pattern.pattern,
        path=abs_path,
        files_only=files_only,
        warning=_merge_skipped_warning(warning, skipped_count),
    )


def _get_file_matches(
    file_path: str,
    pattern: re.Pattern,
    context_lines: int = 2,
) -> list[dict[str, Any]]:
    """Search for regex matches in a file with context."""

    def _truncate(s: str) -> str:
        out, _ = truncate_text(s.rstrip(), _MAX_LINE_LENGTH, keep="head")
        return out

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

    # Cap matches per file (head-keep) so one busy file can't dominate output.
    if len(matches) > _MAX_MATCHES_PER_FILE:
        omitted = len(matches) - _MAX_MATCHES_PER_FILE
        kept = matches[:_MAX_MATCHES_PER_FILE]
        kept.append(
            {
                "line_number": 0,
                "line_content": (
                    f"[TRUNCATED {omitted} matches in this file. Showing first "
                    f"{_MAX_MATCHES_PER_FILE}.]"
                ),
                "context_before": [],
                "context_after": [],
            }
        )
        return kept

    return matches
