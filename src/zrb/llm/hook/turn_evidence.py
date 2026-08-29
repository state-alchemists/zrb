"""Cheap, LLM-free evidence gates for hooks that only need to act on turns
that actually did something — e.g. the journal-compliance agent hook only
needs to ask a judge model about a turn that touched files.

Kept out of `agent/run/history_utils.py` (which owns provider-compat history
*sanitization*, a different concern) even though the caller sits in the same
package — see `runner.py`'s `_execution_loop`, which computes `wrote_files`
for the `STOP` hook payload that `journal_compliance.py` reads back.
"""

from __future__ import annotations

from typing import Any

# The tools whose docstrings say they change files on disk (`file.py`'s
# `__name__` reassignments). Kept here rather than imported from `llm.tool` —
# that package eagerly imports `pydantic_ai` (see `common_tools.py`'s own
# circular-import note), which this module's lazy-import discipline avoids.
FILE_MUTATING_TOOL_NAMES = frozenset({"Write", "Edit", "RM", "MV"})


def turn_wrote_files(
    turn_messages: list[Any], tool_names: frozenset[str] = FILE_MUTATING_TOOL_NAMES
) -> bool:
    """Whether *turn_messages* (this turn's slice of history) contains a call
    to a file-mutating tool. Pure Python, no LLM involved — the cheap half of
    gating an evidence-based journal-compliance hook: only worth asking a
    judge-agent to look at a turn that actually touched files."""
    from pydantic_ai.messages import (  # lazy: heavy third-party
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
