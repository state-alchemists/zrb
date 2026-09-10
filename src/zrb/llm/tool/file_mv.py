import os
import shutil
from typing import Annotated

from pydantic import Field

from zrb.llm.tool.file_observation import check_listed, record_seen


def move_file(
    src: Annotated[str, Field(description="Path of the file or directory to move.")],
    dst: Annotated[
        str,
        Field(
            description=(
                "Destination path. Missing parent directories are created; "
                "overwriting an existing destination is refused unless this "
                "session has Read it, or List/Glob'd its parent directory, "
                "first."
            )
        ),
    ],
) -> str:
    """
    Moves or renames a file or directory. See each parameter's own description
    for what happens at the destination.
    """
    abs_src = os.path.abspath(os.path.expanduser(src))
    abs_dst = os.path.abspath(os.path.expanduser(dst))
    if not os.path.exists(abs_src):
        return (
            f"Error: Source not found: {src}. "
            "[SYSTEM SUGGESTION]: Check the source path; use List to see what exists."
        )
    if os.path.exists(abs_dst):
        blocked = check_listed(abs_dst, recursive=False)
        if blocked is not None:
            return blocked
    try:
        os.makedirs(os.path.dirname(abs_dst), exist_ok=True)
        shutil.move(abs_src, abs_dst)
        record_seen(abs_dst)
        return f"Moved: {src} -> {dst}"
    except Exception as e:
        return (
            f"Error moving {src} to {dst}: {e}. "
            "[SYSTEM SUGGESTION]: Verify the destination parent is writable and the "
            "source is not in use, then retry."
        )
