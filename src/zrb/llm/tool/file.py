import fnmatch
import glob
import os
import re
from typing import Any

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
    include_hidden: bool = False,
    depth: int = 3,
    excluded_patterns: list[str] | None = None,
) -> dict[str, list[str]]:
    """
    Recursively explores and lists files within a directory tree up to a defined depth.

    **WHEN TO USE:**
    - To discover the project structure or find specific files when the path is unknown.
    - To verify the existence of files in a directory.

    **EFFICIENCY TIP:**
    - Do NOT use this tool if you already know the file path. Use `read_file` directly.
    - Keep `depth` low (default 3) to avoid overwhelming output.

    **ARGS:**
    - `path`: The root directory to start the search from.
    - `include_hidden`: If True, includes hidden files and directories (starting with `.`).
    - `depth`: Maximum levels of directories to descend.
    - `excluded_patterns`: List of glob patterns to ignore.
    """
    all_files: list[str] = []
    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Path does not exist: {path}")

    patterns_to_exclude = (
        excluded_patterns
        if excluded_patterns is not None
        else DEFAULT_EXCLUDED_PATTERNS
    )
    if depth <= 0:
        depth = 1

    initial_depth = abs_path.rstrip(os.sep).count(os.sep)
    for root, dirs, files in os.walk(abs_path, topdown=True):
        current_depth = root.rstrip(os.sep).count(os.sep) - initial_depth
        if current_depth >= depth - 1:
            del dirs[:]

        dirs[:] = [
            d
            for d in dirs
            if (include_hidden or not d.startswith("."))
            and not _is_excluded(d, patterns_to_exclude)
        ]

        for filename in files:
            if (include_hidden or not filename.startswith(".")) and not _is_excluded(
                filename, patterns_to_exclude
            ):
                full_path = os.path.join(root, filename)
                rel_full_path = os.path.relpath(full_path, abs_path)
                if not _is_excluded(rel_full_path, patterns_to_exclude):
                    all_files.append(rel_full_path)
    return {"files": sorted(all_files)}


def glob_files(
    pattern: str,
    path: str = ".",
    include_hidden: bool = False,
    excluded_patterns: list[str] | None = None,
) -> list[str]:
    """
    Finds files matching specific glob patterns.

    **WHEN TO USE:**
    - To find files by name or extension (e.g., `**/*.py`, `src/**/*.ts`).
    - Faster and more targeted than `list_files` when looking for specific file types.

    **ARGS:**
    - `pattern`: The glob pattern to match (e.g., `**/*.md`).
    - `path`: The root directory to start the search from.
    - `include_hidden`: Whether to include hidden files/dirs.
    - `excluded_patterns`: List of glob patterns to ignore.
    """
    found_files = []
    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        return [f"Error: Path does not exist: {path}"]

    patterns_to_exclude = (
        excluded_patterns
        if excluded_patterns is not None
        else DEFAULT_EXCLUDED_PATTERNS
    )

    search_pattern = os.path.join(abs_path, pattern)
    # This might find files in excluded directories
    candidates = glob.glob(search_pattern, recursive=True)

    for candidate in candidates:
        if os.path.isdir(candidate):
            continue

        rel_path = os.path.relpath(candidate, abs_path)

        # Filter hidden
        if not include_hidden:
            if any(part.startswith(".") for part in rel_path.split(os.sep)):
                continue

        # Filter excluded
        if _is_excluded(rel_path, patterns_to_exclude):
            continue

        found_files.append(rel_path)

    return sorted(found_files)


