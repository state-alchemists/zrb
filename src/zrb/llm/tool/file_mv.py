import os
import shutil


def move_file(src: str, dst: str) -> str:
    """
    Moves or renames a file or directory. Creates missing parent directories at the destination.

    Overwrites the destination if it already exists. Before calling on a rename,
    confirm the destination is free (e.g., with LS) unless overwrite is intended.
    """
    abs_src = os.path.abspath(os.path.expanduser(src))
    abs_dst = os.path.abspath(os.path.expanduser(dst))
    if not os.path.exists(abs_src):
        return f"Error: Source not found: {src}"
    try:
        os.makedirs(os.path.dirname(abs_dst), exist_ok=True)
        shutil.move(abs_src, abs_dst)
        return f"Moved: {src} -> {dst}"
    except Exception as e:
        return f"Error moving {src} to {dst}: {e}"
