import os
import shutil


def remove_file(path: str, recursive: bool = False) -> str:
    """
    Removes a file or directory. Irreversible — there is no trash; the bytes are gone.

    `recursive=False` (default): removes a file or an empty directory only.
    `recursive=True`: removes a directory and all its contents.

    Before calling, confirm the path is the one the user intended (typo-check, absolute path).
    """
    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        return f"Error: Path not found: {path}"
    if os.path.isdir(abs_path):
        if recursive:
            try:
                shutil.rmtree(abs_path)
                return f"Removed directory recursively: {path}"
            except Exception as e:
                return f"Error removing directory {path}: {e}"
        try:
            os.rmdir(abs_path)
            return f"Removed empty directory: {path}"
        except OSError:
            return (
                f"Error: {path} is a non-empty directory. "
                "Pass recursive=True to remove it and all its contents (irreversible)."
            )
    try:
        os.remove(abs_path)
        return f"Removed: {path}"
    except Exception as e:
        return f"Error removing {path}: {e}"