def read_file(
    path: str,
    start_line: int | None = None,
    end_line: int | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> str:
    """
    Reads content from a file, optionally specifying a line range.

    **EFFICIENCY TIP:**
    - Prefer reading the **entire file** at once for full context (imports, class definitions).
    - Only use `start_line`/`end_line` or `offset`/`limit` for extremely large files (e.g., logs).
    - If the file is too large (default limit ~2000 lines), it will be truncated.

    **ARGS:**
    - `path`: Path to the file to read.
    - `start_line`: The 1-based line number to start reading from.
    - `end_line`: The 1-based line number to stop reading at (inclusive).
    - `limit`: Max lines to read (alias/alternative to end_line calculation).
    - `offset`: 0-based line index to start reading from (alternative to start_line).
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
            lines = f.readlines()

        total_lines = len(lines)
        start_idx, end_idx, truncated = _calculate_read_bounds(
            total_lines, start_line, end_line, limit, offset
        )

        selected_lines = lines[start_idx:end_idx]
        content_result = "".join(selected_lines)

        header = _format_read_header(path, start_idx, end_idx, total_lines, truncated)
        return f"{header}{content_result}"

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
    # Check size
    file_size = os.path.getsize(abs_path)
    if file_size > 10 * 1024 * 1024:  # 10MB limit
        return (
            f"Error: File is too large ({file_size} bytes). "
            f"Please use `offset` and `limit` to read chunks."
        )

    # Check binary
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


def _calculate_read_bounds(
    total_lines: int,
    start_line: int | None,
    end_line: int | None,
    limit: int | None,
    offset: int | None,
) -> tuple[int, int, bool]:
    """Calculates the start and end indices for reading lines."""
    DEFAULT_LIMIT = 2000
    truncated = False

    final_start_idx = 0
    final_end_idx = total_lines

    if offset is not None:
        final_start_idx = offset
    elif start_line is not None:
        final_start_idx = start_line - 1

    if limit is not None:
        final_end_idx = final_start_idx + limit
    elif end_line is not None:
        final_end_idx = end_line

    if start_line is None and end_line is None and limit is None and offset is None:
        if total_lines > DEFAULT_LIMIT:
            final_end_idx = DEFAULT_LIMIT
            truncated = True

    # Bounds checking
    if final_start_idx < 0:
        final_start_idx = 0
    if final_end_idx > total_lines:
        final_end_idx = total_lines
    if final_start_idx > final_end_idx:
        final_start_idx = final_end_idx

    return final_start_idx, final_end_idx, truncated


def _format_read_header(
    path: str, start_idx: int, end_idx: int, total_lines: int, truncated: bool
) -> str:
    """Formats the header information for the read content."""
    if truncated:
        next_offset = end_idx
        return (
            f"IMPORTANT: The file content has been truncated.\n"
            f"Status: Showing lines {start_idx + 1}-{end_idx} of {total_lines} total lines.\n"
            f"Action: To read more of the file, you can use the 'offset' and 'limit' parameters in a subsequent 'read_file' call. "
            f"For example, to read the next section, use offset={next_offset}, limit=2000.\n\n"
        )
    elif start_idx > 0 or end_idx < total_lines:
        return f"File: {path} (Lines {start_idx + 1}-{end_idx} of {total_lines})\n"
    return ""


def read_files(paths: list[str]) -> dict[str, str]:
    """
    Reads content from multiple files simultaneously.

    **USAGE:**
    - Use this when you need context from several related files (e.g., a class definition and its tests).

    **ARGS:**
    - `paths`: List of file paths to read.
    """
    results = {}
    for path in paths:
        results[path] = read_file(path)
    return results


def write_file(path: str, content: str, mode: str = "w") -> str:
    """
    Writes or appends content to a file.

    **CRITICAL - PREVENT ERRORS:**
    1. **ESCAPING:** Do NOT double-escape quotes in your JSON tool call.
    2. **SIZE LIMIT:** DO NOT write more than 4000 characters in a single call.
    3. **CHUNKING:** For large files, use `mode="w"` for the first chunk and `mode="a"` for the rest.

    **ARGS:**
    - `path`: Target file path.
    - `content`: Text content to write.
    - `mode`: File opening mode ("w" to overwrite, "a" to append).
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
    Performs batch write operations to multiple files.

    **ARGS:**
    - `files`: A list of dictionaries, each containing:
        - `path` (str): Target file path.
        - `content` (str): Text to write.
        - `mode` (str, optional): "w" (overwrite, default) or "a" (append).
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

    **CRITICAL INSTRUCTIONS:**
    1. **PRECISION:** `old_text` must match the file content EXACTLY.
    2. **READ FIRST:** Always `read_file` before replacing.
    3. **MINIMAL CONTEXT:** Include 2-3 lines of context in `old_text` to ensure uniqueness.

    **ARGS:**
    - `path`: Path to the file to modify.
    - `old_text`: The exact literal text to be replaced.
    - `new_text`: The replacement text.
    - `count`: Number of occurrences to replace (default -1 for all).
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
    path: str,
    regex: str,
    file_pattern: str | None = None,
    include_hidden: bool = True,
) -> dict[str, Any]:
    """
    Searches for a regular expression pattern within files.

    **WHEN TO USE:**
    - To find usages of a function, variable, or string across the project.

    **ARGS:**
    - `path`: Root directory to search.
    - `regex`: A standard Python regular expression.
    - `file_pattern`: Optional glob (e.g., "*.py") to restrict the search.
    - `include_hidden`: Whether to search in hidden files/dirs.
    """
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

    try:
        for root, dirs, files in os.walk(abs_path):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if include_hidden or not d.startswith(".")]
            for filename in files:
                # Skip hidden files
                if not include_hidden and filename.startswith("."):
                    continue
                # Apply file pattern filter if provided
                if file_pattern and not fnmatch.fnmatch(filename, file_pattern):
                    continue

                file_path = os.path.join(root, filename)
                rel_file_path = os.path.relpath(file_path, os.getcwd())
                searched_file_count += 1

                try:
                    matches = _get_file_matches(file_path, pattern)
                    if matches:
                        file_match_count += 1
                        match_count += len(matches)
                        search_results["results"].append(
                            {"file": rel_file_path, "matches": matches}
                        )
                except Exception:
                    # Ignore read errors for binary files etc
                    pass

        if match_count == 0:
            search_results["summary"] = (
                f"No matches found for pattern '{regex}' in path '{path}' "
                f"(searched {searched_file_count} files)."
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
) -> list[dict[str, any]]:
    """Search for regex matches in a file with context."""
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
                "line_content": line.rstrip(),
                "context_before": [
                    lines[j].rstrip() for j in range(context_start, line_idx)
                ],
                "context_after": [
                    lines[j].rstrip() for j in range(line_idx + 1, context_end)
                ],
            }
            matches.append(match_data)
    return matches


