import os
import shutil
from typing import Annotated

from pydantic import Field


def remove_file(
    path: Annotated[str, Field(description="Absolute or relative path to remove.")],
    recursive: Annotated[
        bool,
        Field(
            description=(
                "False (default) only removes a file or empty directory; True "
                "also removes a non-empty directory's contents — irreversible "
                "either way."
            )
        ),
    ] = False,
) -> str:
    """
    Removes a file or directory. Irreversible — there is no trash; the bytes are gone.

    `recursive=False` (default): removes a file or an empty directory only.
    `recursive=True`: removes a directory and all its contents.

    Before calling, confirm the path is the one the user intended (typo-check, absolute path).
    """
    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        return (
            f"Error: Path not found: {path}. "
            "[SYSTEM SUGGESTION]: Check the path; use List to see what exists "
            "in the directory."
        )
    if os.path.isdir(abs_path):
        if recursive:
            try:
                shutil.rmtree(abs_path)
                return f"Removed directory recursively: {path}"
            except Exception as e:
                return (
                    f"Error removing directory {path}: {e}. "
                    "[SYSTEM SUGGESTION]: Verify your permissions and that no process "
                    "is using the directory, then retry."
                )
        try:
            os.rmdir(abs_path)
            return f"Removed empty directory: {path}"
        except OSError:
            return (
                f"Error: {path} is a non-empty directory. "
                "[SYSTEM SUGGESTION]: Pass recursive=True to remove it and all its "
                "contents (irreversible)."
            )
    try:
        os.remove(abs_path)
        return f"Removed: {path}"
    except Exception as e:
        return (
            f"Error removing {path}: {e}. "
            "[SYSTEM SUGGESTION]: Verify your permissions and that the file is not "
            "in use, then retry."
        )
