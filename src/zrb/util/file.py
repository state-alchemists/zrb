import os
import re


def read_file(file_path: str, replace_map: dict[str, str] = {}) -> str:
    """Reads a file and optionally replaces content based on a map.

    Args:
        file_path: The path to the file.
        replace_map: A dictionary of strings to replace.

    Returns:
        The content of the file with replacements applied.
    """
    with open(
        os.path.abspath(os.path.expanduser(file_path)), "r", encoding="utf-8"
    ) as f:
        content = f.read()
    for key, val in replace_map.items():
        content = content.replace(key, val)
    return content


def read_file_with_line_numbers(
    file_path: str, replace_map: dict[str, str] = {}
) -> str:
    """Reads a file and returns content with line numbers.

    Args:
        file_path: The path to the file.
        replace_map: A dictionary of strings to replace.

    Returns:
        The content of the file with line numbers and replacements applied.
    """
    content = read_file(file_path, replace_map)
    lines = content.splitlines()
    numbered_lines = [f"{i + 1} | {line}" for i, line in enumerate(lines)]
    return "\n".join(numbered_lines)


def read_dir(dir_path: str) -> list[str]:
    """Reads a directory and returns a list of file names.

    Args:
        dir_path: The path to the directory.

    Returns:
        A list of file names in the directory.
    """
    return [f for f in os.listdir(os.path.abspath(os.path.expanduser(dir_path)))]


def write_file(file_path: str, content: str | list[str]):
    """Writes content to a file.

    Args:
        file_path: The path to the file.
        content: The content to write, either a string or a list of strings.
    """
    if isinstance(content, list):
        content = "\n".join([line for line in content if line is not None])
    dir_path = os.path.dirname(file_path)
    os.makedirs(dir_path, exist_ok=True)
    should_add_eol = content.endswith("\n")
    # Remove trailing newlines, but keep one if the file originally ended up with newline
    content = re.sub(r"\n{3,}$", "\n\n", content)
    content = content.rstrip("\n")
    if should_add_eol:
        content += "\n"
    with open(os.path.abspath(os.path.expanduser(file_path)), "w") as f:
        f.write(content)
