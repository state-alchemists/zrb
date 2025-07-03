import fnmatch
import json
import os
import re
from typing import Any, Dict, List, Optional

from zrb.builtin.llm.tool.sub_agent import create_sub_agent_tool
from zrb.context.any_context import AnyContext
from zrb.llm_rate_limitter import llm_rate_limitter
from zrb.util.file import read_file, read_file_with_line_numbers, write_file

_EXTRACT_INFO_FROM_FILE_SYSTEM_PROMPT = """
You are an extraction info agent.
Your goal is to help to extract relevant information to help the main assistant.
You write your output is in markdown format containing path and relevant information.
Extract only information that relevant to main assistant's goal.

Extracted Information format (Use this as reference, extract relevant information only):
# imports
- <imported-package>
- ...
# variables
- <variable-type> <variable-name>: <the-purpose-of-the-variable>
- ...
# functions
- <function-name>:
  - parameters: <parameters>
  - logic/description: <what-the-function-do-and-how-it-works>
...
...
""".strip()


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
    path: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
) -> str:
    """Read file content (or specific lines) at a path, including line numbers.
    This tool can read both, text and pdf file.
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
    abs_path = os.path.abspath(os.path.expanduser(path))
    # Check if file exists
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"File not found: {path}")
    try:
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
    start_line: int,
    end_line: int,
    search_content: str,
    replace_content: str,
) -> str:
    """Apply a precise search/replace to a file based on line numbers and content.
    Args:
        path (str): Path to modify. Pass exactly as provided, including '~'.
        start_line (int): The 1-based starting line number of the content to replace.
        end_line (int): The 1-based ending line number (inclusive) of the content to replace.
        search_content (str): The exact content expected to be found in the specified
            line range. Must exactly match file content including whitespace/indentation,
            excluding line numbers.
        replace_content (str): The new content to replace the search_content with.
            Excluding line numbers.
    Returns:
        str: JSON: {"success": true, "path": "f.py"} or {"success": false, "error": "..."}
    Raises:
        Exception: If an error occurs.
    """
    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"File not found: {path}")
    try:
        content = read_file(abs_path)
        lines = content.splitlines()
        if start_line < 1 or end_line > len(lines) or start_line > end_line:
            raise ValueError(
                f"Invalid line range {start_line}-{end_line} for file with {len(lines)} lines"
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


async def analyze_file(
    ctx: AnyContext, path: str, query: str, token_limit: int = 40000
) -> str:
    """Analyze file using LLM capability to reduce context usage.
    Use this tool for:
    - summarization
    - outline/structure extraction
    - code review
    - other tasks
    Args:
        path (str): File path to be analyze. Pass exactly as provided, including '~'.
        query(str): Instruction to analyze the file
        token_limit(Optional[int]): Max token length to be taken from file
    Returns:
        str: The analysis result
    Raises:
        Exception: If an error occurs.
    """
    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"File not found: {path}")
    file_content = read_file(abs_path)
    _analyze_file = create_sub_agent_tool(
        tool_name="analyze_file",
        tool_description="analyze file with LLM capability",
        system_prompt=_EXTRACT_INFO_FROM_FILE_SYSTEM_PROMPT,
        tools=[read_from_file, search_files],
    )
    payload = json.dumps(
        {"instruction": query, "file_path": abs_path, "file_content": file_content}
    )
    clipped_payload = llm_rate_limitter.clip_prompt(payload, token_limit)
    return await _analyze_file(ctx, clipped_payload)


def read_many_files(paths: List[str]) -> str:
    """
    Read and return the content of multiple files.

    This function is ideal for when you need to inspect the contents of
    several files at once. For each file path provided in the input list,
    it reads the entire file content. The result is a JSON string
    containing a dictionary where keys are the file paths and values are
    the corresponding file contents.

    Use this tool when you need a comprehensive view of multiple files,
    for example, to understand how different parts of a module interact,
    to check configurations across various files, or to gather context
    before making widespread changes.

    Args:
        paths (List[str]): A list of absolute or relative paths to the
                           files you want to read. It is crucial to
                           provide accurate paths. Use the `list_files`
                           tool if you are unsure about the exact file
                           locations.

    Returns:
        str: A JSON string representing a dictionary where each key is a
             file path and the corresponding value is the content of that
             file. If a file cannot be read, its entry in the dictionary
             will contain an error message.
             Example:
             {
                 "results": {
                     "path/to/file1.py": "...",
                     "path/to/file2.txt": "..."
                 }
             }
    """
    results = {}
    for path in paths:
        try:
            abs_path = os.path.abspath(os.path.expanduser(path))
            if not os.path.exists(abs_path):
                raise FileNotFoundError(f"File not found: {path}")
            content = read_file_with_line_numbers(abs_path)
            results[path] = content
        except Exception as e:
            results[path] = f"Error reading file: {e}"
    return json.dumps({"results": results})


def write_many_files(files: Dict[str, str]) -> str:
    """
    Write content to multiple files simultaneously.

    This function allows you to create, overwrite, or update multiple
    files in a single operation. You provide a dictionary where each
    key is a file path and the corresponding value is the content to be
    written to that file. This is particularly useful for applying
    changes across a project, such as refactoring code, updating
    configuration files, or creating a set of new files from a template.

    Each file is handled as a complete replacement of its content. If the
    file does not exist, it will be created. If it already exists, its

    entire content will be overwritten with the new content you provide.
    Therefore, it is essential to provide the full, intended content for
    each file.

    Args:
        files (Dict[str, str]): A dictionary where keys are the file paths
                                (absolute or relative) and values are the
                                complete contents to be written to those
                                files.

    Returns:
        str: A JSON string summarizing the operation. It includes a list
             of successfully written files and a list of files that
             failed, along with the corresponding error messages.
             Example:
             {
                 "success": [
                     "path/to/file1.py",
                     "path/to/file2.txt"
                 ],
                 "errors": {
                     "path/to/problematic/file.py": "Error message"
                 }
             }
    """
    success = []
    errors = {}
    for path, content in files.items():
        try:
            abs_path = os.path.abspath(os.path.expanduser(path))
            directory = os.path.dirname(abs_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
            write_file(abs_path, content)
            success.append(path)
        except Exception as e:
            errors[path] = f"Error writing file: {e}"
    return json.dumps({"success": success, "errors": errors})
