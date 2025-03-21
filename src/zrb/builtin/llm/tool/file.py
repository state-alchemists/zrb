import os
import fnmatch

from zrb.util.file import read_file, write_file


def list_file(
    directory: str = ".",
    included_patterns: list[str] = [
        "*.py", "*.go", "*.js", "*.ts", "*.java", "*.c", "*.cpp"
    ],
    excluded_patterns: list[str] = [
        "venv", ".venv", "node_modules", ".git", "__pycache__"
    ],
) -> list[str]:
    """List all files in a directory that match any of the included glob patterns
    and do not reside in any directory matching an excluded pattern.
    Patterns are evaluated using glob-style matching.
    """
    all_files: list[str] = []
    for root, dirs, files in os.walk(directory):
        for filename in files:
            if any(fnmatch.fnmatch(filename, pat) for pat in included_patterns):
                full_path = os.path.join(root, filename)
                # Check each component of the full path for excluded patterns.
                if any(
                    any(fnmatch.fnmatch(part, pat) for pat in excluded_patterns)
                    for part in os.path.normpath(full_path).split(os.sep)
                ):
                    continue
                all_files.append(full_path)
    return all_files


def read_text_file(file: str) -> str:
    """Read a text file"""
    return read_file(os.path.abspath(file))


def write_text_file(file: str, content: str):
    """Write a text file"""
    return write_file(os.path.abspath(file), content)


def read_all(
    directory: str = ".",
    included_patterns: list[str] = ["*.py", "*.go", "*.js", "*.ts", "*.java", "*.c", "*.cpp"],
    excluded_patterns: list[str] = [],
) -> list[str]:
    """Read all files in a directory that match any of the included glob patterns
    and do not match any of the excluded glob patterns.
    Patterns are evaluated using glob-style matching.
    """
    files = list_file(directory, included_patterns, excluded_patterns)
    for index, file in enumerate(files):
        content = read_text_file(file)
        files[index] = f"# {file}\n```\n{content}\n```"
    return files
