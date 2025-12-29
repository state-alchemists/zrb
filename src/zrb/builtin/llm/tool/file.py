import fnmatch
import json
import os
import re
from typing import Any, Optional

from zrb.builtin.llm.tool.sub_agent import create_sub_agent_tool
from zrb.config.config import CFG
from zrb.config.llm_rate_limitter import llm_rate_limitter
from zrb.context.any_context import AnyContext
from zrb.task.llm.file_tool_model import FileReplacement, FileToRead, FileToWrite
from zrb.util.file import read_file, read_file_with_line_numbers, write_file

DEFAULT_EXCLUDED_PATTERNS = [
    # Common Python artifacts
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".Python",
    "build",
    "develop-eggs",
    "dist",
    "downloads",
    "eggs",
    ".eggs",
    "lib",
    "lib64",
    "parts",
    "sdist",
    "var",
    "wheels",
    "share/python-wheels",
    "*.egg-info",
    ".installed.cfg",
    "*.egg",
    "MANIFEST",
    # Virtual environments
    ".env",
    ".venv",
    "env",
    "venv",
    "ENV",
    "VENV",
    # Editor/IDE specific
    ".idea",
    ".vscode",
    "*.swp",
    "*.swo",
    "*.swn",
    # OS specific
    ".DS_Store",
    "Thumbs.db",
    # Version control
    ".git",
    ".hg",
    ".svn",
    # Node.js
    "node_modules",
    "npm-debug.log*",
    "yarn-debug.log*",
    "yarn-error.log*",
    # Test/Coverage artifacts
    ".history",
    ".tox",
    ".nox",
    ".coverage",
    ".coverage.*",
    ".cache",
    ".pytest_cache",
    ".hypothesis",
    "htmlcov",
    # Compiled files
    "*.so",
    "*.dylib",
    "*.dll",
    # Minified files
    "*.min.css",
    "*.min.js",
]


def list_files(
    path: str = ".",
    include_hidden: bool = False,
    depth: int = 3,
    excluded_patterns: Optional[list[str]] = None,
) -> dict[str, list[str]]:
    """
    Lists files recursively up to a specified depth.

    **EFFICIENCY TIP:**
    Do NOT use this tool if you already know the file path (e.g., from the user's prompt).
    Use `read_from_file` directly in that case. Only use this to explore directory structures.

    Example:
    list_files(path='src', include_hidden=False, depth=2)

    Args:
        path (str): Directory path. Defaults to current directory.
        include_hidden (bool): Include hidden files. Defaults to False.
        depth (int): Maximum depth to traverse. Defaults to 3.
            Minimum depth is 1 (current directory only).
        excluded_patterns (list[str]): Glob patterns to exclude.

    Returns:
        dict: {'files': [relative_paths]}
    """
    all_files: list[str] = []
    abs_path = os.path.abspath(os.path.expanduser(path))
    # Explicitly check if path exists before proceeding
    if not os.path.exists(abs_path):
        # Raise FileNotFoundError, which is a subclass of OSError
        raise FileNotFoundError(f"Path does not exist: {path}")
    # Determine effective exclusion patterns
    patterns_to_exclude = (
        excluded_patterns
        if excluded_patterns is not None
        else DEFAULT_EXCLUDED_PATTERNS
    )
    if depth <= 0:
        depth = 1
    try:
        initial_depth = abs_path.rstrip(os.sep).count(os.sep)
        for root, dirs, files in os.walk(abs_path, topdown=True):
            current_depth = root.rstrip(os.sep).count(os.sep) - initial_depth
            if current_depth >= depth - 1:
                del dirs[:]
            dirs[:] = [
                d
                for d in dirs
                if (include_hidden or not _is_hidden(d))
                and not is_excluded(d, patterns_to_exclude)
            ]
            for filename in files:
                if (include_hidden or not _is_hidden(filename)) and not is_excluded(
                    filename, patterns_to_exclude
                ):
                    full_path = os.path.join(root, filename)
                    rel_full_path = os.path.relpath(full_path, abs_path)
                    if not is_excluded(rel_full_path, patterns_to_exclude):
                        all_files.append(rel_full_path)
        return {"files": sorted(all_files)}

    except (OSError, IOError) as e:
        raise OSError(f"Error listing files in {path}: {e}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error listing files in {path}: {e}")


