"""The tool surface a cell is given, resolved from zrb's own registration code.

Split out of ``measure.py`` because two callers need the same answer and had
started to disagree: ``measure.py`` sizes the surface, ``run.py`` now hands it
to the model. A second copy of "which tools does preset P register" is a second
thing to keep in step with `common_tools.py`, and the numbers in the ADRs
already drifted once from exactly that.

**Why the runner needs this at all.** pydantic-ai serializes every registered
tool's description *and* parameter schema into every request, so a tool
definition is prompt text the model reads (ADR-0058). zrb leans on that
deliberately: ADR-0045 sorts each rule by what can enforce it and puts per-tool
mechanics — argument semantics, output shape, irreversibility, which tool to
reach for instead — in the docstring rather than the prompt. A harness whose
mock tools carry one-line docstrings is therefore not running zrb's rules with
one section missing; it is running them with the half that ADR-0045 moved out of
the prompt missing, and cannot see any rule that lives there. Measured on this
tree, that half is 2,482 tokens over 20 eager tools against 4,686 tokens of
composed `full` prompt — 35% of the instruction budget, with `Shell` alone at
539.

The definitions are real; only the *implementations* are mocks. ``tool_defs``
returns each tool's shipped ``(name, description, parameters_json_schema)`` and
``run.py`` binds a mock executor to it, so a cell sees the exact bytes a real
request would carry while still running against the in-memory world.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock


class Capture:
    """A ``CommonToolHost`` that records instead of registering."""

    def __init__(self) -> None:
        self.tools: list = []
        self.factories: list = []
        self.toolsets: list = []

    def append_tool(self, *tool) -> None:
        self.tools.extend(tool)

    def append_tool_factory(self, *factory) -> None:
        self.factories.extend(factory)

    def append_toolset_factory(self, *factory) -> None:
        self.toolsets.extend(factory)


def eager_tools(preset: str) -> list:
    """Every tool a request would carry a schema for, factories resolved.

    Sets ``ZRB_LLM_PROFILE`` because `apply_common_tools` reads the preset off
    `CFG` at registration time. Callers that also compose a prompt should
    resolve both up front rather than interleaving them, since the two read the
    same variable.
    """
    os.environ["ZRB_LLM_PROFILE"] = preset
    from zrb.llm.common_tools import apply_common_tools

    host = Capture()
    apply_common_tools(host)
    resolved = list(host.tools)
    for factory in host.factories:
        try:
            produced = factory(MagicMock())
        except Exception:
            continue
        resolved.extend(produced if isinstance(produced, (list, tuple)) else [produced])
    return [t for t in resolved if t is not None]


def as_tool(tool):
    """Normalise a registered entry to a pydantic-ai ``Tool``."""
    from pydantic_ai import Tool

    return tool if isinstance(tool, Tool) else Tool(tool)


def tool_defs(preset: str) -> list:
    """The shipped ``ToolDefinition`` of every *eager* tool in a preset.

    Deferred tools are excluded: only their name reaches the model until it
    searches for one, so their schema is not part of the per-request budget and
    must not be handed to a cell as though it were.
    """
    out = []
    for tool in eager_tools(preset):
        resolved = as_tool(tool)
        if getattr(resolved, "defer_loading", False):
            continue
        out.append(resolved.tool_def)
    return out
