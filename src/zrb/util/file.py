import os
import re


def read_file(file_path: str, replace_map: dict[str, str] = {}) -> str:
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
    content = read_file(file_path, replace_map)
    lines = content.splitlines()
    numbered_lines = [f"{i + 1} | {line}" for i, line in enumerate(lines)]
    return "\n".join(numbered_lines)


def read_dir(dir_path: str) -> list[str]:
    return [f for f in os.listdir(os.path.abspath(os.path.expanduser(dir_path)))]


def write_file(file_path: str, content: str | list[str]):
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
