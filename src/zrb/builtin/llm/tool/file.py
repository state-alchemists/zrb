import fnmatch
import json
import os
import re
from typing import Any, Optional

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
]


def list_files(
    path: str = ".",
    recursive: bool = True,
    include_hidden: bool = False,
    excluded_patterns: Optional[list[str]] = None,
) -> str:
    """List files/directories in a path, excluding specified patterns.
    Args:
        path (str): Path to list. Pass exactly as provided, including '~'. Defaults to ".".
        recursive (bool): List recursively. Defaults to True.
        include_hidden (bool): Include hidden files/dirs. Defaults to False.
        excluded_patterns (Optional[List[str]]): List of glob patterns to exclude.
            Defaults to a comprehensive list of common temporary/artifact patterns.
    Returns:
        str: JSON string: {"files": ["file1.txt", ...]} or {"error": "..."}
    Raises:
        Exception: If an error occurs.
    """
    all_files: list[str] = []
    abs_path = os.path.abspath(os.path.expanduser(path))
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
                    and not _is_excluded(d, patterns_to_exclude)
                ]
                # Process files
                for filename in files:
                    if (
                        include_hidden or not _is_hidden(filename)
                    ) and not _is_excluded(filename, patterns_to_exclude):
                        full_path = os.path.join(root, filename)
                        # Check rel path for patterns like '**/node_modules/*'
                        rel_full_path = os.path.relpath(full_path, abs_path)
                        is_rel_path_excluded = _is_excluded(
                            rel_full_path, patterns_to_exclude
                        )
                        if not is_rel_path_excluded:
                            all_files.append(full_path)
        else:
            # Non-recursive listing (top-level only)
            for item in os.listdir(abs_path):
                full_path = os.path.join(abs_path, item)
                # Include both files and directories if not recursive
                if (include_hidden or not _is_hidden(item)) and not _is_excluded(
                    item, patterns_to_exclude
                ):
                    all_files.append(full_path)
        # Return paths relative to the original path requested
        try:
            rel_files = [
                os.path.relpath(f, os.path.dirname(abs_path)) for f in all_files
            ]
            return json.dumps({"files": sorted(rel_files)})
        except (
            ValueError
        ) as e:  # Handle case where path is '.' and abs_path is CWD root
            if "path is on mount '" in str(e) and "' which is not on mount '" in str(e):
                # If paths are on different mounts, just use absolute paths
                rel_files = all_files
                return json.dumps({"files": sorted(rel_files)})
            raise
    except (OSError, IOError) as e:
        raise OSError(f"Error listing files in {path}: {e}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error listing files in {path}: {e}")


def _is_hidden(path: str) -> bool:
    """
    Check if path is hidden (starts with '.').
    Args:
        path: File or directory path to check
    Returns:
        True if the path is hidden, False otherwise
    """
    # Extract just the basename to check if it starts with a dot
    return os.path.basename(path).startswith(".")


def _is_excluded(name: str, patterns: list[str]) -> bool:
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
    path: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
) -> str:
    """Read file content (or specific lines) at a path, including line numbers.
    Args:
        path (str): Path to read. Pass exactly as provided, including '~'.
        start_line (Optional[int]): Starting line number (1-based).
            Defaults to None (start of file).
        end_line (Optional[int]): Ending line number (1-based, inclusive).
            Defaults to None (end of file).
    Returns:
        str: JSON: {"path": "...", "content": "...", "start_line": N, ...} or {"error": "..."}
        The content includes line numbers.
    Raises:
        Exception: If an error occurs.
    """
    try:
        abs_path = os.path.abspath(os.path.expanduser(path))
        # Check if file exists
        if not os.path.exists(abs_path):
            return json.dumps({"error": f"File {path} does not exist"})
        content = read_file_with_line_numbers(abs_path)
        lines = content.splitlines()
        total_lines = len(lines)
        # Adjust line indices (convert from 1-based to 0-based)
        start_idx = (start_line - 1) if start_line is not None else 0
        end_idx = end_line if end_line is not None else total_lines
        # Validate indices
        if start_idx < 0:
            start_idx = 0
        if end_idx > total_lines:
            end_idx = total_lines
        if start_idx > end_idx:
            start_idx = end_idx
        # Select the lines for the result
        selected_lines = lines[start_idx:end_idx]
        content_result = "\n".join(selected_lines)
        return json.dumps(
            {
                "path": path,
                "content": content_result,
                "start_line": start_idx + 1,  # Convert back to 1-based for output
                "end_line": end_idx,  # end_idx is already exclusive upper bound
                "total_lines": total_lines,
            }
        )
    except (OSError, IOError) as e:
        raise OSError(f"Error reading file {path}: {e}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error reading file {path}: {e}")


