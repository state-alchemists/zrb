"""Where a conversation's verbatim archive lives, and where its lock sits.

Both the summarizer (which writes an archive) and the history manager (which
collects one once no history refers to it) need these names, and the history
manager is the lower of the two — it owns the directory the archives sit in — so
the layout lives here rather than in the writer.
"""

from __future__ import annotations

import hashlib
import os

from zrb.config.config import CFG
from zrb.util.string.name import safe_segment

ARCHIVE_DIR_NAME = "verbatim"
"""Subdirectory of `LLM_HISTORY_DIR` holding the archives."""


def verbatim_archive_path(session_name: str, history_dir: str | None = None) -> str:
    """The archive file for *session_name*.

    `history_dir` is the directory the history manager stores conversations in,
    so the archive follows the same storage configuration; it defaults to
    `CFG.LLM_HISTORY_DIR` (``~/.zrb/llm-history``). The path is absolute: it is
    handed to the model, which reads what its working directory would otherwise
    make ambiguous.
    """
    base = os.path.expanduser(history_dir or CFG.LLM_HISTORY_DIR)
    return os.path.abspath(
        os.path.join(base, ARCHIVE_DIR_NAME, f"{safe_segment(session_name)}.md")
    )


def conversation_key(opening_text: str) -> str:
    """A stable archive name derived from a conversation's opening message.

    The fallback when the caller cannot name the conversation: a rename or a
    resume does not change it, and two conversations that open differently do
    not share a file. The readable prefix makes the file findable; the digest
    keeps two similar openings apart.
    """
    readable = " ".join(opening_text.split())[:48].strip() or "conversation"
    digest = hashlib.sha1(opening_text.encode("utf-8")).hexdigest()[:8]
    return f"{safe_segment(readable)}-{digest}"


def archive_lock_path(path: str) -> str:
    """The sidecar file the archive's lock sits on.

    Nothing is written to it and it is never removed: the lock is the operating
    system's, released when its holder exits, so this file is only a handle. The
    leading dot keeps it out of a casual listing of the archives beside it, and
    the pruner removes it with the archive it belongs to.
    """
    directory, name = os.path.split(path)
    return os.path.join(directory, f".{name}.lock")
