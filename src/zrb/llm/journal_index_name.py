"""Shared validation for ``LLM_JOURNAL_INDEX_FILE``.

The journal writers (``llm/tool/journal_write.py``) and the live-context reader
(``llm/prompt/live_context.py``) resolve the root and category indexes from
this one knob. Both must reject the same malformed values before joining them
into a path — a reader that trusted a value the writer would refuse could be
pointed at a file outside the journal entirely. Kept at the top of ``llm/`` so
neither package has to import the other to share it.
"""

import os

# The writers splice this name, unescaped, into generated Markdown link
# syntax (`[label](category/<name>)`). `_directory_link_re()` happens to
# recover the right category even when `<name>` carries one of these — Python's
# backtracking regex engine retries shorter spans until the escaped literal
# suffix matches — but that correctness rides on a regex implementation detail
# a future rewrite could drop. Rejected outright instead of relied upon.
_MARKDOWN_DELIMITERS = frozenset("()[]`")


def resolve_journal_index_name(name: str) -> str:
    """Return *name* if it is a bare filename, else raise ``ValueError``.

    Rejects an empty value, ``.``/``..``, a backslash, a directory component
    — including an absolute path or a ``../`` escape, since `os.path.basename`
    of either differs from the value itself — and a Markdown link delimiter,
    since every writer splices this name straight into `[label](...)` syntax.
    """
    if (
        not name
        or name in (".", "..")
        or os.path.basename(name) != name
        or "\\" in name
        or not _MARKDOWN_DELIMITERS.isdisjoint(name)
    ):
        raise ValueError(
            "[SYSTEM SUGGESTION]: LLM_JOURNAL_INDEX_FILE must be a filename "
            "without directory components or Markdown link delimiters "
            "((, ), [, ], `)."
        )
    return name