def _is_excluded(name: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if fnmatch.fnmatch(name, pattern):
            return True
        parts = name.split(os.path.sep)
        for part in parts:
            if fnmatch.fnmatch(part, pattern):
                return True
    return False


async def analyze_file(path: str, query: str) -> str:
    """
    Delegates deep analysis of a specific file to a specialized sub-agent.

    **WHEN TO USE:**
    - For complex questions about a file's logic, structure, or potential bugs.
    - When you need a summary or specific details that require "understanding" the code.

    **NOTE:** For simple data retrieval, use `read_file`.

    **ARGS:**
    - `path`: Path to the file to analyze.
    - `query`: The specific analytical question or instruction.
    """
    # Lazy imports to avoid circular dependencies
    from zrb.config.config import CFG
    from zrb.llm.agent import create_agent, run_agent
    from zrb.llm.config.config import llm_config
    from zrb.llm.config.limiter import llm_limiter
    from zrb.llm.prompt.prompt import get_file_extractor_system_prompt

    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        return f"Error: File not found: {path}"

    # Read content
    content = read_file(abs_path)
    if content.startswith("Error:"):
        return content

    # Check token limit and truncate if necessary
    token_threshold = CFG.LLM_FILE_ANALYSIS_TOKEN_THRESHOLD
    # Simple character-based approximation (1 token ~ 4 chars)
    char_limit = token_threshold * 4

    clipped_content = content
    if len(content) > char_limit:
        clipped_content = content[:char_limit] + "\n...[TRUNCATED]..."

    system_prompt = get_file_extractor_system_prompt()

    # Create the sub-agent
    agent = create_agent(
        model=llm_config.model,
        system_prompt=system_prompt,
        tools=[
            read_file,
            search_files,
        ],
    )

    # Construct the user message
    user_message = f"""
    Instruction: {query}
    File Path: {abs_path}
    File Content:
    ```
    {clipped_content}
    ```
    """

    # Run the agent
    # We pass empty history as this is a fresh sub-task
    # We use print as the print_fn (which streams to stdout)
    result, _ = await run_agent(
        agent=agent,
        message=user_message,
        message_history=[],
        limiter=llm_limiter,
    )

    return str(result)
