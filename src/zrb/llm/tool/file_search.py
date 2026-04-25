import fnmatch
import os
import re
import shutil
import subprocess
import time
from typing import Any

from zrb.config.config import CFG
from zrb.util.file import is_path_excluded
from zrb.util.truncate import truncate_output

from zrb.llm.tool.file_list import DEFAULT_EXCLUDED_PATTERNS


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

    search_results: dict[str, Any] = {"summary": "", "results": []}
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
                actual_matches = [m for m in matches if m.get("line_number", 0) > 0]
                match_count += len(actual_matches)
                if files_only:
                    search_results["results"].append(rel_file_path)
                else:
                    search_results["results"].append(
                        {"file": rel_file_path, "matches": matches}
                    )
        except Exception:
            pass

    if auto_truncate:
        results = search_results["results"]
        if len(results) > preserved_head_lines + preserved_tail_lines:
            truncated = results[:preserved_head_lines] + results[-preserved_tail_lines:]
            omitted = len(results) - preserved_head_lines - preserved_tail_lines
            search_results["results"] = truncated
            search_results["truncation_notice"] = (
                f"[TRUNCATED {omitted} result files. Showing first {preserved_head_lines} and last {preserved_tail_lines} files with matches.]"
            )

    if match_count == 0:
        search_results["summary"] = (
            f"No matches found for pattern '{regex}' in path '{abs_path}' "
            f"[SYSTEM SUGGESTION]: Try broadening your regex pattern, removing the file_pattern filter, "
            f"or checking if you're searching in the correct directory."
        )
    else:
        search_results["summary"] = (
            f"Found {match_count} matches in {file_match_count} files."
        )

    if files_only:
        result: dict[str, Any] = {
            "files": search_results["results"],
            "summary": search_results["summary"],
        }
        if "truncation_notice" in search_results:
            result["truncation_notice"] = search_results["truncation_notice"]
        return result

    return search_results


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
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    matches = []
    for line_idx, line in enumerate(lines):
        if pattern.search(line):
            line_num = line_idx + 1
            context_start = max(0, line_idx - context_lines)
            context_end = min(len(lines), line_idx + context_lines + 1)

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

    search_results = {"summary": "", "results": []}
    match_count = 0
    searched_file_count = 0
    file_match_count = 0

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

    try:
        for root, dirs, files in os.walk(abs_path):
            if time.time() - start_time > timeout:
                search_results["warning"] = f"Search timed out after {timeout} seconds."
                break
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".")
                and not is_path_excluded(d, patterns_to_exclude)
            ]
            for filename in files:
                if time.time() - start_time > timeout:
                    search_results["warning"] = (
                        f"Search timed out after {timeout} seconds."
                    )
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
                        actual_matches = [
                            m for m in matches if m.get("line_number", 0) > 0
                        ]
                        match_count += len(actual_matches)
                        if files_only:
                            search_results["results"].append(rel_file_path)
                        else:
                            search_results["results"].append(
                                {"file": rel_file_path, "matches": matches}
                            )
                except Exception:
                    pass

        if auto_truncate:
            results = search_results["results"]
            if len(results) > preserved_head_lines + preserved_tail_lines:
                truncated_results = (
                    results[:preserved_head_lines] + results[-preserved_tail_lines:]
                )
                omitted = len(results) - preserved_head_lines - preserved_tail_lines
                search_results["results"] = truncated_results
                search_results["truncation_notice"] = (
                    f"[TRUNCATED {omitted} result files. Showing first {preserved_head_lines} and last {preserved_tail_lines} files with matches.]"
                )

        if match_count == 0:
            search_results["summary"] = (
                f"No matches found for pattern '{regex}' in path '{path}' "
                f"(searched {searched_file_count} files). "
                f"[SYSTEM SUGGESTION]: Try broadening your regex pattern, removing the file_pattern filter, or checking if you're searching in the correct directory."
            )
        else:
            search_results["summary"] = (
                f"Found {match_count} matches in {file_match_count} files "
                f"(searched {searched_file_count} files)."
            )

        if files_only:
            result: dict[str, Any] = {
                "files": search_results["results"],
                "summary": search_results["summary"],
            }
            if "truncation_notice" in search_results:
                result["truncation_notice"] = search_results["truncation_notice"]
            if "warning" in search_results:
                result["warning"] = search_results["warning"]
            return result

        return search_results

    except Exception as e:
        return {"error": f"Error searching files: {e}"}
