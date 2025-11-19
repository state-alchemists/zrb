import fnmatch
import json
import os
import re
import sys
from typing import Any, Optional

from zrb.builtin.llm.tool.sub_agent import create_sub_agent_tool
from zrb.config.config import CFG
from zrb.config.llm_rate_limitter import llm_rate_limitter
from zrb.context.any_context import AnyContext
from zrb.util.file import read_file, read_file_with_line_numbers, write_file

if sys.version_info >= (3, 12):
    from typing import TypedDict
else:
    from typing_extensions import TypedDict


class FileToRead(TypedDict):
    """
    Configuration for reading a file or file section.

    Attributes:
        path (str): Absolute or relative path to the file
        start_line (int | None): Starting line number (1-based, inclusive). If None, reads from beginning.
        end_line (int | None): Ending line number (1-based, exclusive). If None, reads to end.
    """

    path: str
    start_line: int | None
    end_line: int | None


class FileToWrite(TypedDict):
    """
    Configuration for writing content to a file.

    Attributes:
        path (str): Absolute or relative path where file will be written
        content (str): Content to write to the file (overwrites existing content)
    """

    path: str
    content: str


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
    Lists files and directories within a specified path, providing a map of the filesystem.

    Use this tool to explore and understand the directory structure of the project. It's essential for finding files before reading or modifying them. If you receive an error about a file not being found, use this tool to verify the correct path.

    Args:
        path (str): The directory path to list. Defaults to current directory.
        recursive (bool): Whether to list files recursively. Defaults to True.
        include_hidden (bool): Whether to include hidden files (starting with '.'). Defaults to False.
        excluded_patterns (Optional[list[str]]): List of glob patterns to exclude. Uses sensible defaults if None.

    Returns:
        dict[str, list[str]]: A dictionary with key 'files' containing sorted list of relative file paths.

    Examples:
        - List all files in current directory: `list_files()`
        - List files in specific directory: `list_files("src/")`
        - List non-recursively: `list_files(recursive=False)`
        - Include hidden files: `list_files(include_hidden=True)`
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
) -> str | dict[str, Any]:
    """
    Reads the content of one or more files.

    Use this tool to inspect the contents of specific files. You can read the entire file(s) or specify a range of lines for single file reading. The content returned will include line numbers, which are useful for other tools like `replace_in_file`.

    Args:
        file (FileToRead | list[FileToRead]): Single file config or list of file configs.
            Each FileToRead should have:
            - path (str): File path to read
            - start_line (int | None): Starting line number (1-based, inclusive). If None, reads from beginning.
            - end_line (int | None): Ending line number (1-based, exclusive). If None, reads to end.

    Returns:
        str | dict[str, Any]:
            - For single file: String with file content including line numbers
            - For multiple files: Dictionary mapping file paths to file info including content

    Examples:
        - Read entire file: `read_from_file({"path": "file.txt"})`
        - Read specific lines: `read_from_file({"path": "file.txt", "start_line": 10, "end_line": 20})`
        - Read multiple files: `read_from_file([{"path": "file1.txt"}, {"path": "file2.txt"}])`

    Note:
        - Line numbers are 1-based (first line is line 1)
        - Content includes line numbers for easy reference
        - Use this before `replace_in_file` to get exact text blocks for replacement
    """
    # Handle single file input
    if not isinstance(file, list):
        file_config = file
        path = file_config["path"]
        start_line = file_config.get("start_line")
        end_line = file_config.get("end_line")
        try:
            abs_path = os.path.abspath(os.path.expanduser(path))
            if not os.path.exists(abs_path):
                raise FileNotFoundError(f"File not found: {path}")
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
            return content_result
        except Exception as e:
            raise RuntimeError(f"Error reading file {path}: {e}")

    # Handle list of files input
    results = {}
    for file_config in file:
        path = file_config["path"]
        start_line = file_config.get("start_line")
        end_line = file_config.get("end_line")
        try:
            abs_path = os.path.abspath(os.path.expanduser(path))
            if not os.path.exists(abs_path):
                raise FileNotFoundError(f"File not found: {path}")
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
            results[path] = {
                "path": path,
                "content": content_result,
                "start_line": start_idx + 1,  # Convert back to 1-based for output
                "end_line": end_idx,  # end_idx is already exclusive upper bound
                "total_lines": total_lines,
            }
        except Exception as e:
            results[path] = f"Error reading file: {e}"
    return results