def _is_hidden(path: str) -> bool:
    """
    Check if path is hidden (starts with '.') but ignore '.' and '..'.
    Args:
        path: File or directory path to check
    Returns:
        True if the path is hidden, False otherwise
    """
    basename = os.path.basename(path)
    # Ignore '.' and '..' as they are not typically considered hidden in listings
    if basename == "." or basename == "..":
        return False
    return basename.startswith(".")


def is_excluded(name: str, patterns: list[str]) -> bool:
    """Check if a name/path matches any exclusion patterns."""
    for pattern in patterns:
        if fnmatch.fnmatch(name, pattern):
            return True
        # Split the path using the OS path separator.
        parts = name.split(os.path.sep)
        # Check each part of the path.
        for part in parts:
            if fnmatch.fnmatch(part, pattern):
                return True
    return False


def read_from_file(
    file: FileToRead | list[FileToRead],
) -> dict[str, Any]:
    """
    Reads content from one or more files, optionally specifying line ranges.

    **EFFICIENCY TIP:**
    For source code or configuration files, prefer reading the **entire file** at once
    to ensure you have full context (imports, class definitions, etc.).
    Only use `start_line` and `end_line` for extremely large files (like logs) or
    when you are certain only a specific section is needed.

    Examples:
    ```
    # Read entire content of a single file
    read_from_file(file={'path': 'path/to/file.txt'})

    # Read specific lines from a file
    # The content will be returned with line numbers in the format: "LINE_NUMBER | line content"
    read_from_file(file={'path': 'path/to/large_file.log', 'start_line': 100, 'end_line': 150})

    # Read multiple files
    read_from_file(file=[
        {'path': 'path/to/file1.txt'},
        {'path': 'path/to/file2.txt', 'start_line': 1, 'end_line': 5}
    ])
    ```

    Args:
        file (FileToRead | list[FileToRead]): A single file configuration or a list of them.

    Returns:
        dict: Content and metadata for a single file, or a dict of results for multiple files.
        The `content` field in the returned dictionary will have line numbers in the format: "LINE_NUMBER | line content"
    """
    is_list = isinstance(file, list)
    files = file if is_list else [file]

    results = {}
    for file_config in files:
        path = file_config["path"]
        start_line = file_config.get("start_line", None)
        end_line = file_config.get("end_line", None)
        try:
            abs_path = os.path.abspath(os.path.expanduser(path))
            if not os.path.exists(abs_path):
                raise FileNotFoundError(f"File not found: {path}")

            content = read_file_with_line_numbers(abs_path)
            lines = content.splitlines()
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
            content_result = "\n".join(selected_lines)

            results[path] = {
                "path": path,
                "content": content_result,
                "start_line": start_idx + 1,
                "end_line": end_idx,
                "total_lines": total_lines,
            }
        except Exception as e:
            if not is_list:
                if isinstance(e, (OSError, IOError)):
                    raise OSError(f"Error reading file {path}: {e}") from e
                raise RuntimeError(f"Unexpected error reading file {path}: {e}") from e
            results[path] = f"Error reading file: {e}"

    if is_list:
        return results

    return results[files[0]["path"]]


