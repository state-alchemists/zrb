import fnmatch
import json
import os
import re
import sys
from typing import Any, Literal, Optional

from zrb.builtin.llm.tool.sub_agent import create_sub_agent_tool
from zrb.config.config import CFG
from zrb.config.llm_rate_limitter import llm_rate_limitter
from zrb.context.any_context import AnyContext
from zrb.util.file import read_file, read_file_with_line_numbers, write_file

if sys.version_info >= (3, 12):
    from typing import NotRequired, TypedDict
else:
    from typing_extensions import NotRequired, TypedDict


class FileToRead(TypedDict):
    """
    Configuration for reading a file or file section.

    Attributes:
        path (str): Absolute or relative path to the file
        start_line (int | None): Starting line number (1-based, inclusive). If None, reads from beginning.
        end_line (int | None): Ending line number (1-based, exclusive). If None, reads to end.
    """

    path: str
    start_line: NotRequired[int | None]
    end_line: NotRequired[int | None]


class FileToWrite(TypedDict):
    """
    Configuration for writing content to a file.

    Attributes:
        path (str): Absolute or relative path where file will be written.
        content (str): Content to write. CRITICAL: For JSON, ensure all special characters in this string are properly escaped.
        mode (str): Mode for writing: 'w' (overwrite, default), 'a' (append), 'x' (create exclusively).
    """

    path: str
    content: str
    mode: NotRequired[Literal["w", "wt", "tw", "a", "at", "ta", "x", "xt", "tx"]]




class Replacement(TypedDict):
    """
    Configuration for a single text replacement operation.

    Attributes:
        old_string (str): Exact text to find and replace (must match file content exactly)
        new_string (str): New text to replace with
    """

    old_string: str
    new_string: str