def write_to_file(
    file: FileToWrite | list[FileToWrite],
) -> str | dict[str, Any]:
    """
    Writes content to one or more files, creating them or completely overwriting them.

    Use this tool to create new files or replace existing files' entire content.
    **WARNING:** This is a destructive operation and will overwrite files if they exist. Use `replace_in_file` for safer, targeted changes.

    Args:
        file (FileToWrite | list[FileToWrite]): Single file config or list of file configs.
            Each FileToWrite should have:
            - path (str): File path to write
            - content (str): Content to write to the file

    Returns:
        str | dict[str, Any]:
            - For single file: Success message string
            - For multiple files: Dictionary with 'success' and 'errors' keys

    Examples:
        - Write single file: `write_to_file({"path": "new_file.txt", "content": "Hello World"})`
        - Write multiple files: `write_to_file([{"path": "file1.txt", "content": "content1"}, {"path": "file2.txt", "content": "content2"}])`

    Important:
        - **DESTRUCTIVE OPERATION:** This completely overwrites existing files
        - Creates parent directories if they don't exist
        - For partial file modifications, use `replace_in_file` instead
        - Always verify file paths before writing
    """
    # Normalize to list
    files = file if isinstance(file, list) else [file]

    success = []
    errors = {}
    for file_config in files:
        path = file_config["path"]
        content = file_config["content"]
        try:
            abs_path = os.path.abspath(os.path.expanduser(path))
            directory = os.path.dirname(abs_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
            write_file(abs_path, content)
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
        return f"Successfully wrote to file: {file['path']}"


def search_files(
    path: str,
    regex: str,
    file_pattern: Optional[str] = None,
    include_hidden: bool = True,
) -> dict[str, Any]:
    """
    Searches for a regular expression (regex) pattern within files in a
    specified directory.

    This tool is invaluable for finding specific code, configuration, or text
    across multiple files. Use it to locate function definitions, variable
    assignments, error messages, or any other text pattern.

    Args:
        path (str): Directory path to search in
        regex (str): Regular expression pattern to search for
        file_pattern (Optional[str]): Glob pattern to filter files (e.g., "*.py", "*.md")
        include_hidden (bool): Whether to search hidden files. Defaults to True.

    Returns:
        dict[str, Any]: Search results with:
            - summary (str): Summary of search results
            - results (list): List of matches per file with context

    Examples:
        - Search for function: `search_files("src/", r"def my_function")`
        - Search in Python files: `search_files("src/", r"class.*:", file_pattern="*.py")`
        - Search with regex: `search_files(".", r"TODO|FIXME")`

    Note:
        - Returns matches with line numbers and surrounding context
        - Invalid regex patterns will raise ValueError
        - Searches recursively by default
        - File patterns use glob syntax (e.g., "*.py", "*.md")
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
    file_replacement: FileReplacement | list[FileReplacement],
) -> str | dict[str, Any]:
    """
    Replaces one or more strings in one or more files.

    This tool is for making targeted modifications to files. It is safer than `write_to_file` for small changes. First, use `read_from_file` to get the exact text block you want to change. Then, use that block as the `old_string`.

    Args:
        file_replacement (FileReplacement | list[FileReplacement]): Single or multiple file replacements.
            Each FileReplacement should have:
            - path (str): File path to modify
            - replacements (list[Replacement]): List of replacement operations
                Each Replacement should have:
                - old_string (str): Exact string to replace (must exist in file)
                - new_string (str): New string to replace with

    Returns:
        str | dict[str, Any]:
            - For single file: Success message string
            - For multiple files: Dictionary with 'success' and 'errors' keys

    Examples:
        - Single replacement: `replace_in_file({"path": "file.txt", "replacements": [{"old_string": "old text", "new_string": "new text"}]})`
        - Multiple replacements: `replace_in_file({"path": "file.txt", "replacements": [{"old_string": "text1", "new_string": "text1_new"}, {"old_string": "text2", "new_string": "text2_new"}]})`

    Important:
        - **CRITICAL:** `old_string` must exactly match content in file (including whitespace)
        - Always use `read_from_file` first to get exact text blocks
        - Only replaces first occurrence of each `old_string`
        - Returns error if `old_string` not found
        - No changes made if `old_string` equals `new_string`
    """
    # Normalize to list
    file_replacements = (
        file_replacement if isinstance(file_replacement, list) else [file_replacement]
    )
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
    if isinstance(file_replacement, list):
        return {"success": success, "errors": errors}
    else:
        if errors:
            raise RuntimeError(
                f"Error applying replacement to {file_replacement['path']}: {errors[file_replacement['path']]}"
            )
        return f"Successfully applied replacement(s) to {file_replacement['path']}"


async def analyze_file(
    ctx: AnyContext, path: str, query: str, token_limit: int | None = None
) -> dict[str, Any]:
    """
    Performs a high level, goal-oriented analysis of a single file using a sub-agent.

    This tool is ideal for complex questions about a single file that go beyond
    simple reading or searching. It uses a specialized sub-agent to analyze the
    file's content in relation to a specific query.

    Args:
        ctx (AnyContext): Execution context
        path (str): Path to the file to analyze
        query (str): Specific analysis query with clear guidelines
        token_limit (int | None): Maximum tokens for analysis. Uses default if None.

    Returns:
        dict[str, Any]: Analysis results from the sub-agent

    Examples:
        - Analyze code structure: `analyze_file(ctx, "src/main.py", "Analyze the main function structure and identify potential improvements")`
        - Review documentation: `analyze_file(ctx, "README.md", "Check if the documentation covers all major features and suggest improvements")`

    Important:
        - **QUERY QUALITY:** Provide clear, specific queries with guidelines
        - Vague queries result in poor analysis quality
        - Include analysis goals and expected output format in query
        - Uses sub-agent with access to `read_from_file` and `search_files` tools
        - File content is automatically clipped to token limit if needed
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
