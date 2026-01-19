import fnmatch
import os
import re
from typing import Literal


def read_file(file_path: str, replace_map: dict[str, str] = {}) -> str:
    """Reads a file and optionally replaces content based on a map.

    Args:
        file_path: The path to the file.
        replace_map: A dictionary of strings to replace.

    Returns:
        The content of the file with replacements applied.
    """
    abs_file_path = os.path.abspath(os.path.expanduser(file_path))
    is_pdf = abs_file_path.lower().endswith(".pdf")
    try:
        content = (
            _read_pdf_file_content(abs_file_path)
            if is_pdf
            else _read_text_file_content(abs_file_path)
        )
        for key, val in replace_map.items():
            content = content.replace(key, val)
        return content
    except Exception:
        import base64
        from pathlib import Path

        data = Path(abs_file_path).read_bytes()
        return base64.b64encode(data).decode("ascii")


def _read_text_file_content(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    return content


def _read_pdf_file_content(file_path: str) -> str:
    import pdfplumber
    from pdfplumber.pdf import PDF

    with pdfplumber.open(file_path) as pdf:
        pdf: PDF
        return "\n".join(
            page.extract_text() for page in pdf.pages if page.extract_text()
        )


def write_file(
    file_path: str,
    content: str | list[str],
    mode: Literal["w", "wt", "tw", "a", "at", "ta", "x", "xt", "tx"] = "w",
):
    """Writes content to a file.

    Args:
        file_path: The path to the file.
        content: The content to write, either a string or a list of strings.
        mode: Writing mode (by default "w")
    """
    if isinstance(content, list):
        content = "\n".join([line for line in content if line is not None])
    abs_file_path = os.path.abspath(os.path.expanduser(file_path))
    dir_path = os.path.dirname(abs_file_path)
    os.makedirs(dir_path, exist_ok=True)
    should_add_eol = content.endswith("\n")
    # Remove trailing newlines, but keep one if the file originally ended up with newline
    content = re.sub(r"\n{3,}$", "\n\n", content)
    content = content.rstrip("\n")
    if should_add_eol:
        content += "\n"
    with open(abs_file_path, mode) as f:
        f.write(content)


def list_files(
    path: str = ".",
    include_hidden: bool = False,
    depth: int = 3,
    excluded_patterns: list[str] = [],
) -> list[str]:
    all_files: list[str] = []
    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Path does not exist: {path}")

    patterns_to_exclude = excluded_patterns
    if depth <= 0:
        depth = 1

    initial_depth = abs_path.rstrip(os.sep).count(os.sep)
    for root, dirs, files in os.walk(abs_path, topdown=True):
        current_depth = root.rstrip(os.sep).count(os.sep) - initial_depth
        if current_depth >= depth - 1:
            del dirs[:]

        dirs[:] = [
            d
            for d in dirs
            if (include_hidden or not d.startswith("."))
            and not _is_excluded(d, patterns_to_exclude)
        ]

        for filename in files:
            if (include_hidden or not filename.startswith(".")) and not _is_excluded(
                filename, patterns_to_exclude
            ):
                full_path = os.path.join(root, filename)
                rel_full_path = os.path.relpath(full_path, abs_path)
                if not _is_excluded(rel_full_path, patterns_to_exclude):
                    all_files.append(rel_full_path)
    return sorted(all_files)


def _is_excluded(name: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if fnmatch.fnmatch(name, pattern):
            return True
        parts = name.split(os.path.sep)
        for part in parts:
            if fnmatch.fnmatch(part, pattern):
                return True
    return False