class FileReplacement(TypedDict):
    """Represents a file replacement operation with path and one or more replacements."""

    path: str
    replacements: list[Replacement]


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
    recursive: bool = True,
    include_hidden: bool = False,
    excluded_patterns: Optional[list[str]] = None,
) -> dict[str, list[str]]:
    """
    List files and directories in a given path, with options for recursive listing, including hidden files, and excluding patterns.

    Args:
        path (str): The directory path to list. Defaults to the current directory.
        recursive (bool): If True, lists files recursively. Defaults to True.
        include_hidden (bool): If True, includes hidden files (dotfiles). Defaults to False.
        excluded_patterns (Optional[list[str]]): A list of glob patterns to exclude. Uses sensible defaults if None.

    Returns:
        A dictionary with a 'files' key containing a sorted list of relative file paths.
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
    try:
        if recursive:
            for root, dirs, files in os.walk(abs_path, topdown=True):
                # Filter directories in-place
                dirs[:] = [
                    d
                    for d in dirs
                    if (include_hidden or not _is_hidden(d))
                    and not is_excluded(d, patterns_to_exclude)
                ]
                # Process files
                for filename in files:
                    if (include_hidden or not _is_hidden(filename)) and not is_excluded(
                        filename, patterns_to_exclude
                    ):
                        full_path = os.path.join(root, filename)
                        # Check rel path for patterns like '**/node_modules/*'
                        rel_full_path = os.path.relpath(full_path, abs_path)
                        is_rel_path_excluded = is_excluded(
                            rel_full_path, patterns_to_exclude
                        )
                        if not is_rel_path_excluded:
                            all_files.append(full_path)
        else:
            # Non-recursive listing (top-level only)
            for item in os.listdir(abs_path):
                full_path = os.path.join(abs_path, item)
                # Include both files and directories if not recursive
                if (include_hidden or not _is_hidden(item)) and not is_excluded(
                    item, patterns_to_exclude
                ):
                    all_files.append(full_path)
        # Return paths relative to the original path requested
        try:
            rel_files = [os.path.relpath(f, abs_path) for f in all_files]
            return {"files": sorted(rel_files)}
        except (
            ValueError
        ) as e:  # Handle case where path is '.' and abs_path is CWD root
            if "path is on mount '" in str(e) and "' which is not on mount '" in str(e):
                # If paths are on different mounts, just use absolute paths
                rel_files = all_files
                return {"files": sorted(rel_files)}
            raise
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
    Read the content of a file or a specific range of lines. Can also read multiple files at once.

    Args:
        file (FileToRead | list[FileToRead]): A single file configuration or a list of them.
            Each `FileToRead` should have:
            - path (str): The path to the file to read.
            - start_line (int | None): The 1-based line number to start reading from. Defaults to the beginning.
            - end_line (int | None): The 1-based line number to stop reading at (exclusive). Defaults to the end.

    Returns:
        If a single file is read, returns a dictionary with its content and metadata.
        If multiple files are read, returns a dictionary mapping each file path to its content and metadata, or an error string.
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
    Write content to a file. Can overwrite, append, or create exclusively.

    **WARNING:** The default mode 'w' is a destructive operation that overwrites the entire file.
    Use mode 'a' to append or 'x' to create a file only if it does not exist.
    For targeted changes within a file, use `replace_in_file` instead.

    Args:
        file (FileToWrite | list[FileToWrite]): A single file configuration or a list of them.
            Each `FileToWrite` should have:
            - path (str): The path of the file to write to.
            - content (str): The content to write.
            - mode (str, optional): 'w' to overwrite (default), 'a' to append, 'x' to create exclusively.

    Returns:
        If a single file is written, returns a success message.
        If multiple files are written, returns a dictionary with 'success' and 'errors' keys.
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
    Search for a regular expression (regex) pattern in files within a given directory.

    Args:
        path (str): The directory path to search in.
        regex (str): The regular expression pattern to search for.
        file_pattern (Optional[str]): A glob pattern to filter files (e.g., "*.py", "*.md").
        include_hidden (bool): If True, searches hidden files. Defaults to True.

    Returns:
        A dictionary containing a 'summary' of the search and a 'results' list with matches per file.
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
    file_path: str, pattern: re.Pattern, context_lines: int = 2
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
    Replace the first occurrence of one or more strings in a file.

    **CRITICAL:** `old_string` must be an exact match of the file content, including whitespace and newlines. Always use `read_from_file` first to get the exact text block.

    Args:
        file_replacement (FileReplacement | list[FileReplacement]): A single or multiple file replacement configurations.
            Each `FileReplacement` should have:
            - path (str): The path of the file to modify.
            - replacements (list[Replacement]): A list of replacement operations.
                Each `Replacement` should have:
                - old_string (str): The exact string to be replaced.
                - new_string (str): The new string to insert.

    Returns:
        If a single file is modified, returns a success message.
        If multiple files are modified, returns a dictionary with 'success' and 'errors' keys.
    """
    # Normalize to list
    file_replacements = file if isinstance(file, list) else [file]
    success = []
    errors = {}
    for file_replacement_config in file_replacements:
        path = file_replacement_config["path"]
        replacements = file_replacement_config["replacements"]
        try:
            abs_path = os.path.abspath(os.path.expanduser(path))
            if not os.path.exists(abs_path):
                raise FileNotFoundError(f"File not found: {path}")
            content = read_file(abs_path)
            original_content = content
            # Apply all replacements
            for replacement in replacements:
                old_string = replacement["old_string"]
                new_string = replacement["new_string"]
                if old_string not in content:
                    raise ValueError(f"old_string not found in file: {path}")
                # Replace first occurrence only (maintains current behavior)
                content = content.replace(old_string, new_string, 1)
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
    else:
        if errors:
            raise RuntimeError(
                f"Error applying replacement to {file['path']}: {errors[file['path']]}"
            )
        return f"Successfully applied replacement(s) to {file['path']}"


async def analyze_file(
    ctx: AnyContext, path: str, query: str, token_limit: int | None = None
) -> dict[str, Any]:
    """
    Perform a high-level, goal-oriented analysis of a single file to answer a specific query.

    Uses a sub-agent for complex questions about code structure, documentation quality, or other file-specific analysis.

    Args:
        ctx (AnyContext): The execution context.
        path (str): The path to the file to analyze.
        query (str): A specific analysis query with clear guidelines.
        token_limit (int | None): The maximum number of tokens for the analysis. Uses a default if None.

    Returns:
        A dictionary containing the analysis results from the sub-agent.
    """
    if token_limit is None:
        token_limit = CFG.LLM_FILE_ANALYSIS_TOKEN_LIMIT
    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"File not found: {path}")
    file_content = read_file(abs_path)
    _analyze_file = create_sub_agent_tool(
        tool_name="analyze_file",
        tool_description="Analyze file content using LLM sub-agent for complex questions about code structure, documentation quality, or file-specific analysis. Use for questions that require understanding beyond simple text reading.",
        system_prompt=CFG.LLM_FILE_EXTRACTOR_SYSTEM_PROMPT,
        tools=[read_from_file, search_files],
    )
    payload = json.dumps(
        {
            "instruction": query,
            "file_path": abs_path,
            "file_content": llm_rate_limitter.clip_prompt(file_content, token_limit),
        }
    )
    return await _analyze_file(ctx, payload)
