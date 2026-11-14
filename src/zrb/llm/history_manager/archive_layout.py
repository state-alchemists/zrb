"""Where a conversation's verbatim archive lives, how it is named, and its lock.

Both the summarizer (which writes an archive) and the history manager (which
collects one once no history refers to it) need these names, and the history
manager is the lower of the two — it owns the directory the archives sit in — so
the layout lives here rather than in the writer.

That includes the pointer: the prose a summary leaves behind names its archive
the way `render_archive_pointer` spells it, and the collector finds archives
again by searching written transcripts for that same spelling
(`archive_names_in`). Writer and reader sit together because nothing else joins
them: reword one half alone and the summary still reads correctly while its
archive becomes invisible to the next cleanup.
"""

from __future__ import annotations

import hashlib
import os
import re

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


TOOL_RESULTS_DIR_SUFFIX = ".tool-results"
"""Suffix of the directory beside an archive holding its pruned tool results."""


def tool_results_dir(archive_path: str) -> str:
    """The directory of verbatim tool results belonging to *archive_path*.

    One directory per conversation, named after the archive without its
    extension, so the history manager collects the two together: the archive is
    the only copy of the text a summary dropped, and these files are the only
    copy of the text a prune dropped.
    """
    root, name = os.path.split(archive_path)
    stem = name[:-3] if name.endswith(".md") else name
    return os.path.join(root, f"{stem}{TOOL_RESULTS_DIR_SUFFIX}")


def render_archive_pointer(archive_path: str) -> str:
    """The deterministic pointer a summary leaves to its archive.

    Written by this module, never by the summarizer model: the path must be the
    real one on this machine, and a model asked to repeat it can mangle or
    invent it. `archive_names_in` reads this exact prose back out.
    """
    return (
        "## Verbatim history archive\n\n"
        "The messages this summary replaced are archived word for word, "
        f"append-only, at:\n\n`{archive_path}`\n\n"
        "Read that file when this summary is not detailed enough; it holds the "
        "original text of every compacted message (attachment bytes are named "
        "there, not copied), and later compactions append to the same file."
    )


# The archive filename as a pointer spells it: the path in backticks ends in
# `verbatim/<name>.md` (a backslash on Windows). Capturing the name alone lets a
# referenced archive be matched whatever directory it sits in. A space is a
# valid character in that name -- safe_segment() keeps one from a session name --
# so only the markdown/quoting delimiters the pointer could be wrapped in are
# excluded, not whitespace in general.
_ARCHIVE_REFERENCE = re.compile(r"verbatim[/\\]([^`)'\"\n]+\.md)")

# The directory a pruned tool result points at: `verbatim/<name>.tool-results/`
# followed by the call id. The capture stops at the path separator, unlike the
# archive pattern above, because this name is a directory and the file inside it
# is not part of the reference.
_TOOL_RESULTS_REFERENCE = re.compile(r"verbatim[/\\]([^/\\`)'\"\n]+\.tool-results)")


def archive_names_in(text: str) -> set[str]:
    """The archive filenames *text* points at.

    Searched rather than parsed: a pointer is a sentence inside a summary, and a
    transcript that is no longer valid JSON still names the archive it was
    written against. Skipping it would turn a corrupt transcript into a deleted
    archive.
    """
    return set(_ARCHIVE_REFERENCE.findall(text))


def tool_results_names_in(text: str) -> set[str]:
    """The tool-result directory names *text* points at."""
    return set(_TOOL_RESULTS_REFERENCE.findall(text))