def write_to_file(
    file: FileToWrite | list[FileToWrite],
) -> str | dict[str, Any]:
    """
    Writes content to one or more files, with options for overwrite, append, or exclusive
    creation.

    **CRITICAL - PREVENT JSON ERRORS:**
    1. **ESCAPING:** Do NOT double-escape quotes.
       - CORRECT: "content": "He said \"Hello\""
       - WRONG:   "content": "He said \\"Hello\\""  <-- This breaks JSON parsing!
    2. **SIZE LIMIT:** Content MUST NOT exceed 4000 characters.
       - Exceeding this causes truncation and EOF errors.
       - Split larger content into multiple sequential calls (first 'w', then 'a').

    Examples:
    ```
    # Overwrite 'file.txt' with initial content
    write_to_file(file={'path': 'path/to/file.txt', 'content': 'Initial content.'})

    # Append a second chunk to 'file.txt' (note the newline at the beginning of the content)
    write_to_file(file={'path': 'path/to/file.txt', 'content': '\nSecond chunk.', 'mode': 'a'})

    # Write to multiple files
    write_to_file(file=[
        {'path': 'path/to/file1.txt', 'content': 'Content for file 1'},
        {'path': 'path/to/file2.txt', 'content': 'Content for file 2', 'mode': 'w'}
    ])
    ```

    Args:
        file (FileToWrite | list[FileToWrite]): A single file configuration or a list of them.

    Returns:
        Success message for single file, or dict with success/errors for multiple files.
    """
    # Normalize to list
    files = file if isinstance(file, list) else [file]

    success = []
    errors = {}
    for file_config in files:
        path = file_config["path"]
        content = file_config["content"]
        mode = file_config.get("mode", "w")
        try:
            abs_path = os.path.abspath(os.path.expanduser(path))
            # The underlying utility creates the directory, so we don't need to do it here.
            write_file(abs_path, content, mode=mode)
            success.append(path)
        except Exception as e:
            errors[path] = f"Error writing file: {e}"

    # Return appropriate response based on input type
    if isinstance(file, list):
        return {"success": success, "errors": errors}
    else:
        if errors:
            raise RuntimeError(
                f"Error writing file {file['path']}: {errors[file['path']]}"
            )
        return f"Successfully wrote to file: {file['path']} in mode '{file.get('mode', 'w')}'"


def search_files(
    path: str,
    regex: str,
    file_pattern: Optional[str] = None,
    include_hidden: bool = True,
) -> dict[str, Any]:
    """
    Searches for a regex pattern in files within a directory.

    Example:
    search_files(path='src', regex='class \\w+', file_pattern='*.py', include_hidden=False)

    Args:
        path (str): Directory to search.
        regex (str): Regex pattern.
        file_pattern (str): Glob pattern filter.
        include_hidden (bool): Include hidden files.

    Returns:
        dict: Summary and list of matches.
    """
    try:
        pattern = re.compile(regex)
    except re.error as e:
        raise ValueError(f"Invalid regex pattern: {e}")
    search_results = {"summary": "", "results": []}
    match_count = 0
    searched_file_count = 0
    file_match_count = 0
    try:
        abs_path = os.path.abspath(os.path.expanduser(path))
        for root, dirs, files in os.walk(abs_path):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if include_hidden or not _is_hidden(d)]
            for filename in files:
                # Skip hidden files
                if not include_hidden and _is_hidden(filename):
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
                except IOError as e:
                    search_results["results"].append(
                        {"file": rel_file_path, "error": str(e)}
                    )
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
    except (OSError, IOError) as e:
        raise OSError(f"Error searching files in {path}: {e}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error searching files in {path}: {e}")


def _get_file_matches(
    file_path: str,
    pattern: re.Pattern,
    context_lines: int = 2,
) -> list[dict[str, Any]]:
    """Search for regex matches in a file with context."""
    try:
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
    except (OSError, IOError) as e:
        raise IOError(f"Error reading {file_path}: {e}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error processing {file_path}: {e}")


