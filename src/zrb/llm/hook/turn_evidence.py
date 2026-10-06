"""LLM-free evidence gates over a turn's messages.

`runner.py` uses these to compute `wrote_files`, `changed_paths` and
`journal_worthy` for the `STOP` hook payload.
"""

from __future__ import annotations

import re
from typing import Any

# Not imported from `llm.tool`, which transitively loads `pydantic_ai`.
FILE_MUTATING_TOOL_NAMES = frozenset({"Write", "Edit", "RM", "MV"})

# Precision over recall: a false positive costs only one cheap async judge call.
_PREFERENCE_SIGNAL_RE = re.compile(
    r"\b(i prefer|please remember|remember that|from now on|going forward|"
    r"always use|never use|as a rule)\b",
    re.IGNORECASE,
)


def turn_wrote_files(
    turn_messages: list[Any], tool_names: frozenset[str] = FILE_MUTATING_TOOL_NAMES
) -> bool:
    """Whether *turn_messages* contains a call to a file-mutating tool."""
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


# Argument names carrying a filesystem path on the mutating tools: `path` for
# Write/Edit/RM, `src`/`dst` for MV.
_PATH_ARG_NAMES = ("path", "src", "dst")


def turn_changed_paths(
    turn_messages: list[Any], tool_names: frozenset[str] = FILE_MUTATING_TOOL_NAMES
) -> list[str]:
    """Paths named by file-mutating tool calls, deduplicated in first-seen order.

    Files changed through a shell command are not seen."""
    from zrb.llm.agent.types import (  # lazy: zrb internal (heavy via transitive)
        ModelResponse,
        ToolCallPart,
    )

    seen: dict[str, None] = {}
    for msg in turn_messages:
        if not isinstance(msg, ModelResponse):
            continue
        for part in getattr(msg, "parts", []):
            if not isinstance(part, ToolCallPart) or part.tool_name not in tool_names:
                continue
            try:
                args = part.args_as_dict()
            except ValueError:
                continue
            for name in _PATH_ARG_NAMES:
                value = args.get(name)
                if isinstance(value, str) and value:
                    seen.setdefault(value, None)
    return list(seen)


def turn_states_preference(turn_messages: list[Any]) -> bool:
    """Whether a user prompt in *turn_messages* reads like a standing preference."""
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
