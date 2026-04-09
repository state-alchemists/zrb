import fnmatch
import glob
import os
import re
import time
from typing import Any

from zrb.util.file import is_path_excluded
from zrb.util.file import read_file as util_read_file
from zrb.util.file import write_file as util_write_file
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


def list_files(
    path: str = ".",
    auto_truncate: bool = True,
    exclude_patterns: list[str] | None = None,
) -> dict[str, list[str]]:
    """
    Recursively lists files up to 3 levels deep.

    Auto-excludes `.git`, `node_modules`, `__pycache__`, etc. Sorted alphabetically.

    MANDATES:
    - For targeted file discovery by pattern, use `Glob` instead.
    - Use `exclude_patterns=[]` to include all files.
    """
    all_files: list[str] = []
    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Path does not exist: {path}")

    depth = 3
    patterns_to_exclude = (
        exclude_patterns if exclude_patterns is not None else DEFAULT_EXCLUDED_PATTERNS
    )
    preserved_head_lines = 500
    preserved_tail_lines = 500

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

    if (
        auto_truncate
        and len(sorted_files) > preserved_head_lines + preserved_tail_lines
    ):
        truncated_files = (
            sorted_files[:preserved_head_lines] + sorted_files[-preserved_tail_lines:]
        )
        omitted = len(sorted_files) - preserved_head_lines - preserved_tail_lines
        return {
            "files": truncated_files,
            "truncation_notice": f"[TRUNCATED {omitted} files. Showing first {preserved_head_lines} and last {preserved_tail_lines} files.]",
        }

    return {"files": sorted_files}


def glob_files(
    pattern: str,
    path: str = ".",
    auto_truncate: bool = True,
    exclude_patterns: list[str] | None = None,
) -> list[str]:
    """
    Finds files matching glob patterns (e.g., `**/*.py`). Supports `**` for recursive search.

    Auto-excludes `.git`, `node_modules`, `__pycache__`, etc. Sorted alphabetically.

    MANDATES:
    - For general directory listing without a pattern, use `LS` instead.
    - Use `exclude_patterns=[]` to include all files.
    """
    found_files = []
    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        return f"Error: Path does not exist: {path}"

    patterns_to_exclude = (
        exclude_patterns if exclude_patterns is not None else DEFAULT_EXCLUDED_PATTERNS
    )
    preserved_head_lines = 500
    preserved_tail_lines = 500

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

    if (
        auto_truncate
        and len(sorted_files) > preserved_head_lines + preserved_tail_lines
    ):
        truncated_files = (
            sorted_files[:preserved_head_lines] + sorted_files[-preserved_tail_lines:]
        )
        omitted = len(sorted_files) - preserved_head_lines - preserved_tail_lines
        truncated_files.append(
            f"[TRUNCATED {omitted} files. Showing first {preserved_head_lines} and last {preserved_tail_lines} files.]"
        )
        return truncated_files

    return sorted_files


def read_file(
    path: str,
    auto_truncate: bool = True,
) -> str:
    """
    Reads a file's full content. Truncates at 1000 head/tail lines or 100k chars.

    MANDATES:
    - Use `Grep` first to locate the relevant section before reading.
    - For multiple related files, use `ReadMany` instead.
    - Always read a file before editing it.
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
        max_chars = 100000
        preserved_head_lines = 1000
        preserved_tail_lines = 1000

        if auto_truncate:
            content, truncation_info = truncate_output(
                content,
                preserved_head_lines,
                preserved_tail_lines,
                1000,
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
    """Formats the header information for the read content."""
    if truncated:
        return (
            f"IMPORTANT: The file content has been truncated.\n"
            f"Status: Showing lines {start_idx + 1}-{end_idx} of {total_lines} total lines.\n"
            f"[SYSTEM SUGGESTION]: Use 'Grep' to find specific function definitions or patterns before reading.\n\n"
        )
    return ""


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

    MANDATES:
    - For modifying existing files, use `Edit` (surgical replacement) instead.
    - For large content, write in chunks: mode="w" for first chunk, mode="a" for each subsequent.
    - For multiple files at once, use `WriteMany`.
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


def replace_in_file(path: str, old_text: str, new_text: str, count: int = -1) -> str:
    """
    Replaces exact text sequences within a file.

    MANDATES:
    - Always `Read` the file first to copy exact text byte-for-byte—Grep output may truncate long lines.
    - Include 2-3 surrounding lines in `old_text` to ensure a unique match.
    - If `old_text` matches multiple locations, expand context or use `count=1` for first occurrence only.
    - For new files, use `Write` instead.
    """
    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        return f"Error: File not found: {path}"

    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()

        if old_text not in content:
            return f"Error: '{old_text}' not found in {path}"

        new_content = content.replace(old_text, new_text, count)

        if content == new_content:
            return f"No changes made to {path}"

        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return f"Successfully updated {path}"
    except Exception as e:
        return f"Error replacing text in {path}: {e}"


def search_files(
    regex: str,
    path: str = ".",
    file_pattern: str = "",
    auto_truncate: bool = True,
    exclude_patterns: list[str] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """
    Searches for a regex pattern across files. Results include line numbers and context.

    MANDATES:
    - Use `file_pattern` to restrict to specific file types (e.g., `*.py`).
    - For file listing without content search, use `Glob` or `LS` instead.
    - Use `exclude_patterns=[]` to search all files including normally excluded ones.
    - Lines are truncated at 1000 chars—never copy Grep output directly into `Edit`'s `old_text`; always `Read` the file first.
    """
    start_time = time.time()
    try:
        pattern = re.compile(regex)
    except re.error as e:
        return {"error": f"Invalid regex pattern: {e}"}

    search_results = {"summary": "", "results": []}
    match_count = 0
    searched_file_count = 0
    file_match_count = 0

    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        return {"error": f"Path not found: {path}"}

    preserved_head_lines = 250
    preserved_tail_lines = 250

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
                        preserved_head_lines=preserved_head_lines,
                        preserved_tail_lines=preserved_tail_lines,
                    )
                    if matches:
                        file_match_count += 1
                        actual_matches = [
                            m for m in matches if m.get("line_number", 0) > 0
                        ]
                        match_count += len(actual_matches)
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
        return search_results

    except Exception as e:
        return {"error": f"Error searching files: {e}"}


def _get_file_matches(
    file_path: str,
    pattern: re.Pattern,
    context_lines: int = 2,
    preserved_head_lines: int = 250,
    preserved_tail_lines: int = 250,
    max_line_length: int = 1000,
) -> list[dict[str, Any]]:
    """Search for regex matches in a file with context."""
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

    MANDATES:
    - For simple file reading, use `Read` instead.
    - For directory-level analysis, use `AnalyzeCode`.
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
        content, head_lines=1000, tail_lines=1000, max_chars=char_limit
    )

    system_prompt = get_file_extractor_system_prompt()

    agent = create_agent(
        model=llm_config.model,
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
