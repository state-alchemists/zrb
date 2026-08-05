import os

from zrb.llm.tool.command_repetition import bump_workspace_revision
from zrb.llm.tool.file_freshness import (
    clear_edit_streak,
    is_file_fresh,
    mark_file_fresh,
    mark_file_stale,
    refuse_stale_write,
)
from zrb.llm.tool.post_write_check import format_post_write_diagnostics


async def write_file(path: str, content: str, mode: str = "w") -> str:
    """
    Writes or appends to a file, creating it and any missing parent directories.

    For large content, write in chunks: first with mode="w", subsequent with mode="a".
    On success, runs LSP/static checks — errors appear as `[DIAGNOSTIC]` in the return value.

    Overwriting an existing file requires having `Read` it since it last
    changed — this replaces every byte, and a write built from a stale memory
    of the file silently reverts whatever happened in between. Appending
    (mode="a") and creating a new file are unaffected.
    """
    # Anything that is not an append replaces the whole file, so it is gated.
    # Matched on the prefix rather than on ``== "w"``: "wt" and "w+" truncate
    # just as thoroughly, and an equality check let them through ungated.
    appending = mode.startswith("a")
    if not appending:
        refusal = refuse_stale_write(path)
        if refusal:
            return refusal
    abs_path = os.path.abspath(os.path.expanduser(path))
    # An append is the one mode that can leave content the model has not seen in
    # place, so whether it ends up holding a full view depends on what was there
    # first. Sampled before the write, which is about to invalidate both facts.
    leaves_unseen_content = (
        appending and os.path.isfile(abs_path) and not is_file_fresh(path)
    )
    parent = os.path.dirname(abs_path)
    # Sampled before makedirs. Creating a directory is a change to the user's
    # tree, and a silent one reads as "the path already existed" — which is how a
    # path resolved against the wrong base lands a file where nothing reads it.
    # Reported, not refused: writing a new tree is often exactly the intent.
    created_dir = bool(parent) and not os.path.isdir(parent)
    try:
        os.makedirs(parent, exist_ok=True)
        with open(abs_path, mode, encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        return (
            f"Error writing to file {path}: {e}. "
            "[SYSTEM SUGGESTION]: Check that the parent path is a directory (not a "
            "file), that you have write permission, and that there is free disk "
            "space, then retry."
        )

    # A whole-file write, or the creation of a new file in any mode, means the
    # model authored every byte — its memory *is* the file until something
    # changes it out from under that view.
    #
    # An append to a file that already existed does not. It leaves whatever was
    # there in place, and only extends the model's view if that view was current
    # to begin with. Marking it fresh unconditionally opened a one-step bypass
    # of the whole guard: `mode="a"` with empty content against an unread file
    # granted freshness, and the very next `mode="w"` was then free to discard
    # content the model had never seen.
    if leaves_unseen_content:
        mark_file_stale(path)
    else:
        mark_file_fresh(path)
    bump_workspace_revision()
    clear_edit_streak(path)
    dir_note = f" (created new directory {parent})" if created_dir else ""
    suffix = await format_post_write_diagnostics(abs_path)
    return f"Successfully wrote to {path}{dir_note}{suffix}"
