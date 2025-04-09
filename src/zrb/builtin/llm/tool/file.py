import fnmatch
import json
import os
import re
from typing import Any, Dict, List, Optional

from zrb.util.file import read_file as _read_file
from zrb.util.file import write_file as _write_file


def list_files(
    path: str = ".", recursive: bool = True, include_hidden: bool = False
) -> str:
    """
    Request to list files and directories within the specified directory.
    If recursive is true, it will list all files and directories recursively.
    If recursive is false or not provided, it will only list the top-level contents.
    Args:
        path: (required) The path of the directory to list contents for (relative to the CWD)
        recursive: (optional) Whether to list files recursively.
            Use true for recursive listing, false or omit for top-level only.
        include_hidden: (optional) Whether to include hidden files/directories.
            Defaults to False (exclude hidden files).
    Returns:
        A JSON string containing a list of file paths or an error message.
        Example success: '{"files": ["file1.txt", "subdir/file2.py"]}'
        Example error: '{"error": "Error listing files: [Errno 2] No such file..."}'
    """
    all_files: List[str] = []
    abs_path = os.path.abspath(path)
    try:
        if recursive:
            for root, dirs, files in os.walk(abs_path):
                # Skip hidden directories (like .git) for performance and relevance
                dirs[:] = [d for d in dirs if include_hidden or not _is_hidden(d)]
                for filename in files:
                    # Skip hidden files
                    if include_hidden or not _is_hidden(filename):
                        all_files.append(os.path.join(root, filename))
        else:
            # Non-recursive listing (top-level only)
            for item in os.listdir(abs_path):
                full_path = os.path.join(abs_path, item)
                # Include both files and directories if not recursive
                if include_hidden or not _is_hidden(
                    item
                ):  # Skip hidden items unless included
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
    except Exception as e:
        raise Exception(f"Error listing files in {path}: {e}")


def _is_hidden(path: str) -> bool:
    """Check if path is hidden (starts with '.')."""
    return os.path.basename(path).startswith(".")


def read_from_file(
    path: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
) -> str:
    """
    Request to read the contents of a file at the specified path. Use this when you need
    to examine the contents of an existing file you do not know the contents of, for example
    to analyze code, review text files, or extract information from configuration files.
    The output includes line numbers prefixed to each line (e.g. "1 | const x = 1"),
    making it easier to reference specific lines when creating diffs or discussing code.
    By specifying start_line and end_line parameters, you can efficiently read specific
    portions of large files without loading the entire file into memory. Automatically
    extracts raw text from PDF and DOCX files. May not be suitable for other types of
    binary files, as it returns the raw content as a string.
    Args:
        path: (required) The path of the file to read (relative to the CWD)
        start_line: (optional) The starting line number to read from (1-based).
            If not provided, it starts from the beginning of the file.
        end_line: (optional) The ending line number to read to (1-based, inclusive).
            If not provided, it reads to the end of the file.
    Returns:
        A JSON string containing the file path, content, and line range, or an error.
        Example success: '{"path": "f.py", "content": "...", "start_line": 1, "end_line": 2}'
        Example error: '{"error": "File not found: data.txt"}'
    """
    try:
        abs_path = os.path.abspath(path)
        # Check if file exists
        if not os.path.exists(abs_path):
            return json.dumps({"error": f"File {path} does not exist"})
        content = _read_file(abs_path)
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
    except Exception as e:
        raise Exception(f"Error reading file {path}: {e}")


