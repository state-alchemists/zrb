import os
import re
from typing import Optional, Tuple

from zrb.util.file import list_files, read_file


def expand_prompt(prompt: str) -> str:
    """
    Expands @reference patterns in the prompt into a Reference + Appendix style.
    Example: "Check @main.py" -> "Check main.py (see Appendix)\n...[Appendix with content]..."
    """
    if not prompt:
        return prompt

    matches = _get_path_references(prompt)
    if not matches:
        return prompt

    appendix_entries: list[str] = []
    # We construct the new string by slicing.
    last_idx = 0
    parts = []

    for match in matches:
        # Add text before match
        parts.append(prompt[last_idx : match.start()])

        path_ref = match.group("path")
        original_token = match.group(0)

        header, content, is_valid_ref = _process_path_reference(path_ref)

        if not is_valid_ref:
            # Fallback: leave original token if unreadable or not found
            parts.append(original_token)
            last_idx = match.end()
            continue

        # If we successfully got content
        parts.append(f"`{path_ref}` (see Appendix)")

        # Add to appendix with strict instructions
        appendix_entry = _create_appendix_entry(path_ref, header, content)
        appendix_entries.append(appendix_entry)

        last_idx = match.end()

    # Add remaining text
    parts.append(prompt[last_idx:])

    new_prompt = "".join(parts)

    if appendix_entries:
        appendix_header = _create_appendix_header()
        appendix_section = appendix_header + "\n\n".join(appendix_entries)
        new_prompt += appendix_section

    return new_prompt


def _get_path_references(prompt: str) -> list[re.Match]:
    """Find all @path references in the prompt.

    Args:
        prompt: The input prompt string

    Returns:
        List of regex match objects for @path references
    """
    if not prompt:
        return []

    # Regex to capture @path.
    # Matches @ followed by typical path chars.
    # We'll allow alphanumeric, _, -, ., /, \, and ~ (home dir).
    pattern = re.compile(r"@(?P<path>[\w~\-\./\\]+)")
    return list(pattern.finditer(prompt))


def _process_path_reference(path_ref: str) -> Tuple[Optional[str], Optional[str], bool]:
    """Process a single path reference.

    Args:
        path_ref: The path reference (without @ prefix)

    Returns:
        Tuple of (header, content, is_valid_ref)
        - header: Formatted header for the appendix entry
        - content: The content of the file or directory listing
        - is_valid_ref: Whether the path was successfully processed
    """
    # Check existence
    expanded_path = os.path.expanduser(path_ref)
    abs_path = os.path.abspath(expanded_path)

    content = ""
    header = ""
    is_valid_ref = False

    if os.path.isfile(abs_path):
        try:
            content = read_file(abs_path)
            header = f"File Content: `{path_ref}`"
            is_valid_ref = True
        except Exception:
            pass
    elif os.path.isdir(abs_path):
        try:
            # Use list_files for directory structure
            file_list = list_files(abs_path, depth=2)
            content = "\n".join(file_list)
            if not content:
                content = "(Empty directory)"
            header = f"Directory Listing: `{path_ref}`"
            is_valid_ref = True
        except Exception:
            pass

    return header, content, is_valid_ref


def _create_appendix_entry(path_ref: str, header: str, content: str) -> str:
    """Create an appendix entry for a path reference.

    Args:
        path_ref: The original path reference
        header: The formatted header
        content: The content to include

    Returns:
        Formatted appendix entry string
    """
    # Determine which tool to warn against based on path type
    expanded_path = os.path.expanduser(path_ref)
    abs_path = os.path.abspath(expanded_path)
    is_file = os.path.isfile(abs_path)
    warning_tool = "`read_file`" if is_file else "`list_files`"
    warning_message = f"> **DO NOT** use {warning_tool} to read this path again."

    entry_lines = [
        f"### {header}",
        f"> **SYSTEM NOTE:** The content of `{path_ref}` is provided below.",
        warning_message,
        "> Use the content provided here directly.\n",
        "```",
        f"{content}",
        "```",
    ]
    return "\n".join(entry_lines)


def _create_appendix_header() -> str:
    """Create the appendix section header.

    Returns:
        Formatted appendix header string
    """
    sep = "=" * 20
    header_lines = [
        f"\n\n{sep}APPENDIX: PRE-LOADED CONTEXT {sep}",
        "⚠️ **SYSTEM INSTRUCTION**: The user has attached the following content.",
        "You MUST use this provided content for your analysis.",
        "**DO NOT** consume resources by calling `read_file` or `list_files`",
        "or `run_shell_command` to read these specific paths again.\n",
    ]
    return "\n".join(header_lines)
