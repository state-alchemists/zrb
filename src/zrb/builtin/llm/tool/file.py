import os

from zrb.util.file import read_file, write_file


def list_file(
    directory: str = ".",
    extensions: list[str] = [".py", ".go", ".js", ".ts", ".java", ".c", ".cpp"],
) -> list[str]:
    """List all files in a directory"""
    all_files: list[str] = []
    for root, _, files in os.walk(directory):
        for filename in files:
            for extension in extensions:
                if filename.lower().endswith(extension):
                    all_files.append(os.path.join(root, filename))
    return all_files


def read_text_file(file: str) -> str:
    """Read a text file"""
    return read_file(os.path.abspath(file))


def write_text_file(file: str, content: str):
    """Write a text file"""
    return write_file(os.path.abspath(file), content)


def read_source_code(
    directory: str = ".",
    extensions: list[str] = [".py", ".go", ".js", ".ts", ".java", ".c", ".cpp"],
) -> list[str]:
    """Read source code in a directory"""
    files = list_file(directory, extensions)
    for index, file in enumerate(files):
        content = read_text_file(file)
        files[index] = f"# {file}\n```\n{content}\n```"
    return files
