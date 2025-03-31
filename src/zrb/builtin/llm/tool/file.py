import fnmatch
import os
import re
from typing import Dict, List, Optional, Tuple, Union

from zrb.util.file import read_file as _read_file
from zrb.util.file import write_file as _write_file

# Common directories and files to exclude from file operations
_DEFAULT_EXCLUDES = [
    # Version control
    ".git",
    ".svn",
    ".hg",
    # Dependencies and packages
    "node_modules",
    "venv",
    ".venv",
    "env",
    ".env",
    # Build and cache
    "__pycache__",
    "*.pyc",
    "build",
    "dist",
    "target",
    # IDE and editor files
    ".idea",
    ".vscode",
    "*.swp",
    "*.swo",
    # OS-specific
    ".DS_Store",
    "Thumbs.db",
    # Temporary and backup files
    "*.tmp",
    "*.bak",
    "*.log",
]

# Maximum number of lines to read before truncating
_MAX_LINES_BEFORE_TRUNCATION = 1000

# Number of context lines to show around method definitions when truncating
_CONTEXT_LINES = 5


def list_files(
    path: str = ".",
    recursive: bool = True,
    file_pattern: Optional[str] = None,
    excluded_patterns: list[str] = _DEFAULT_EXCLUDES,
) -> list[str]:
    """
    List files in a directory that match specified patterns.

    Args:
        path: The path of the directory to list contents for
            (relative to the current working directory)
        recursive: Whether to list files recursively.
            Use True for recursive listing, False for top-level only.
        file_pattern: Optional glob pattern to filter files.
            None by default (all files will be included).
        excluded_patterns: List of glob patterns to exclude. By default, contains sane values
            to exclude common directories and files like version control, build artifacts,
            and temporary files.

    Returns:
        A list of file paths matching the criteria
    """
    all_files: list[str] = []

    if recursive:
        for root, dirs, files in os.walk(path):
            # Filter out excluded directories to avoid descending into them
            dirs[:] = [
                d
                for d in dirs
                if not _should_exclude(os.path.join(root, d), excluded_patterns)
            ]

            for filename in files:
                full_path = os.path.join(root, filename)
                # If file_pattern is None, include all files, otherwise match the pattern
                if file_pattern is None or fnmatch.fnmatch(filename, file_pattern):
                    if not _should_exclude(full_path, excluded_patterns):
                        all_files.append(full_path)
    else:
        # Non-recursive listing (top-level only)
        try:
            for item in os.listdir(path):
                full_path = os.path.join(path, item)
                if os.path.isfile(full_path):
                    # If file_pattern is None, include all files, otherwise match the pattern
                    if file_pattern is None or fnmatch.fnmatch(item, file_pattern):
                        if not _should_exclude(full_path, excluded_patterns):
                            all_files.append(full_path)
        except (FileNotFoundError, PermissionError) as e:
            print(f"Error listing files in {path}: {e}")

    return sorted(all_files)


def _should_exclude(
    full_path: str, excluded_patterns: list[str] = _DEFAULT_EXCLUDES
) -> bool:
    """
    Return True if the file at full_path should be excluded based on
    the list of excluded_patterns. Patterns that include a path separator
    are applied to the full normalized path; otherwise they are matched
    against each individual component of the path.

    Args:
        full_path: The full path to check
        excluded_patterns: List of patterns to exclude

    Returns:
        True if the path should be excluded, False otherwise
    """
    norm_path = os.path.normpath(full_path)
    path_parts = norm_path.split(os.sep)

    for pat in excluded_patterns:
        # If the pattern seems intended for full path matching (contains a separator)
        if os.sep in pat or "/" in pat:
            if fnmatch.fnmatch(norm_path, pat):
                return True
        else:
            # Otherwise check each part of the path
            if any(fnmatch.fnmatch(part, pat) for part in path_parts):
                return True
            # Also check the filename against the pattern
            if os.path.isfile(full_path) and fnmatch.fnmatch(
                os.path.basename(full_path), pat
            ):
                return True

    return False


