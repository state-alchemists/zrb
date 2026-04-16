import fnmatch
import glob
import os
import re
import time
from typing import Any

from zrb.config.config import CFG
from zrb.util.file import is_path_excluded
from zrb.util.truncate import truncate_output

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


def read_file(
    path: str,
    auto_truncate: bool = True,
) -> str:
    """
    Reads a file's full content. Truncates at 1000 head/tail lines or 100k chars.
    """
    abs_path = os.path.abspath(os.path.expanduser(path))

    validation_error = _validate_path_for_reading(abs_path)
    if validation_error:
        return validation_error

    safety_error = _check_file_safety(abs_path)
    if safety_error:
        return safety_error

    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()

        total_lines = content.count("\n") + 1
        max_chars = CFG.LLM_MAX_OUTPUT_CHARS
        preserved_head_lines = CFG.LLM_FILE_READ_LINES
        preserved_tail_lines = CFG.LLM_FILE_READ_LINES

        if auto_truncate:
            content, truncation_info = truncate_output(
                content,
                preserved_head_lines,
                preserved_tail_lines,
                CFG.LLM_FILE_READ_LINES,
                max_chars,
            )
            start_idx = 0
            end_idx = truncation_info["truncated_lines"]
            truncated = truncation_info["truncation_type"] != "none"
        else:
            start_idx = 0
            end_idx = total_lines
            truncated = False

        header = _format_read_header(path, start_idx, end_idx, total_lines, truncated)
        return f"{header}{content}"

    except UnicodeDecodeError:
        return f"Error: File {path} appears to be binary or non-UTF-8."
    except Exception as e:
        return f"Error reading file {path}: {e}"


def _validate_path_for_reading(abs_path: str) -> str | None:
    """Validates if the path exists and is a file."""
    if not os.path.exists(abs_path):
        return f"Error: File not found: {abs_path}"
    if os.path.isdir(abs_path):
        return f"Error: {abs_path} is a directory."
    return None


def _check_file_safety(abs_path: str) -> str | None:
    """Checks if the file is safe to read (size and content type)."""
    file_size = os.path.getsize(abs_path)
    if file_size > 10 * 1024 * 1024:
        return (
            f"Error: File is too large ({file_size} bytes). "
            f"[SYSTEM SUGGESTION]: Use Grep to search for specific content instead."
        )

    try:
        with open(abs_path, "rb") as f:
            chunk = f.read(1024)
            if b"\0" in chunk:
                return (
                    "Error: File appears to be binary. "
                    "Reading binary files is not supported."
                )
    except Exception:
        pass
    return None


def _format_read_header(
    path: str, start_idx: int, end_idx: int, total_lines: int, truncated: bool
) -> str:
    """
    Formats the header information for the read content.

    Uses a clear delimiter so the LLM can unambiguously distinguish
    metadata from file content. The content below ---CONTENT---
    is the actual file content; everything above is NOT part of the file.
    """
    if truncated:
        meta = (
            f"[File: {path} | lines {start_idx + 1}–{end_idx} of {total_lines} shown | "
            f"truncated — use Grep to locate sections, then Read again]"
        )
    else:
        meta = f"[File: {path} | {total_lines} lines]"
    return f"{meta}\n---CONTENT---\n"


def read_files(
    paths: list[str],
    auto_truncate: bool = True,
) -> dict[str, str]:
    """
    Reads multiple files in a single call. Same truncation as `Read`.

    Individual file errors don't stop batch processing.
    """
    results = {}
    for path in paths:
        results[path] = read_file(path, auto_truncate=auto_truncate)
    return results


def write_file(path: str, content: str, mode: str = "w") -> str:
    """
    Writes or appends content to a file. Creates the file and any missing parent directories.

    `mode="w"` (default) overwrites; `mode="a"` appends. For large content, write in chunks:
    first chunk with mode="w", subsequent chunks with mode="a".
    """
    abs_path = os.path.abspath(os.path.expanduser(path))
    try:
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, mode, encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing to file {path}: {e}"