def write_to_file(
    path: str,
    content: str,
    line_count: int,
) -> str:
    """Write full content to a file. Creates/overwrites file.
    Args:
        path (str): Path to write. Pass exactly as provided, including '~'.
        content (str): Full file content.
            MUST be complete, no truncation/omissions. Exclude line numbers.
        line_count (int): Number of lines in the provided content.
    Returns:
        str: JSON: {"success": true, "path": "f.txt", "warning": "..."} or {"error": "..."}
    Raises:
        Exception: If an error occurs.
    """
    actual_lines = len(content.splitlines())
    warning = None
    if actual_lines != line_count:
        warning = (
            f"Provided line_count ({line_count}) does not match actual "
            f"content lines ({actual_lines}) for file {path}"
        )
    try:
        abs_path = os.path.abspath(os.path.expanduser(path))
        # Ensure directory exists
        directory = os.path.dirname(abs_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        write_file(abs_path, content)
        result_data = {"success": True, "path": path}
        if warning:
            result_data["warning"] = warning
        return json.dumps(result_data)
    except (OSError, IOError) as e:
        raise OSError(f"Error writing file {path}: {e}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error writing file {path}: {e}")


def search_files(
    path: str,
    regex: str,
    file_pattern: Optional[str] = None,
    include_hidden: bool = True,
) -> str:
    """Search files in a directory using regex, showing context.
    Args:
        path (str): Path to search. Pass exactly as provided, including '~'.
        regex (str): Python regex pattern to search for.
        file_pattern (Optional[str]): Glob pattern to filter files
            (e.g., '*.py'). Defaults to None.
        include_hidden (bool): Include hidden files/dirs. Defaults to True.
    Returns:
        str: JSON: {"summary": "...", "results": [{"file":"f.py", ...}]} or {"error": "..."}
    Raises:
        Exception: If error occurs or regex is invalid.
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
        return json.dumps(
            search_results
        )  # No need for pretty printing for LLM consumption
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


def apply_diff(
    path: str,
    diff: str,
    search_marker: str = "<<<<<< SEARCH",
    meta_marker: str = "------",
    separator: str = "======",
    replace_marker: str = ">>>>>> REPLACE",
) -> str:
    """Apply a precise search/replace diff to a file.
    Args:
        path (str): Path to modify. Pass exactly as provided, including '~'.
        diff (str): Search/replace block defining changes (see format example below).
        search_marker (str): Marker for start of search block. Defaults to "<<<<<< SEARCH".
        meta_marker (str): Marker for start of content to search for. Defaults to "------".
        separator (str): Marker separating search/replace content. Defaults to "======".
        replace_marker (str): Marker for end of replacement block.
            Defaults to ">>>>>> REPLACE".
    SEARCH block must exactly match file content including whitespace/indentation.
    SEARCH block should NOT contains line numbers
    Format example:
        [Search Marker, e.g., <<<<<< SEARCH]
        :start_line:10
        :end_line:15
        [Meta Marker, e.g., ------]
        [exact content to find including whitespace]
        [Separator, e.g., ======]
        [new content to replace with]
        [Replace Marker, e.g., >>>>>> REPLACE]
    Returns:
        str: JSON: {"success": true, "path": "f.py"} or {"success": false, "error": "..."}
    Raises:
        Exception: If an error occurs.
    """
    try:
        start_line, end_line, search_content, replace_content = _parse_diff(
            diff, search_marker, meta_marker, separator, replace_marker
        )
        abs_path = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(abs_path):
            return json.dumps(
                {"success": False, "path": path, "error": f"File not found at {path}"}
            )
        content = read_file(abs_path)
        lines = content.splitlines()
        if start_line < 1 or end_line > len(lines) or start_line > end_line:
            return json.dumps(
                {
                    "success": False,
                    "path": path,
                    "error": (
                        f"Invalid line range {start_line}-{end_line} "
                        f"for file with {len(lines)} lines."
                    ),
                }
            )
        original_content = "\n".join(lines[start_line - 1 : end_line])
        if original_content != search_content:
            error_message = (
                f"Search content does not match file content at "
                f"lines {start_line}-{end_line}.\n"
                f"Expected ({len(search_content.splitlines())} lines):\n"
                f"---\n{search_content}\n---\n"
                f"Actual ({len(lines[start_line-1:end_line])} lines):\n"
                f"---\n{original_content}\n---"
            )
            return json.dumps({"success": False, "path": path, "error": error_message})
        new_lines = (
            lines[: start_line - 1] + replace_content.splitlines() + lines[end_line:]
        )
        new_content = "\n".join(new_lines)
        if content.endswith("\n"):
            new_content += "\n"
        write_file(abs_path, new_content)
        return json.dumps({"success": True, "path": path})
    except ValueError as e:
        raise ValueError(f"Error parsing diff: {e}")
    except (OSError, IOError) as e:
        raise OSError(f"Error applying diff to {path}: {e}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error applying diff to {path}: {e}")


def _parse_diff(
    diff: str,
    search_marker: str,
    meta_marker: str,
    separator: str,
    replace_marker: str,
) -> tuple[int, int, str, str]:
    """
    Parse diff content into components.
    Args:
        diff: The diff content to parse
        search_marker: Marker indicating the start of the search block
        meta_marker: Marker indicating the start of the content to search for
        separator: Marker separating search content from replacement content
        replace_marker: Marker indicating the end of the replacement block
    Returns:
        Tuple of (start_line, end_line, search_content, replace_content)
    Raises:
        ValueError: If diff format is invalid or missing required markers
        ValueError: If start_line or end_line cannot be parsed
    """
    # Find all marker positions
    search_start_idx = diff.find(search_marker)
    meta_start_idx = diff.find(meta_marker)
    separator_idx = diff.find(separator)
    replace_end_idx = diff.find(replace_marker)
    # Validate all markers are present
    missing_markers = []
    if search_start_idx == -1:
        missing_markers.append("search marker")
    if meta_start_idx == -1:
        missing_markers.append("meta marker")
    if separator_idx == -1:
        missing_markers.append("separator")
    if replace_end_idx == -1:
        missing_markers.append("replace marker")
    if missing_markers:
        raise ValueError(f"Invalid diff format - missing: {', '.join(missing_markers)}")
    # Extract metadata
    meta_content = diff[search_start_idx + len(search_marker) : meta_start_idx].strip()
    # Parse line numbers
    start_line_match = re.search(r":start_line:(\d+)", meta_content)
    end_line_match = re.search(r":end_line:(\d+)", meta_content)
    if not start_line_match:
        raise ValueError("Missing start_line in diff metadata")
    if not end_line_match:
        raise ValueError("Missing end_line in diff metadata")
    start_line = int(start_line_match.group(1))
    end_line = int(end_line_match.group(1))
    # Extract content sections
    search_content = diff[meta_start_idx + len(meta_marker) : separator_idx].strip(
        "\r\n"
    )
    replace_content = diff[separator_idx + len(separator) : replace_end_idx].strip(
        "\r\n"
    )
    return start_line, end_line, search_content, replace_content
