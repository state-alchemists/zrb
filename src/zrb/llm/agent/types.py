"""Re-exported pydantic-ai types for annotation use elsewhere in zrb.

`create_agent()` (`agent/common.py`) is the one place that constructs a real
`pydantic_ai.Agent` (ADR-0036). This module is its companion for the far more
common case: a file that only needs a pydantic-ai *type* to annotate a
parameter or return value, with no `Agent` construction or run-loop logic of
its own. Importing from here instead of `pydantic_ai` directly collapses
those signature-only call sites onto one import path.

Deliberately excluded: concrete model/provider classes (`OpenAIChatModel`,
`Provider`, `known_model_names`, ...). Re-exporting those would start to look
like the "bespoke provider abstraction" ADR-0037 rejects. `Model` itself is
re-exported below because it's used purely as an annotation everywhere it
appears in zrb — actual provider/model *resolution* stays exactly where
ADR-0037 leaves it, in `llm/config/config.py`, importing `pydantic_ai`
directly.

Every name here is a plain re-export — zero logic, zero behavior change.
Most existing call sites import these names inside `if TYPE_CHECKING:`
blocks (already zero-cost at runtime); importing this module there instead
of `pydantic_ai` directly changes nothing about that.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic_ai import Tool, ToolReturn, UserContent
    from pydantic_ai.capabilities import AbstractCapability
    from pydantic_ai.messages import ModelMessage
    from pydantic_ai.models import Model
    from pydantic_ai.settings import ModelSettings
    from pydantic_ai.tools import ToolFuncEither
    from pydantic_ai.toolsets import AbstractToolset
    from pydantic_ai.usage import RequestUsage, RunUsage

__all__ = [
    "AbstractCapability",
    "AbstractToolset",
    "Model",
    "ModelMessage",
    "ModelSettings",
    "RequestUsage",
    "RunUsage",
    "Tool",
    "ToolFuncEither",
    "ToolReturn",
    "UserContent",
]