def write_files(files: list[dict[str, str]]) -> dict[str, str]:
    """
    Batch writes multiple files in a single call.

    Each entry must be a dict with `path` (str), `content` (str), and optional `mode` ("w"/"a").
    Creates parent directories automatically. Same chunking guidance as `Write`.
    """
    results = {}
    for file_info in files:
        path = file_info.get("path")
        content = file_info.get("content")
        mode = file_info.get("mode", "w")
        if not path or content is None:
            results[str(path)] = "Error: Missing path or content"
            continue
        results[path] = write_file(path, content, mode)
    return results


def replace_in_file(
    path: str,
    old_text: str,
    new_text: str,
    count: int = -1,
) -> str:
    """
    Replaces exact text sequences within a file.

    `count=-1` (default) replaces all occurrences; `count=1` replaces only the first.
    Returns an error with near-miss suggestions if old_text is not found.
    """
    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        return f"Error: File not found: {path}"

    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return f"Error: Cannot read file {path}: {e}"

    if old_text not in content:
        # Find near misses to give actionable feedback
        lines = content.splitlines()
        old_lines = old_text.splitlines()
        if old_lines:
            first_line = old_lines[0]
            near_matches = [
                (i + 1, line) for i, line in enumerate(lines) if first_line in line
            ]
            if near_matches:
                preview = "\n".join(
                    f"  Line {num}: {line[:120]}" for num, line in near_matches[:3]
                )
                return (
                    f"Error: '{_trunc(old_text, 80)}' not found in {path}.\n"
                    f"Similar lines found:\n{preview}\n"
                    f"[SYSTEM SUGGESTION]: Verify your old_text matches the file exactly — "
                    f"check for hidden characters, trailing spaces, or line ending differences. "
                    f"Use Read to get the exact content."
                )
        return (
            f"Error: '{_trunc(old_text, 80)}' not found in {path}.\n"
            f"[SYSTEM SUGGESTION]: Use Read to get the exact content and copy old_text "
            f"from the content below ---CONTENT---."
        )

    match_count = content.count(old_text)
    new_content = content.replace(old_text, new_text, count)

    if content == new_content:
        return f"No changes made to {path}"

    try:
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(new_content)
    except Exception as e:
        return f"Error: Cannot write file {path}: {e}"

    return f"Successfully updated {path} ({match_count} replacement(s))"


def _trunc(s: str, n: int) -> str:
    return (s[:n] + "...") if len(s) > n else s


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


async def analyze_file(path: str, query: str, auto_truncate: bool = True) -> str:
    """
    Deep semantic analysis of a file via LLM sub-agent. Slow and resource-intensive.
    """
    from zrb.config.config import CFG
    from zrb.llm.agent import create_agent, run_agent
    from zrb.llm.config.config import llm_config
    from zrb.llm.config.limiter import llm_limiter
    from zrb.llm.prompt.prompt import get_file_extractor_system_prompt

    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        return f"Error: File not found: {path}"

    content = read_file(abs_path, auto_truncate=auto_truncate)
    if content.startswith("Error:"):
        return content

    token_threshold = CFG.LLM_FILE_ANALYSIS_TOKEN_THRESHOLD
    char_limit = token_threshold * 4

    clipped_content, _ = truncate_output(
        content,
        head_lines=CFG.LLM_FILE_READ_LINES,
        tail_lines=CFG.LLM_FILE_READ_LINES,
        max_chars=char_limit,
    )

    system_prompt = get_file_extractor_system_prompt()

    agent = create_agent(
        model=llm_config.resolve_model(),
        system_prompt=system_prompt,
        tools=[
            read_file,
            search_files,
        ],
    )

    user_message = f"""
    Instruction: {query}
    File Path: {abs_path}
    File Content:
    ```
    {clipped_content}
    ```
    """

    result, _ = await run_agent(
        agent=agent,
        message=user_message,
        message_history=[],
        limiter=llm_limiter,
    )

    return str(result)


list_files.__name__ = "LS"

glob_files.__name__ = "Glob"

read_file.__name__ = "Read"

read_files.__name__ = "ReadMany"

write_file.__name__ = "Write"

write_files.__name__ = "WriteMany"

replace_in_file.__name__ = "Edit"

search_files.__name__ = "Grep"

analyze_file.__name__ = "AnalyzeFile"
