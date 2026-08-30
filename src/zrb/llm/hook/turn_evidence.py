"""Cheap, LLM-free evidence gates for hooks that only need to act on turns
that actually did something — e.g. the journal-compliance agent hook only
needs to ask a judge model about a turn that touched files, or that stated a
preference worth remembering.

Kept out of `agent/run/history_utils.py` (which owns provider-compat history
*sanitization*, a different concern) even though the caller sits in the same
package — see `runner.py`'s `_execution_loop`, which computes `wrote_files`
and `journal_worthy` for the `STOP` hook payload that `journal_compliance.py`
reads back.
"""

from __future__ import annotations

import re
from typing import Any

# The tools whose docstrings say they change files on disk (`file.py`'s
# `__name__` reassignments). Kept here rather than imported from `llm.tool` —
# that package's tool modules transitively load `pydantic_ai`, which this
# hook-evidence module's lazy-import discipline avoids.
FILE_MUTATING_TOOL_NAMES = frozenset({"Write", "Edit", "RM", "MV"})

# A precision-over-recall heuristic: catches the turns WriteJournalNote's own
# docstring calls highest-value ("said exactly once"), which `wrote_files`
# alone never fires on. Not meant to be exhaustive — a false positive here
# only costs one extra cheap async judge call, not a wrong answer to the user.
_PREFERENCE_SIGNAL_RE = re.compile(
    r"\b(i prefer|please remember|remember that|from now on|going forward|"
    r"always use|never use|as a rule)\b",
    re.IGNORECASE,
)


def turn_wrote_files(
    turn_messages: list[Any], tool_names: frozenset[str] = FILE_MUTATING_TOOL_NAMES
) -> bool:
    """Whether *turn_messages* (this turn's slice of history) contains a call
    to a file-mutating tool. Pure Python, no LLM involved — the cheap half of
    gating an evidence-based journal-compliance hook: only worth asking a
    judge-agent to look at a turn that actually touched files."""
    from zrb.llm.agent.types import (  # lazy: zrb internal (heavy via transitive)
        ModelResponse,
        ToolCallPart,
    )

    for msg in turn_messages:
        if not isinstance(msg, ModelResponse):
            continue
        for part in getattr(msg, "parts", []):
            if isinstance(part, ToolCallPart) and part.tool_name in tool_names:
                return True
    return False


def turn_states_preference(turn_messages: list[Any]) -> bool:
    """Whether *turn_messages* contains a user prompt that reads like a stated
    preference or standing instruction. Pure regex, no LLM involved — the
    cheap half of widening the journal-compliance gate beyond `wrote_files`
    alone, so a preference stated with no file edit still gets a look."""
    from zrb.llm.agent.types import (  # lazy: zrb internal (heavy via transitive)
        ModelRequest,
        UserPromptPart,
    )

    for msg in turn_messages:
        if not isinstance(msg, ModelRequest):
            continue
        for part in getattr(msg, "parts", []):
            if not isinstance(part, UserPromptPart):
                continue
            content = part.content
            if isinstance(content, str) and _PREFERENCE_SIGNAL_RE.search(content):
                return True
    return False
