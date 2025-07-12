import fnmatch
import json
import os
import re
from typing import Any, Dict, List, Optional

from zrb.builtin.llm.tool.sub_agent import create_sub_agent_tool
from zrb.config.config import CFG
from zrb.config.llm_rate_limitter import llm_rate_limitter
from zrb.context.any_context import AnyContext
from zrb.util.file import read_file, read_file_with_line_numbers, write_file

_EXTRACT_INFO_FROM_FILE_SYSTEM_PROMPT = CFG.LLM_ANALYZE_FILE_EXTRACTOR_SYSTEM_PROMPT


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
    """
    Lists the files and directories within a specified path.

    This is a fundamental tool for exploring the file system. Use it to discover the structure of a directory, find specific files, or get a general overview of the project layout before performing other operations.

    Args:
        path (str, optional): The directory path to list. Defaults to the current directory (".").
        recursive (bool, optional): If True, lists files and directories recursively. If False, lists only the top-level contents. Defaults to True.
        include_hidden (bool, optional): If True, includes hidden files and directories (those starting with a dot). Defaults to False.
        excluded_patterns (list[str], optional): A list of glob patterns to exclude from the listing. This is useful for ignoring irrelevant files like build artifacts or virtual environments. Defaults to a standard list of common exclusion patterns.

    Returns:
        str: A JSON string containing a list of file and directory paths relative to the input path.
             Example: '{"files": ["src/main.py", "README.md"]}'
    Raises:
        FileNotFoundError: If the specified path does not exist.
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
    """
    Reads the content of a file, optionally from a specific start line to an end line.

    This tool is essential for inspecting file contents. It can read both text and PDF files. The returned content is prefixed with line numbers, which is crucial for providing context when you need to modify the file later with the `apply_diff` tool.

    Use this tool to:
    - Examine the source code of a file.
    - Read configuration files.
    - Check the contents of a document.

    Args:
        path (str): The path to the file to read.
        start_line (int, optional): The 1-based line number to start reading from. If omitted, reading starts from the beginning of the file.
        end_line (int, optional): The 1-based line number to stop reading at (inclusive). If omitted, reads to the end of the file.

    Returns:
        str: A JSON object containing the file path, the requested content with line numbers, the start and end lines, and the total number of lines in the file.
             Example: '{"path": "src/main.py", "content": "1: import os\n2: \n3: print(\"Hello, World!\")", "start_line": 1, "end_line": 3, "total_lines": 3}'
    Raises:
        FileNotFoundError: If the specified file does not exist.
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
) -> str:
    """
    Writes content to a file, completely overwriting it if it exists or creating it if it doesn't.

    Use this tool to create new files or to replace the entire content of existing files. This is a destructive operation, so be certain of your actions. Always read the file first to understand its contents before overwriting it, unless you are creating a new file.

    Args:
        path (str): The path to the file to write to.
        content (str): The full, complete content to be written to the file. Do not use partial content or omit any lines.

    Returns:
        str: A JSON object indicating success or failure.
             Example: '{"success": true, "path": "new_file.txt"}'
    """
    try:
        abs_path = os.path.abspath(os.path.expanduser(path))
        # Ensure directory exists
        directory = os.path.dirname(abs_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        write_file(abs_path, content)
        result_data = {"success": True, "path": path}
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
    """
    Searches for a regular expression (regex) pattern within files in a specified directory.

    This tool is invaluable for finding specific code, configuration, or text across multiple files. Use it to locate function definitions, variable assignments, error messages, or any other text pattern.

    Args:
        path (str): The directory path to start the search from.
        regex (str): The Python-compatible regular expression pattern to search for.
        file_pattern (str, optional): A glob pattern to filter which files get searched (e.g., "*.py", "*.md"). If omitted, all files are searched.
        include_hidden (bool, optional): If True, the search will include hidden files and directories. Defaults to True.

    Returns:
        str: A JSON object containing a summary of the search and a list of results. Each result includes the file path and a list of matches, with each match showing the line number, line content, and a few lines of context from before and after the match.
    Raises:
        ValueError: If the provided `regex` pattern is invalid.
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


def replace_in_file(
    path: str,
    old_string: str,
    new_string: str,
) -> str:
    """
    Replaces the first occurrence of a string in a file.

    This tool is for making targeted modifications to a file. It is a single-step operation that is generally safer and more ergonomic than `write_to_file` for small changes.

    To ensure the replacement is applied correctly and to avoid ambiguity, the `old_string` parameter should be a unique, multi-line string that includes context from before and after the code you want to change.

    Args:
        path (str): The path of the file to modify.
        old_string (str): The exact, verbatim string to search for and replace. This should be a unique, multi-line block of text.
        new_string (str): The new string that will replace the `old_string`.

    Returns:
        str: A JSON object indicating the success or failure of the operation.
    Raises:
        FileNotFoundError: If the specified file does not exist.
        ValueError: If the `old_string` is not found in the file.
    """
    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"File not found: {path}")
    try:
        content = read_file(abs_path)
        if old_string not in content:
            raise ValueError(f"old_string not found in file: {path}")
        new_content = content.replace(old_string, new_string, 1)
        write_file(abs_path, new_content)
        return json.dumps({"success": True, "path": path})
    except ValueError as e:
        raise e
    except (OSError, IOError) as e:
        raise OSError(f"Error applying replacement to {path}: {e}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error applying replacement to {path}: {e}")


async def analyze_file(
    ctx: AnyContext, path: str, query: str, token_limit: int | None = None
) -> str:
    """
    Performs a deep, goal-oriented analysis of a single file using a sub-agent.

    This tool is ideal for complex questions about a single file that go beyond simple reading or searching. It uses a specialized sub-agent to analyze the file's content in relation to a specific query.

    Use this tool to:
    - Summarize the purpose and functionality of a script or configuration file.
    - Extract the structure of a file (e.g., "List all the function names in this Python file").
    - Perform a detailed code review of a specific file.
    - Answer complex questions like, "How is the 'User' class used in this file?".

    Args:
        path (str): The path to the file to be analyzed.
        query (str): A clear and specific question or instruction about what to analyze in the file.
        token_limit (int, optional): The maximum token length of the file content to be passed to the analysis sub-agent.

    Returns:
        str: A detailed, markdown-formatted analysis of the file, tailored to the specified query.
    Raises:
        FileNotFoundError: If the specified file does not exist.
    """
    if token_limit is None:
        token_limit = CFG.LLM_FILE_ANALYSIS_TOKEN_LIMIT
    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"File not found: {path}")
    file_content = read_file(abs_path)
    _analyze_file = create_sub_agent_tool(
        tool_name="analyze_file",
        tool_description="analyze file with LLM capability",
        system_prompt=CFG.LLM_ANALYZE_FILE_EXTRACTOR_SYSTEM_PROMPT,
        tools=[read_from_file, search_files],
    )
    payload = json.dumps(
        {"instruction": query, "file_path": abs_path, "file_content": file_content}
    )
    clipped_payload = llm_rate_limitter.clip_prompt(payload, token_limit)
    return await _analyze_file(ctx, clipped_payload)


def read_many_files(paths: List[str]) -> str:
    """
    Reads and returns the full content of multiple files at once.

    This tool is highly efficient for gathering context from several files simultaneously. Use it when you need to understand how different files in a project relate to each other, or when you need to inspect a set of related configuration or source code files.

    Args:
        paths (List[str]): A list of paths to the files you want to read. It is crucial to provide accurate paths. Use the `list_files` tool first if you are unsure about the exact file locations.

    Returns:
        str: A JSON object where keys are the file paths and values are their corresponding contents, prefixed with line numbers. If a file cannot be read, its value will be an error message.
             Example: '{"results": {"src/api.py": "1: import ...", "config.yaml": "1: key: value"}}'
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
    Writes content to multiple files in a single, atomic operation.

    This tool is for applying widespread changes to a project, such as creating a set of new files from a template, updating multiple configuration files, or performing a large-scale refactoring.

    Each file's content is completely replaced. If a file does not exist, it will be created. If it exists, its current content will be entirely overwritten. Therefore, you must provide the full, intended content for each file.

    Args:
        files (Dict[str, str]): A dictionary where keys are the file paths and values are the complete contents to be written to those files.

    Returns:
        str: A JSON object summarizing the operation, listing successfully written files and any files that failed, along with corresponding error messages.
             Example: '{"success": ["file1.py", "file2.txt"], "errors": {}}'
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


apply_diff = replace_in_file
