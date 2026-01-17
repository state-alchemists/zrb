import fnmatch
import os

DEFAULT_EXCLUDED_PATTERNS = [
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".Python",
    "build",
    "dist",
    ".env",
    ".venv",
    "env",
    "venv",
    ".idea",
    ".vscode",
    ".git",
    "node_modules",
    ".pytest_cache",
    ".coverage",
    "htmlcov",
]


def list_files(
    path: str = ".",
    include_hidden: bool = False,
    depth: int = 3,
    excluded_patterns: list[str] | None = None,
) -> dict[str, list[str]]:
    """
    Lists files recursively up to a specified depth.
    Use this to explore directory structure.
    """
    all_files: list[str] = []
    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Path does not exist: {path}")

    patterns_to_exclude = (
        excluded_patterns
        if excluded_patterns is not None
        else DEFAULT_EXCLUDED_PATTERNS
    )
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
    return {"files": sorted(all_files)}


def read_file(path: str) -> str:
    """Reads the entire content of a file."""
    abs_path = os.path.abspath(os.path.expanduser(path))
    with open(abs_path, "r", encoding="utf-8") as f:
        return f.read()


def write_file(path: str, content: str, mode: str = "w") -> str:
    """Writes content to a file. Mode 'w' for overwrite, 'a' for append."""
    abs_path = os.path.abspath(os.path.expanduser(path))
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, mode, encoding="utf-8") as f:
        f.write(content)
    return f"Successfully wrote to {path}"


def replace_in_file(path: str, old_text: str, new_text: str) -> str:
    """Replaces exact text in a file."""
    abs_path = os.path.abspath(os.path.expanduser(path))
    with open(abs_path, "r", encoding="utf-8") as f:
        content = f.read()
    if old_text not in content:
        return f"Error: '{old_text}' not found in {path}"
    new_content = content.replace(old_text, new_text)
    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    return f"Successfully updated {path}"


def _is_excluded(name: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if fnmatch.fnmatch(name, pattern):
            return True
        parts = name.split(os.path.sep)
        for part in parts:
            if fnmatch.fnmatch(part, pattern):
                return True
    return False