def write_to_file(path: str, content: str, line_count: int) -> str:
    """
    Request to write full content to a file at the specified path. If the file exists,
    it will be overwritten with the provided content. If the file doesn't exist,
    it will be created. This tool will automatically create any directories needed
    to write the file.
    Args:
        path: (required) The path of the file to write to (relative to the CWD)
        content: (required) The content to write to the file. ALWAYS provide the COMPLETE
            intended content of the file, without any truncation or omissions. You MUST
            include ALL parts of the file, even if they haven't been modified. Do NOT
            include the line numbers in the content though, just the actual content
            of the file.
        line_count: (required) The number of lines in the file. Make sure to compute
            this based on the actual content of the file, not the number of lines
            in the content you're providing.
    Returns:
        A JSON string indicating success or failure, including any warnings.
        Example success: '{"success": true, "path": "new_config.json"}'
        Example success with warning: '{"success": true, "path": "f.txt", "warning": "..."}'
        Example error: '{"success": false, "error": "Permission denied: /etc/hosts"}'
    """
    actual_lines = len(content.splitlines())
    warning = None
    if actual_lines != line_count:
        warning = (
            f"Provided line_count ({line_count}) does not match actual "
            f"content lines ({actual_lines}) for file {path}"
        )
    try:
        abs_path = os.path.abspath(path)
        # Ensure directory exists
        directory = os.path.dirname(abs_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        _write_file(abs_path, content)
        result_data = {"success": True, "path": path}
        if warning:
            result_data["warning"] = warning
        return json.dumps(result_data)
    except Exception as e:
        raise Exception(f"Error writing file {e}")


def search_files(
    path: str,
    regex: str,
    file_pattern: Optional[str] = None,
    include_hidden: bool = False,
) -> str:
    """
    Request to perform a regex search across files in a specified directory,
    providing context-rich results. This tool searches for patterns or specific
    content across multiple files, displaying each match with encapsulating context.
    Args:
        path: (required) The path of the directory to search in (relative to the CWD).
              This directory will be recursively searched.
        regex: (required) The regular expression pattern to search for. Uses Rust regex syntax.
               (Note: Python's `re` module will be used here, which has similar syntax)
        file_pattern: (optional) Glob pattern to filter files (e.g., '*.ts').
                      If not provided, searches all files (*).
        include_hidden: (optional) Whether to include hidden files.
                      Defaults to False (exclude hidden files).
    Returns:
        A JSON string containing the search results or an error message.
        Example success: '{"summary": "Found 5 matches...", "results": [{"file":"f.py", ...}]}'
        Example no match: '{"summary": "No matches found...", "results": []}'
        Example error: '{"error": "Invalid regex: ..."}'
    """
    try:
        pattern = re.compile(regex)
    except re.error as e:
        raise Exception(f"Invalid regex pattern: {e}")
    search_results = {"summary": "", "results": []}
    match_count = 0
    searched_file_count = 0
    file_match_count = 0
    try:
        abs_path = os.path.abspath(path)
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
        return json.dumps(search_results, indent=2)  # Pretty print for readability
    except Exception as e:
        raise Exception(f"Error searching files: {e}")


def _get_file_matches(
    file_path: str, pattern: re.Pattern, context_lines: int = 2
) -> List[Dict[str, Any]]:
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
    except Exception as e:
        raise IOError(f"Error reading {file_path}: {str(e)}")


def apply_diff(path: str, diff: str) -> str:
    """
    Request to replace existing code using a search and replace block.
    This tool allows for precise, surgical replaces to files by specifying exactly
    what content to search for and what to replace it with.
    The tool will maintain proper indentation and formatting while making changes.
    Only a single operation is allowed per tool use.
    The SEARCH section must exactly match existing content including whitespace
    and indentation.
    If you're not confident in the exact content to search for, use the read_file tool
    first to get the exact content.
    Args:
        path: (required) The path of the file to modify (relative to the CWD)
        diff: (required) The search/replace block defining the changes.
              Format:
              <<<<<<< SEARCH
              :start_line:START_LINE_NUMBER
              :end_line:END_LINE_NUMBER
              -------
              [exact content to find including whitespace]
              =======
              [new content to replace with]
              >>>>>>> REPLACE
    Returns:
        A JSON string indicating success or failure.
    """
    try:
        start_line, end_line, search_content, replace_content = _parse_diff(diff)
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            return json.dumps(
                {"success": False, "path": path, "error": f"File not found at {path}"}
            )
        content = _read_file(abs_path)
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
        _write_file(abs_path, new_content)
        return json.dumps({"success": True, "path": path})
    except Exception as e:
        raise Exception(f"Error applying diff on {path}: {e}")


def _parse_diff(diff: str) -> tuple[int, int, str, str]:
    """Parse diff content into components."""
    search_marker = "<<<<<<< SEARCH"
    meta_marker = "-------"
    separator = "======="
    replace_marker = ">>>>>>> REPLACE"
    search_start_idx = diff.find(search_marker)
    meta_start_idx = diff.find(meta_marker)
    separator_idx = diff.find(separator)
    replace_end_idx = diff.find(replace_marker)
    if any(
        idx == -1
        for idx in [search_start_idx, meta_start_idx, separator_idx, replace_end_idx]
    ):
        raise ValueError("Invalid diff format - missing markers")
    meta_content = diff[search_start_idx + len(search_marker) : meta_start_idx].strip()
    start_line = int(re.search(r":start_line:(\d+)", meta_content).group(1))
    end_line = int(re.search(r":end_line:(\d+)", meta_content).group(1))
    search_content = diff[meta_start_idx + len(meta_marker) : separator_idx].strip(
        "\r\n"
    )
    replace_content = diff[separator_idx + len(separator) : replace_end_idx].strip(
        "\r\n"
    )
    return start_line, end_line, search_content, replace_content