def replace_in_file(
    file: FileReplacement | list[FileReplacement],
) -> str | dict[str, Any]:
    """
    Replaces exact text in files.

    **CRITICAL INSTRUCTIONS:**
    1. **READ FIRST:** Use `read_file` to get exact content. Do not guess.
    2. **EXACT MATCH:** `old_text` must match file content EXACTLY (whitespace, newlines).
    3. **ESCAPING:** Do NOT double-escape quotes in `new_text`. Use `\"`, not `\\"`.
    4. **SIZE LIMIT:** `new_text` MUST NOT exceed 4000 chars to avoid truncation/EOF errors.
    5. **MINIMAL CONTEXT:** Keep `old_text` small (target lines + 2-3 context lines).
    6. **DEFAULT:** Replaces **ALL** occurrences. Set `count=1` for first occurrence only.

    Examples:
    ```
    # Replace ALL occurrences
    replace_in_file(file=[
        {'path': 'file.txt', 'old_text': 'foo', 'new_text': 'bar'},
        {'path': 'file.txt', 'old_text': 'baz', 'new_text': 'qux'}
    ])

    # Replace ONLY the first occurrence
    replace_in_file(
        file={'path': 'file.txt', 'old_text': 'foo', 'new_text': 'bar', 'count': 1}
    )

    # Replace code block (include context for safety)
    replace_in_file(
        file={
            'path': 'app.py',
            'old_text': '    def old_fn():\n        pass',
            'new_text': '    def new_fn():\n        pass'
        }
    )
    ```

    Args:
        file: Single replacement config or list of them.

    Returns:
        Success message or error dict.
    """
    # Normalize to list
    file_replacements = file if isinstance(file, list) else [file]
    # Group replacements by file path to minimize file I/O
    replacements_by_path: dict[str, list[FileReplacement]] = {}
    for r in file_replacements:
        path = r["path"]
        if path not in replacements_by_path:
            replacements_by_path[path] = []
        replacements_by_path[path].append(r)
    success = []
    errors = {}
    for path, replacements in replacements_by_path.items():
        try:
            abs_path = os.path.abspath(os.path.expanduser(path))
            if not os.path.exists(abs_path):
                raise FileNotFoundError(f"File not found: {path}")
            content = read_file(abs_path)
            original_content = content
            # Apply all replacements for this file
            for replacement in replacements:
                old_text = replacement["old_text"]
                new_text = replacement["new_text"]
                count = replacement.get("count", -1)
                if old_text not in content:
                    raise ValueError(f"old_text not found in file: {path}")
                # Replace occurrences
                content = content.replace(old_text, new_text, count)
            # Only write if content actually changed
            if content != original_content:
                write_file(abs_path, content)
                success.append(path)
            else:
                success.append(f"{path} (no changes needed)")
        except Exception as e:
            errors[path] = f"Error applying replacement to {path}: {e}"
    # Return appropriate response based on input type
    if isinstance(file, list):
        return {"success": success, "errors": errors}
    path = file["path"]
    if errors:
        error_message = errors[path]
        raise RuntimeError(f"Error applying replacement to {path}: {error_message}")
    return f"Successfully applied replacement(s) to {path}"


async def analyze_file(
    ctx: AnyContext, path: str, query: str, token_threshold: int | None = None
) -> dict[str, Any]:
    """
    Analyzes a file using a sub-agent for complex questions.

    CRITICAL: The query must contain ALL necessary context, instructions, and information.
        The sub-agent performing the analysis does NOT share your current conversation
        history, memory, or global context.
        The quality of analysis depends entirely on the query. Vague queries yield poor
        results.

    Example:
    analyze_file(path='src/main.py', query='Summarize the main function.')

    Args:
        ctx (AnyContext): The execution context.
        path (str): The path to the file to analyze.
        query (str): A specific analysis query with clear guidelines and
            necessary information.
        token_threshold (int | None): Max tokens.

    Returns:
        Analysis results.
    """
    if token_threshold is None:
        token_threshold = CFG.LLM_FILE_ANALYSIS_TOKEN_THRESHOLD
    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"File not found: {path}")
    file_content = read_file(abs_path)
    _analyze_file = create_sub_agent_tool(
        tool_name="analyze_file",
        tool_description=(
            "Analyze file content using LLM sub-agent "
            "for complex questions about code structure, documentation "
            "quality, or file-specific analysis. Use for questions that "
            "require understanding beyond simple text reading."
        ),
        system_prompt=CFG.LLM_FILE_EXTRACTOR_SYSTEM_PROMPT,
        tools=[read_from_file, search_files],
        auto_summarize=False,
        remember_history=False,
    )
    payload = json.dumps(
        {
            "instruction": query,
            "file_path": abs_path,
            "file_content": llm_rate_limitter.clip_prompt(
                file_content, token_threshold
            ),
        }
    )
    return await _analyze_file(ctx, payload)
