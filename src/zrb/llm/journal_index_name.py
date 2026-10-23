"""Shared validation for ``LLM_JOURNAL_INDEX_FILE``.

The journal writers (``llm/tool/journal_write.py``) and the live-context reader
(``llm/prompt/live_context.py``) resolve the root and category indexes from
this one knob. Both must reject the same malformed values before joining them
into a path — a reader that trusted a value the writer would refuse could be
pointed at a file outside the journal entirely. Kept at the top of ``llm/`` so
neither package has to import the other to share it.
"""

import os


def resolve_journal_index_name(name: str) -> str:
    """Return *name* if it is a bare filename, else raise ``ValueError``.

    Rejects an empty value, ``.``/``..``, a backslash, and anything with a
    directory component — including an absolute path or a ``../`` escape —
    since `os.path.basename` of either differs from the value itself.
    """
    if (
        not name
        or name in (".", "..")
        or os.path.basename(name) != name
        or "\\" in name
    ):
        raise ValueError(
            "[SYSTEM SUGGESTION]: LLM_JOURNAL_INDEX_FILE must be a filename "
            "without directory components."
        )
    return name
