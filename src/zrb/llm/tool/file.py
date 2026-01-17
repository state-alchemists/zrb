import fnmatch
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
]


def list_files(
    path: str = ".",
    include_hidden: bool = False,
    depth: int = 3,
    excluded_patterns: list[str] | None = None,
) -> dict[str, list[str]]:
    """
    Lists files recursively up to a specified depth.
    Use this to explore directory structure.
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


def read_file(
    path: str, start_line: int | None = None, end_line: int | None = None
) -> str:
    """
    Reads content from a file, optionally specifying line ranges.
    """
    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        return f"Error: File not found: {path}"

    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        total_lines = len(lines)
        start_idx = (start_line - 1) if start_line is not None else 0
        end_idx = end_line if end_line is not None else total_lines

        if start_idx < 0:
            start_idx = 0
        if end_idx > total_lines:
            end_idx = total_lines
        if start_idx > end_idx:
            start_idx = end_idx

        selected_lines = lines[start_idx:end_idx]
        content_result = "".join(selected_lines)

        if start_line is not None or end_line is not None:
            return f"File: {path} (Lines {start_idx + 1}-{end_idx} of {total_lines})\n{content_result}"
        return content_result

    except Exception as e:
        return f"Error reading file {path}: {e}"


def read_files(paths: list[str]) -> dict[str, str]:
    """
    Reads content from multiple files.
    Returns a dictionary mapping file paths to their content or error messages.
    """
    results = {}
    for path in paths:
        results[path] = read_file(path)
    return results


def write_file(path: str, content: str, mode: str = "w") -> str:
    """
    Writes content to a file. Mode 'w' for overwrite, 'a' for append.
    WARNING: Content MUST NOT exceed 4000 characters.
    """
    if len(content) > 4000:
        return (
            "Error: Content exceeds 4000 characters. Please split your write operation."
        )

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
    Writes content to multiple files.
    Args:
        files: List of dicts, each containing 'path', 'content', and optional 'mode'.
               Example: [{"path": "file1.txt", "content": "hello"}, {"path": "file2.txt", "content": "world", "mode": "a"}]
    Returns:
        Dictionary mapping file paths to success/error messages.
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
    Replaces exact text in a file.
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
    Searches for a regex pattern in files within a directory.
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
                except Exception as e:
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
    Analyzes a file using a sub-agent.
    Use this for complex questions about code structure, logic, or content
    that requires "thinking" rather than just reading.
    """
    # Lazy imports to avoid circular dependencies
    from zrb.config.config import CFG
    from zrb.llm.agent.agent import create_agent, run_agent
    from zrb.llm.config.limiter import llm_limiter
    from zrb.llm.tool.tool import Tool

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

    system_prompt = CFG.LLM_FILE_EXTRACTOR_SYSTEM_PROMPT

    # Create the sub-agent
    agent = create_agent(
        model=CFG.LLM_MODEL,
        system_prompt=system_prompt,
        tools=[
            Tool(read_file, name="read_file", description="Read file content"),
            Tool(search_files, name="search_files", description="Search in files"),
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