def read_from_file(
    path: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    auto_truncate: bool = False,
) -> str:
    """
    Read the contents of a file at the specified path.

    Args:
        path: The path of the file to read (relative to the current working directory)
        start_line: The starting line number to read from (1-based).
            If not provided, starts from the beginning.
        end_line: The ending line number to read to (1-based, inclusive).
            If not provided, reads to the end.
        auto_truncate: Whether to automatically truncate large files when start_line
            and end_line are not specified. If true and the file exceeds a certain
            line threshold, it will return a subset of lines with information about
            the total line count and method definitions. Default is False for backward
            compatibility, but setting to True is recommended for large files.

    Returns:
        A string containing the file content, with line numbers prefixed to each line.
        For truncated files, includes summary information.
    """
    try:
        abs_path = os.path.abspath(path)

        # Read the entire file content
        content = _read_file(abs_path)
        lines = content.splitlines()
        total_lines = len(lines)

        # Determine if we should truncate
        should_truncate = (
            auto_truncate
            and start_line is None
            and end_line is None
            and total_lines > _MAX_LINES_BEFORE_TRUNCATION
        )

        # Adjust line indices (convert from 1-based to 0-based)
        start_idx = (start_line - 1) if start_line is not None else 0
        end_idx = end_line if end_line is not None else total_lines

        # Validate indices
        if start_idx < 0:
            start_idx = 0
        if end_idx > total_lines:
            end_idx = total_lines

        if should_truncate:
            # Find method definitions and their line ranges
            method_info = _find_method_definitions(lines)

            # Create a truncated view with method definitions
            result_lines = []

            # Add file info header
            result_lines.append(f"File: {path} (truncated, {total_lines} lines total)")
            result_lines.append("")

            # Add beginning of file (first 100 lines)
            first_chunk = min(100, total_lines // 3)
            for i in range(first_chunk):
                result_lines.append(f"{i+1} | {lines[i]}")

            result_lines.append("...")
            omitted_msg = (
                f"[{first_chunk+1} - {total_lines-100}] Lines omitted for brevity"
            )
            result_lines.append(omitted_msg)
            result_lines.append("...")

            # Add end of file (last 100 lines)
            for i in range(max(first_chunk, total_lines - 100), total_lines):
                result_lines.append(f"{i+1} | {lines[i]}")

            # Add method definitions summary
            if method_info:
                result_lines.append("")
                result_lines.append("Method definitions found:")
                for method in method_info:
                    method_line = (
                        f"- {method['name']} "
                        f"(lines {method['start_line']}-{method['end_line']})"
                    )
                    result_lines.append(method_line)

            return "\n".join(result_lines)
        else:
            # Return the requested range with line numbers
            result_lines = []
            for i in range(start_idx, end_idx):
                result_lines.append(f"{i+1} | {lines[i]}")

            return "\n".join(result_lines)

    except Exception as e:
        return f"Error reading file {path}: {str(e)}"


def _find_method_definitions(lines: List[str]) -> List[Dict[str, Union[str, int]]]:
    """
    Find method definitions in the given lines of code.

    Args:
        lines: List of code lines to analyze

    Returns:
        List of dictionaries containing method name, start line, and end line
    """
    method_info = []

    # Simple regex patterns for common method/function definitions
    patterns = [
        # Python
        r"^\s*def\s+([a-zA-Z0-9_]+)\s*\(",
        # JavaScript/TypeScript
        r"^\s*(function\s+([a-zA-Z0-9_]+)|([a-zA-Z0-9_]+)\s*=\s*function|"
        r"\s*([a-zA-Z0-9_]+)\s*\([^)]*\)\s*{)",
        # Java/C#/C++
        r"^\s*(?:public|private|protected|static|final|abstract|synchronized)?"
        r"\s+(?:[a-zA-Z0-9_<>[\]]+\s+)+([a-zA-Z0-9_]+)\s*\(",
    ]

    current_method = None

    for i, line in enumerate(lines):
        # Check if this line starts a method definition
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                # If we were tracking a method, close it
                if current_method:
                    current_method["end_line"] = i
                    method_info.append(current_method)

                # Start tracking a new method
                method_name = next(
                    group for group in match.groups() if group is not None
                )
                current_method = {
                    "name": method_name,
                    "start_line": i + 1,  # 1-based line numbering
                    "end_line": None,
                }
                break

        # Check for method end (simplistic approach)
        if current_method and line.strip() == "}":
            current_method["end_line"] = i + 1
            method_info.append(current_method)
            current_method = None

    # Close any open method at the end of the file
    if current_method:
        current_method["end_line"] = len(lines)
        method_info.append(current_method)

    return method_info


def write_to_file(path: str, content: str) -> bool:
    """
    Write content to a file at the specified path.

    Args:
        path: The path of the file to write to (relative to the current working directory)
        content: The content to write to the file

    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure directory exists
        directory = os.path.dirname(os.path.abspath(path))
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

        # Write the content
        _write_file(os.path.abspath(path), content)
        return True
    except Exception as e:
        print(f"Error writing to file {path}: {str(e)}")
        return False


def search_files(
    path: str, regex: str, file_pattern: Optional[str] = None, context_lines: int = 2
) -> str:
    """
    Search for a regex pattern across files in a specified directory.

    Args:
        path: The path of the directory to search in
            (relative to the current working directory)
        regex: The regular expression pattern to search for
        file_pattern: Optional glob pattern to filter files.
            Default is None, which includes all files. Only specify this if you need to
            filter to specific file types (but in most cases, leaving as None is better).
        context_lines: Number of context lines to show before and after each match.
            Default is 2, which provides good context without overwhelming output.

    Returns:
        A string containing the search results with context
    """
    try:
        # Compile the regex pattern
        pattern = re.compile(regex)

        # Get the list of files to search
        files = list_files(path, recursive=True, file_pattern=file_pattern)

        results = []
        match_count = 0

        for file_path in files:
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()

                file_matches = []

                for i, line in enumerate(lines):
                    if pattern.search(line):
                        # Determine context range
                        start = max(0, i - context_lines)
                        end = min(len(lines), i + context_lines + 1)

                        # Add file header if this is the first match in the file
                        if not file_matches:
                            file_matches.append(
                                f"\n{'-' * 80}\n{file_path}\n{'-' * 80}"
                            )

                        # Add separator if this isn't the first match and isn't contiguous
                        # with previous
                        if (
                            file_matches
                            and file_matches[-1] != f"Line {start+1}-{end}:"
                        ):
                            file_matches.append(f"\nLine {start+1}-{end}:")

                        # Add context lines
                        for j in range(start, end):
                            prefix = ">" if j == i else " "
                            file_matches.append(f"{prefix} {j+1}: {lines[j].rstrip()}")

                        match_count += 1

                if file_matches:
                    results.extend(file_matches)

            except Exception as e:
                results.append(f"Error reading {file_path}: {str(e)}")

        if not results:
            return f"No matches found for pattern '{regex}' in {path}"

        # Count unique files by counting headers
        file_count = len([r for r in results if r.startswith("-" * 80)])
        summary = f"Found {match_count} matches in {file_count} files:\n"
        return summary + "\n".join(results)

    except Exception as e:
        return f"Error searching files: {str(e)}"


def apply_diff(path: str, diff: str, start_line: int, end_line: int) -> bool:
    """
    Replace existing code using a search and replace block.

    Args:
        path: The path of the file to modify (relative to the current working directory)
        diff: The search/replace block defining the changes
        start_line: The line number where the search block starts (1-based)
        end_line: The line number where the search block ends (1-based)

    Returns:
        True if successful, False otherwise

    The diff format should be:
    ```
    <<<<<<< SEARCH
    [exact content to find including whitespace]
    =======
    [new content to replace with]
    >>>>>>> REPLACE
    ```
    """
    try:
        # Read the file
        abs_path = os.path.abspath(path)
        content = _read_file(abs_path)
        lines = content.splitlines()

        # Validate line numbers
        if start_line < 1 or end_line > len(lines) or start_line > end_line:
            print(
                f"Invalid line range: {start_line}-{end_line} (file has {len(lines)} lines)"
            )
            return False

        # Parse the diff
        search_content, replace_content = _parse_diff(diff)
        if search_content is None or replace_content is None:
            print("Invalid diff format")
            return False

        # Extract the content to be replaced
        original_content = "\n".join(lines[start_line - 1 : end_line])

        # Verify the search content matches
        if original_content != search_content:
            print("Search content does not match the specified lines in the file")
            return False

        # Replace the content
        new_lines = (
            lines[: start_line - 1] + replace_content.splitlines() + lines[end_line:]
        )
        new_content = "\n".join(new_lines)

        # Write the modified content back to the file
        _write_file(abs_path, new_content)
        return True

    except Exception as e:
        print(f"Error applying diff to {path}: {str(e)}")
        return False


def _parse_diff(diff: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse a diff string to extract search and replace content.

    Args:
        diff: The diff string to parse

    Returns:
        A tuple of (search_content, replace_content), or (None, None) if parsing fails
    """
    try:
        # Split the diff into sections
        search_marker = "<<<<<<< SEARCH"
        separator = "======="
        replace_marker = ">>>>>>> REPLACE"

        if (
            search_marker not in diff
            or separator not in diff
            or replace_marker not in diff
        ):
            return None, None

        # Extract search content
        search_start = diff.index(search_marker) + len(search_marker)
        search_end = diff.index(separator)
        search_content = diff[search_start:search_end].strip()

        # Extract replace content
        replace_start = diff.index(separator) + len(separator)
        replace_end = diff.index(replace_marker)
        replace_content = diff[replace_start:replace_end].strip()

        return search_content, replace_content

    except Exception:
        return None, None
