import os
import re

from zrb.util.file import list_files, read_file


def expand_prompt(prompt: str) -> str:
    """
    Expands @reference patterns in the prompt into a Reference + Appendix style.
    Example: "Check @main.py" -> "Check main.py (see Appendix)\n...[Appendix with content]..."
    """
    if not prompt:
        return prompt

    # Regex to capture @path.
    # Matches @ followed by typical path chars.
    # We'll allow alphanumeric, _, -, ., /, \, and ~ (home dir).
    pattern = re.compile(r"@(?P<path>[\w~\-\./\\]+)")

    matches = list(pattern.finditer(prompt))
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

        if not is_valid_ref:
            # Fallback: leave original token if unreadable or not found
            parts.append(original_token)
            last_idx = match.end()
            continue

        # If we successfully got content
        parts.append(f"`{path_ref}` (see Appendix)")

        # Add to appendix with strict instructions
        entry_lines = [
            f"### {header}",
            f"> **SYSTEM NOTE:** The content of `{path_ref}` is provided below.",
            "> **DO NOT** use tools like `read_file` or `list_files` to read this path again.",
            "> Use the content provided here directly.\n",
            "```",
            f"{content}",
            "```",
        ]
        appendix_entries.append("\n".join(entry_lines))

        last_idx = match.end()

    # Add remaining text
    parts.append(prompt[last_idx:])

    new_prompt = "".join(parts)

    if appendix_entries:
        sep = "=" * 20
        header_lines = [
            f"\n\n{sep}APPENDIX: PRE-LOADED CONTEXT {sep}",
            "⚠️ **SYSTEM INSTRUCTION**: The user has attached the following content.",
            "You MUST use this provided content for your analysis.",
            "**DO NOT** consume resources by calling `read_file` or `list_files`",
            "or `run_shell_command` to read these specific paths again.\n",
        ]
        appendix_section = "\n".join(header_lines)
        appendix_section += "\n\n".join(appendix_entries)
        new_prompt += appendix_section

    return new_prompt
